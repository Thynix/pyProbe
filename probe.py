import argparse
import random
import sqlite3
import datetime
import time
from sys import exit, stderr
from twisted.internet import reactor, protocol
from signal import signal, SIGINT, SIGTERM, SIG_DFL
import thread
import logging
from twisted.application import service
from ConfigParser import SafeConfigParser
from string import split
from twistedfcp.protocol import FreenetClientProtocol, IdentifiedMessage
from twistedfcp import message
from twisted.python import log

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

def insert(args, probe_type, result):
	start = datetime.datetime.utcnow()
	db = sqlite3.connect(args.databaseFile)

	header = result.name
	htl = args.hopsToLive
	now = datetime.datetime.utcnow()
	if header == "ProbeError":
		#type should always be defined, but the code might not be.
		code = None
		if CODE in result:
			description = result[CODE]
		db.execute("insert into error(time, htl, probe_type, error_type, code) values(?, ?, ?, ?, ?)", (now, htl, probe_type, result[TYPE], code))
	elif header == "ProbeRefused":
		db.execute("insert into refused(time, htl, probe_type) values(?, ?, ?)", (now, htl, probe_type))
	elif probe_type == "BANDWIDTH":
		db.execute("insert into bandwidth(time, htl, KiB) values(?, ?, ?)", (now, htl, result[BANDWIDTH]))
	elif probe_type == "BUILD":
		db.execute("insert into build(time, htl, build) values(?, ?, ?)", (now, htl, result[BUILD]))
	elif probe_type == "IDENTIFIER":
		db.execute("insert into identifier(time, htl, identifier, percent) values(?, ?, ?, ?)", (now, htl, result[PROBE_IDENTIFIER], result[UPTIME_PERCENT]))
	elif probe_type == "LINK_LENGTHS":
		max_id = db.execute("select max(id) from link_lengths").fetchone()[0]
		new_id = 0
		if max_id is not None:
			new_id = max_id + 1

		for length in split(result[LINK_LENGTHS], ';'):
			db.execute("insert into link_lengths(time, htl, length, id) values(?, ?, ?, ?)", (now, htl, length, new_id))
		db.execute("insert into peer_count(time, htl, peers) values(?, ?, ?)", (now, htl, len(result[LINK_LENGTHS])))
	elif probe_type == "LOCATION":
		db.execute("insert into location(time, htl, location) values(?, ?, ?)", (now, htl, result[LOCATION]))
	elif probe_type == "STORE_SIZE":
		db.execute("insert into store_size(time, htl, GiB) values(?, ?, ?)", (now, htl, result[STORE_SIZE]))
	elif probe_type == "UPTIME_48H":
		db.execute("insert into uptime_48h(time, htl, percent) values(?, ?, ?)", (now, htl, result[UPTIME_PERCENT]))
	elif probe_type == "UPTIME_7D":
		db.execute("insert into uptime_7d(time, htl, percent) values(?, ?, ?)", (now, htl, result[UPTIME_PERCENT]))

	db.commit()
	db.close()
	logging.info("Committed {0} ({1}) in {2}.".format(header, probe_type, datetime.datetime.utcnow() - start))

def sigint_handler(signum, frame):
	logging.info("Got signal {0}. Shutting down.".format(signum))
	signal(SIGINT, SIG_DFL)
	reactor.stop()

def init_database(db):
	#BANDWIDTH
	db.execute("create table if not exists bandwidth(time, htl, KiB)")
	db.execute("create index if not exists time_index on bandwidth(time)")

	#BUILD
	db.execute("create table if not exists build(time, htl, build)")
	db.execute("create index if not exists time_index on build(time)")

	#IDENTIFIER
	db.execute("create table if not exists identifier(time, htl, identifier, percent)")
	db.execute("create index if not exists time_index on identifier(time, identifier)")

	#LINK_LENGTHS
	db.execute("create table if not exists link_lengths(time, htl, length, id)")
	db.execute("create index if not exists time_index on link_lengths(time)")

	db.execute("create table if not exists peer_count(time, htl, peers)")
	db.execute("create index if not exists time_index on peer_count(time)")

	#LOCATION
	db.execute("create table if not exists location(time, htl, location)")
	db.execute("create index if not exists time_index on location(time)")

	#STORE_SIZE
	db.execute("create table if not exists store_size(time, htl, GiB)")
	db.execute("create index if not exists time_index on peer_count(time)")

	#UPTIME_48H
	db.execute("create table if not exists uptime_48h(time, htl, percent)")
	db.execute("create index if not exists time_index on uptime_48h(time)")

	#UPTIME_7D
	db.execute("create table if not exists uptime_7d(time, htl, percent)")
	db.execute("create index if not exists time_index on uptime_7d(time)")

	#Type is included in error and refused to better inform possible
	#estimates of error in probe results.
	#Error
	db.execute("create table if not exists error(time, htl, probe_type, error_type, code)")
	db.execute("create index if not exists time_index on error(time)")

	#Refused
	db.execute("create table if not exists refused(time, htl, probe_type)")
	db.execute("create index if not exists time_index on refused(time)")

	db.commit()
	db.close()

