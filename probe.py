from __future__ import division
import argparse
import random
from pysqlite2 import dbapi2 as sqlite3
from twisted.enterprise import adbapi
import datetime
import time
from sys import exit, stderr
from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall
from signal import signal, SIGINT, SIGTERM, SIG_DFL
import thread
import logging
from twisted.application import service
from ConfigParser import SafeConfigParser
from string import split
from twistedfcp.protocol import FreenetClientProtocol, IdentifiedMessage
from twistedfcp import message
from twisted.python import log
from fnprobe.db import init_database

__version__ = "0.1"
application = service.Application("pyProbe")

#Log twisted events to Python's standard logging. This will log reconnection
#information at INFO.
log.PythonLoggingObserver().start()

#Which random generator to use.
rand = random.SystemRandom()

#FCP Message fields
BANDWIDTH = "OutputBandwidth"
BUILD = "Build"
CODE = "Code"
PROBE_IDENTIFIER = "ProbeIdentifier"
UPTIME_PERCENT = "UptimePercent"
LINK_LENGTHS = "LinkLengths"
LOCATION = "Location"
STORE_SIZE = "StoreSize"
TYPE = "Type"
HTL = "HopsToLive"
LOCAL = "Local"

def insert(db, args, probe_type, result, duration):
	start = datetime.datetime.utcnow()

	header = result.name
	htl = args.hopsToLive
	now = datetime.datetime.utcnow()

	# Retry insert on locking timeout.
	tries = 0
	success = False
	while not success:
		try:
			insertResult(db, header, htl, result, now, duration, probe_type)
			success = True
		except sqlite3.OperationalError as ex:
			# Database locked. Try again.
			db.rollback()
			logging.warning("Got operational error '{0}'. Tried {1} times before. Retrying.".format(ex, tries))
			tries += 1

	logging.debug("Committed {0} ({1}) in {2}.".format(header, probe_type, datetime.datetime.utcnow() - start))

def insertResult(db, header, htl, result, now, duration, probe_type):
	if header == "ProbeError":
		#type should always be defined, but the code might not be.
		code = None
		if CODE in result:
			description = result[CODE]
		db.execute("insert into error(time, htl, probe_type, error_type, code, duration, local) values(?, ?, ?, ?, ?, ?, ?)", (now, htl, probe_type, result[TYPE], code, duration, result[LOCAL]))
	elif header == "ProbeRefused":
		db.execute("insert into refused(time, htl, probe_type, duration) values(?, ?, ?, ?)", (now, htl, probe_type, duration))
	elif probe_type == "BANDWIDTH":
		db.execute("insert into bandwidth(time, htl, KiB, duration) values(?, ?, ?, ?)", (now, htl, result[BANDWIDTH], duration))
	elif probe_type == "BUILD":
		db.execute("insert into build(time, htl, build, duration) values(?, ?, ?, ?)", (now, htl, result[BUILD], duration))
	elif probe_type == "IDENTIFIER":
		db.execute("insert into identifier(time, htl, identifier, percent, duration) values(?, ?, ?, ?, ?)", (now, htl, result[PROBE_IDENTIFIER], result[UPTIME_PERCENT], duration))
	elif probe_type == "LINK_LENGTHS":
		cur = db.cursor()
		lengths = split(result[LINK_LENGTHS], ';')
		cur.execute("insert into peer_count(time, htl, peers, duration) values(?, ?, ?, ?)", (now, htl, len(lengths), duration))
		new_id = cur.lastrowid
		for length in lengths:
			cur.execute("insert into link_lengths(time, htl, length, id) values(?, ?, ?, ?)", (now, htl, length, new_id))
		cur.close()
	elif probe_type == "LOCATION":
		db.execute("insert into location(time, htl, location, duration) values(?, ?, ?, ?)", (now, htl, result[LOCATION], duration))
	elif probe_type == "STORE_SIZE":
		db.execute("insert into store_size(time, htl, GiB, duration) values(?, ?, ?, ?)", (now, htl, result[STORE_SIZE], duration))
	elif probe_type == "UPTIME_48H":
		db.execute("insert into uptime_48h(time, htl, percent, duration) values(?, ?, ?, ?)", (now, htl, result[UPTIME_PERCENT], duration))
	elif probe_type == "UPTIME_7D":
		db.execute("insert into uptime_7d(time, htl, percent, duration) values(?, ?, ?, ?)", (now, htl, result[UPTIME_PERCENT], duration))

class sigint_handler:
	def __init__(self, pool):
		self.pool = pool

	def __call__(self, signum, frame):
		logging.warning("Got signal {0}. Shutting down.".format(signum))
		self.pool.close()
		signal(SIGINT, SIG_DFL)
		reactor.stop()

#Inactive class for holding arguments in attributes.
class Arguments(object):
	pass

