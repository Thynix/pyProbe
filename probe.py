import argparse
import random
import sqlite3
import datetime
import time
from sys import exit
from twisted.internet import reactor
from signal import signal, SIGINT, SIG_DFL
from threading import Thread
import logging
from twisted.application import service
from ConfigParser import SafeConfigParser
import fcp
from string import split

__version__ = "0.1"
application = service.Application("pyProbe")

#Which random generator to use.
rand = random.SystemRandom()

#FCP Message fields
BANDWIDTH = "outputBandwidthUpperLimit"
BUILD = "build"
DESCRIPTION = "description"
IDENTIFIER = "identifier"
UPTIME_PERCENT = "uptimePercent"
LINK_LENGTHS = "linkLengths"
STORE_SIZE = "storeSize"
TYPE = "type"

def insert(args, probe_type, result):
	start = datetime.datetime.utcnow()
	db = sqlite3.connect(args.databaseFile)

	header = result["header"]
	htl = args.hopsToLive
	now = datetime.datetime.utcnow()
	if header == "ProbeError":
		#type should always be defined, but description might not be.
		db.execute("insert into error(time, htl, type, description) values(?, ?, ?, ?)", (now, htl, result[TYPE], result.get(DESCRIPTION, None)))
	elif header == "ProbeRefused":
		db.execute("insert into refused(time, htl) values(?, ?)", (now, htl))
	elif probe_type == "BANDWIDTH":
		db.execute("insert into bandwidth(time, htl, KiB) values(?, ?, ?)", (now, htl, result[BANDWIDTH]))
	elif probe_type == "BUILD":
		db.execute("insert into build(time, htl, build) values(?, ?, ?)", (now, htl, result[BUILD]))
	elif probe_type == "IDENTIFIER":
		db.execute("insert into identifier(time, htl, identifier, percent) values(?, ?, ?, ?)", (now, htl, result[IDENTIFIER], result[UPTIME_PERCENT]))
	elif probe_type == "LINK_LENGTHS":
		for length in result[LINK_LENGTHS]:
			db.execute("insert into link_lengths(time, htl, length) values(?, ?, ?)", (now, htl, length))
		db.execute("insert into peer_count(time, htl, peers) values(?, ?, ?)", (now, htl, len(result[LINK_LENGTHS])))
	elif probe_type == "STORE_SIZE":
		db.execute("insert into store_size(time, htl, GiB) values(?, ?, ?)", (now, htl, result[STORE_SIZE]))
	elif probe_type == "UPTIME_48H":
		db.execute("insert into uptime_48h(time, htl, percent) values(?, ?, ?)", (now, htl, result[UPTIME_PERCENT]))
	elif probe_type == "UPTIME_7D":
		db.execute("insert into uptime_7d(time, htl, percent) values(?, ?, ?)", (now, htl, result[UPTIME_PERCENT]))

	db.commit()
	db.close()
	logging.info("Committed {0} in {1}.".format(header, datetime.datetime.utcnow() - start))

def probe(args, wait = 0):
	node = fcp.node.FCPNode(host=args.host, port=args.port)
	while True:
		if wait > 0:
			logging.info("Waiting {0} seconds before starting probe.".format(wait))
			time.sleep(wait)

		probe_type = rand.choice(args.types)

		logging.info("Starting {0} probe.".format(probe_type))

		start = datetime.datetime.utcnow()

		#This will be a list of a dictionary of results.
		result = node.probe(async=False, type=probe_type, hopsToLive=args.hopsToLive)

		logging.info("Probe finished. Took {0}.".format(datetime.datetime.utcnow() - start))

		#Should only be one result: the final one.
		assert(len(result) == 1)
		reactor.callFromThread(insert, args, probe_type, result[0])
		wait = args.probeWait - (datetime.datetime.utcnow() - start).seconds

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
	db.execute("create table if not exists link_lengths(time, htl, length)")
	db.execute("create index if not exists time_index on link_lengths(time)")

	db.execute("create table if not exists peer_count(time, htl, peers)")
	db.execute("create index if not exists time_index on peer_count(time)")

	#STORE_SIZE
	db.execute("create table if not exists store_size(time, htl, GiB)")
	db.execute("create index if not exists time_index on peer_count(time)")

	#UPTIME_48H
	db.execute("create table if not exists uptime_48h(time, htl, percent)")
	db.execute("create index if not exists time_index on uptime_48h(time)")

	#UPTIME_7D
	db.execute("create table if not exists uptime_7d(time, htl, percent)")
	db.execute("create index if not exists time_index on uptime_7d(time)")

	#Error
	db.execute("create table if not exists error(time, htl, type, description)")
	db.execute("create index if not exists time_index on error(time)")

	#Refused
	db.execute("create table if not exists refused(time, htl)")
	db.execute("create index if not exists time_index on refused(time)")

	db.commit()
	db.close()

#Inactive class for holding arguments in attributes so that the rest of the code
#need not reflect a transition from command line arguments to a config file.
class Arguments(object):
	pass

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
	for arg in [ "numThreads", "port", "probeWait" ]:
		setattr(args, arg, int(getattr(args, arg)))

	#Convert types list to list
	args.types = split(args.types, ",")

	logging.basicConfig(format="%(asctime)s - %(threadName)s - %(levelname)s: %(message)s", level=getattr(logging, args.verbosity), filename=args.logFile)
	logging.info("Starting up.")

	#Ensure the database holds the required tables, columns, and indicies.
	init_database(sqlite3.connect(args.databaseFile))

	if args.numThreads < 1:
		print("Cannot run fewer than one thread.")
		exit(1)

	def startThreads(threads):
		for thread in threads:
			thread.start()

	#Stagger starting time throughout wait period.
	staggerTime = args.probeWait / args.numThreads
	threads = []
	for i in range(args.numThreads):
		thread = Thread(target=probe, args=(args, i*staggerTime))
		thread.daemon = True
		threads.append(thread)

	reactor.callWhenRunning(signal, SIGINT, sigint_handler)
	reactor.callWhenRunning(startThreads, threads)

#Main if run as script, builtin for twistd.
if __name__ in ["__main__", "__builtin__"]:
    main()