#Inactive class for holding arguments in attributes.
class Arguments(object):
	pass

def MakeRequest(ProbeType, HopsToLive):
	return IdentifiedMessage("ProbeRequest",\
				 [(TYPE, ProbeType), (HTL, HopsToLive)])

class CommitHook:
	"""
	Stores a probe type and commits a result to the database when called.
	Assumes the time of its creation is when the probe request is sent.
	"""
	def __init__(self, args, probeType):
		logging.info("Sending {0}.".format(probeType))
		self.sent = datetime.datetime.utcnow()
		self.args = args
		self.probeType = probeType

	def __call__(self, message):
		logging.info("Got results in {0}.".format(datetime.datetime.utcnow() - self.sent))
		#Commit results
		reactor.callFromThread(insert, self.args, self.probeType, message)
		return True

class ProbeCallback:
	def __init__(self, proto, args):
		"""Sends first probe request"""
		self.args = args
		self.proto = proto
		self.send()

	def send(self):
		"""Internal function to send a probe request and schedule the next.
		   This begins a loop, and so need only be called once at startup."""
		probeType = random.choice(self.args.types)
		self.proto.do_session(MakeRequest(probeType, self.args.hopsToLive), CommitHook(self.args, probeType))

		reactor.callLater(self.args.probeWait, self.send)

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

	def __init__(self, args):
		self.args = args

	def buildProtocol(self, addr):
		proto = FreenetClientProtocol()
		proto.factory = self

		#Register a callback for the NodeHello in order to send messages
		#once the transport is established.
		class StartProbes:
			def __init__(self, proto, args):
				self.proto = proto
				self.args = args

			def callback(self, message):
				delay_per = self.args.probeWait / self.args.numThreads

				def start(i):
					logging.info("Starting probe instance {0}.".format(i))
					ProbeCallback(self.proto, self.args)

				for i in range(self.args.numThreads):
					reactor.callLater(delay_per * i, start, i)

		proto.deferred['NodeHello'] = StartProbes(proto, self.args)
		proto.deferred['ProtocolError'] = Complain()

		return proto

	def clientConnectionLost(self, connector, reason):
		logging.warning("Lost connection: {0}".format(reason))

		#Stop pending probe requests - new requests will be started upon reconnection.
		for delayed_call in reactor.getDelayedCalls():
			delayed_call.cancel()

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
	for arg in [ "numThreads", "port", "probeWait", "hopsToLive" ]:
		setattr(args, arg, int(getattr(args, arg)))

	#Convert types list to list
	args.types = split(args.types, ",")

	logging.basicConfig(format="%(asctime)s - %(levelname)s: %(message)s", level=getattr(logging, args.verbosity), filename=args.logFile)
	logging.info("Starting up.")

	#Ensure the database holds the required tables, columns, and indicies.
	init_database(sqlite3.connect(args.databaseFile))

	if args.numThreads < 1:
		print("Cannot run fewer than one thread.")
		exit(1)

	reactor.callWhenRunning(signal, SIGINT, sigint_handler)
	reactor.callWhenRunning(signal, SIGTERM, sigint_handler)
	reactor.connectTCP(args.host, args.port, FCPReconnectingFactory(args))

#run main if run with twistd: it will start the reactor.
if __name__ == "__builtin__":
	main()

#Run main and start reactor if run as script
if __name__ == '__main__':
	main()
	reactor.run()