def MakeRequest(ProbeType, HopsToLive):
	return IdentifiedMessage("ProbeRequest",\
				 [(TYPE, ProbeType), (HTL, HopsToLive)])

class SendHook:
	"""
	Sends a probe of a random type and commits the result to the database.
	"""
	def __init__(self, args, proto, pool):
		self.sent = datetime.datetime.utcnow()
		self.args = args
		self.probeType = random.choice(self.args.types)
		self.pool = pool
		logging.debug("Sending {0}.".format(self.probeType))

		proto.do_session(MakeRequest(self.probeType, self.args.hopsToLive), self)

	def __call__(self, message):
		delta = datetime.datetime.utcnow() - self.sent
		# Duration in seconds. Python 2.7 introduced timedelta.total_seconds()
		# but this should run on Python 2.6. (Version in Debian Squeeze.)
		# Seconds per day: 24 hours per day * 60 minutes per hour * 60 seconds per minute = 86400
		# Seconds per microsecond: 1/1000000
		duration = delta.days * 86400 + delta.seconds + delta.microseconds / 1000000
		#Commit results
		self.pool.runWithConnection(insert, self.args, self.probeType, message, duration)
		return True

class Complain:
	"""
	Registered on ProtocolError. If the callback is hit, complains loudly
	and exits, as it's an indication that probes are not supported on the
	target node.
	"""
	def callback(self, message):
		errStr = "Got ProtocolError - node does not support probes."
		logging.error(errStr)
		stderr.write(errStr + '\n')
		#This is in a deferred, not in the main thread, so sys.exit()
		#will throw an ineffective exception.
		thread.interrupt_main()

class FCPReconnectingFactory(protocol.ReconnectingClientFactory):
	"A protocol factory that uses FCP."
	protocol = FreenetClientProtocol

	#Log disconnection and reconnection attempts
	noisy = True

	def __init__(self, args, pool):
		self.args = args
		self.pool = pool

	def buildProtocol(self, addr):
		proto = FreenetClientProtocol()
		proto.factory = self
		proto.timeout = self.args.timeout

		proto.deferred['NodeHello'] = self
		proto.deferred['ProtocolError'] = Complain()

		self.sendLoop = LoopingCall(SendHook, self.args, proto, self.pool)

		return proto

	def callback(self, message):
		self.sendLoop.start(self.args.probePeriod)

	def clientConnectionLost(self, connector, reason):
		logging.warning("Lost connection: {0}".format(reason))
		self.sendLoop.stop()

		#Any connection loss is failure; reconnect.
		protocol.ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

def main():
	config = SafeConfigParser()
	#Case-sensitive to set args attributes correctly.
	config.optionxform = str
	config.read("probe.config")
	defaults = config.defaults()

	def get(option):
		return config.get("OVERRIDE", option) or defaults[option]

	args = Arguments()
	for arg in defaults.keys():
		setattr(args, arg, get(arg))

	#Convert integer options
	for arg in [ "port", "hopsToLive", "probeRate" ]:
		setattr(args, arg, int(getattr(args, arg)))

	#Convert floating point options.
	for arg in [ "timeout", "databaseTimeout" ]:
		setattr(args, arg, float(getattr(args, arg)))

	#Convert types list to list
	args.types = split(args.types, ",")

	# Compute probe period. Rate is easier to think about, so it's used in the
	# config file. probeRate is probes/minute. Period is seconds/probe.
	# 60 seconds   1 minute           seconds
	# ---------- * ---------------- = -------
	# 1 minute     probeRate probes   probe
	args.probePeriod = 60 / args.probeRate

	logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s", level=getattr(logging, args.verbosity), filename=args.logFile)
	logging.info("Starting up.")

	# Sqlite does not support concurrent writes, so make only one connection.
	# In this way adbapi provides a dedicated database thread so that waiting
	# for a lock does not block the reactor thread. It will close the connection
	# in a separate thread, so the Python module should not prevent doing so.
	# Versions of sqlite prior to 3.3.1 are not thread-safe.
	# See https://www.sqlite.org/releaselog/3_3_1.html
	#     https://www.sqlite.org/faq.html#q6
	pool = adbapi.ConnectionPool('sqlite3', args.databaseFile, timeout=args.databaseTimeout, cp_max=1, check_same_thread=False)

	#Ensure the database holds the required tables, columns, and indicies.
	pool.runWithConnection(init_database)


	handler = sigint_handler(pool)
	reactor.callWhenRunning(signal, SIGINT, handler)
	reactor.callWhenRunning(signal, SIGTERM, handler)
	reactor.connectTCP(args.host, args.port, FCPReconnectingFactory(args, pool))

#run main if run with twistd: it will start the reactor.
if __name__ == "__builtin__":
	main()

#Run main and start reactor if run as script
if __name__ == '__main__':
	main()
	reactor.run()
