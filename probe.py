import telnetlib
import argparse
import random
import re
import sqlite3
import datetime
import time
import shlex
from sys import exit
from twisted.internet import reactor
from signal import signal, SIGINT, SIG_DFL
from threading import Thread
import logging

#Telnet prompt
prompt="TMCI> "

#Which random generator to use.
rand = random.SystemRandom()

#Not much use; stored anyway.
closestGreater = re.compile(r"Completed probe request: 0\.\d+ -> (0\.\d+)")

#Parse current node's location and UID, previous UID, and peer locations and UIDs.
#UIDs are integers, and locations are decimals.
#group 1: current location
#group 2: current UID
#group 3: comma-separated peer locations
#group 4: comma-separated peer UIDs
parseTrace = re.compile(r"location=(-?\d+\.\d+)node UID=(-?\d+) prev UID=-?\d+ peer locs=\[([-\d ,.]*)\] peer UIDs=\[([-\d ,]*)\]")

def insert(args, result):
	start = datetime.datetime.utcnow()
	db = sqlite3.connect(args.databaseFile)
	#Cursor needed for lastrowid so that traces can be inserted under the correct ProbeID.
	cursor = db.cursor()
	#NULL prompt the database to assign a key as probeID is an INTEGER PRIMARY KEY.
	cursor.execute("insert into probes(probeID, time, target, closest) values (NULL, ?, ?, ?)", [result.end, result.target, result.closest])
	
	probeID = cursor.lastrowid
	
	traceID = 0
	for trace in result.traces:
		for uid in trace.peerUIDs + [trace.UID]:
			db.execute("insert into uids(uid, time) values (?, ?)", (uid, result.end))

		#TODO: Cleaner way to loop over two containers of the same length simultaniously?
		assert len(trace.peerLocs) == len(trace.peerUIDs)
		for i in range(len(trace.peerLocs)):
			db.execute("insert into traces(probeID, traceNum, uid, location, peerLoc, peerUID) values (?, ?, ?, ?, ?, ?)", (probeID, traceID, trace.UID, trace.location, trace.peerLocs[i], trace.peerUIDs[i]))	
		traceID += 1

	cursor.close()
	db.commit()
	db.close()
	end = datetime.datetime.utcnow()
	logging.info("Committed {0} traces in {1}.".format(traceID, end - start))

class traceResult:
	def __init__(self, location, UID, peerLocs, peerUIDs):
		self.location = location
		self.UID = UID
		self.peerLocs = peerLocs
		self.peerUIDs = peerUIDs

class probeResult:
	def __init__(self, target, start=None):
		self.target = target
		if not start:
			self.start = datetime.datetime.utcnow()
		
		#Should be updated.
		self.closest = 0.0
		self.traces = []
		#Time probe completed
		self.end = datetime.datetime.utcnow()

def probe(args, wait = 0):
	while True:
		if wait > 0:
			logging.info("Waiting {0} seconds before starting probe.".format(wait))
			time.sleep(wait)
		
		target = rand.random()	

		tn = telnetlib.Telnet(args.host, args.port)
		
		#Read through intial help message.
		tn.read_until(prompt)
		
		logging.info("Starting probe to {0}.".format(target))
		
		tn.write("PROBE: {0}\n".format(target))
		
		result = probeResult(target)
		raw = tn.read_until(prompt, args.probeTimeout)
		
		#TODO: What if timeout elapses? Need to skip parsing attempt.
		logging.info("Probe finished. Took {0}.".format(datetime.datetime.utcnow() - result.start))

		logging.debug("---Begin raw response---\n{0}\n---End raw response---".format(raw))
		
		#Check for closest location to target location reached. Insert NULL/None if unspecified.
		closest = closestGreater.search(raw)
		if closest is not None:
			closest = float(closest.group(1))
		else:
			logging.warning("Incomplete probe response. Consider increasing probe timeout.")
		
		result.closest = closest
		
		#Parse for locations and UIDs of each trace's node and its peers.
		for trace in parseTrace.findall(raw):
			#Of node described by current trace.
			location = float(trace[0])
			UID = long(trace[1])
			peerLocs = []
			for val in trace[2].split(','):
				#Ignore empty string
				if val: 
					peerLocs.append(float(val))
			peerUIDs = []
			for val in trace[3].split(','):
				if val:
					peerUIDs.append(long(val))
			
			result.traces.append(traceResult(location, UID, peerLocs, peerUIDs))
		
		result.end = datetime.datetime.utcnow()
		reactor.callFromThread(insert, args, result)
		wait = args.probeWait - (result.end - result.start).seconds

def sigint_handler(signum, frame):
	logging.info("Got signal {0}. Shutting down.".format(signum))
	signal(SIGINT, SIG_DFL)
	reactor.stop()

def main():
	parser = argparse.ArgumentParser(description="Make probes to random network locations, saving the results to the specified database.")

	parser.add_argument('--threads, -t', dest="numThreads", default=5, type=int,\
			    help="Number of simultanious probe threads to run. Default 5 threads.")
	parser.add_argument('--host', dest="host", default="127.0.0.1",\
			    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
	parser.add_argument('--port, -p', dest="port", default=2323, type=int,\
			    help="Port the target node is running TMCI on. Default port 2323.")
	#TODO: How much do higher values affect results?
	parser.add_argument('--timeout', dest="probeTimeout", default=30, type=int,\
			    help="Seconds before timeout when waiting for probe. Default 30 seconds.")
	parser.add_argument('--wait', dest="probeWait", default=30, type=int,\
			    help="Minimum seconds to wait between probes. Per-thread. Default 30 seconds.")
	parser.add_argument('--database, -d', dest="databaseFile", default="database.sql",\
			    help="Path to database file. Default \"database.sql\"")
	parser.add_argument('-v', dest="verbosity", action='count',\
			   help="Verbosity level. One is INFO, two is DEBUG. Default WARNING.")
	parser.add_argument('--log, -l', dest="logFile", default="probe.log",\
                            help="File log is written to. Default probe.log")

	args = parser.parse_args()

	level = None
	if args.verbosity == 0:
		level = logging.WARNING
	elif args.verbosity == 1:
		level = logging.INFO
	elif args.verbosity > 1:
		level = logging.DEBUG

	logging.basicConfig(format="%(asctime)s - %(threadName)s - %(levelname)s: %(message)s", level=level, filename=args.logFile)
	logging.info("Starting up.")
	#Logs that shutdown is occuring.
	signal(SIGINT, sigint_handler)

	#Ensure the database holds the required tables, columns, and indicies.
	db = sqlite3.connect(args.databaseFile)
	db.execute("create table if not exists uids(uid, time)")
	#Index to speed up time-based UID analysis.
	db.execute("create index if not exists uid_index on uids(uid)")
	db.execute("create index if not exists time_index on uids(time)")

	#probeID is unique among probes
	db.execute("create table if not exists probes(probeID INTEGER PRIMARY KEY, time, target, closest)")

	#traceID is not unique among a probe's traces; only one peer location or UID is stored per entry.
	db.execute("create table if not exists traces(probeID, traceNum, uid, location, peerLoc, peerUID)")
	#Index to speed up histogram generation. TODO: Remove any indicies which end up being misguided.
	db.execute("create index if not exists probeID_index on traces(traceNum, probeID)")
	db.execute("create index if not exists UID_index on traces(uid)")

	db.commit()
	db.close()

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

	reactor.callWhenRunning(startThreads, threads)
	reactor.run()

if __name__ == "__main__":
    main()
