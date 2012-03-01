import telnetlib
import argparse
import random
import re
import sqlite3
import datetime
import time
import shlex
from sys import executable, exit
from subprocess import Popen
import concurrent.futures
#TODO: function to log line appended to current timestamp. Logger should be able to do that.

#Telnet prompt
prompt="TMCI> "

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

class traceResult:
	def __init__(self, location, UID, peerLocs, peerUIDs):
		self.location = location
		self.UID = UID
		self.peerLocs = peerLocs
		self.peerUIDs = peerUIDs

class probeResult:
	def __init__(self, target, start=datetime.datetime.utcnow()):
		self.target = target
		#Time probe completed
		self.start = start
		
		self.closest = 0.0
		self.traces = []
		self.end = datetime.datetime.utcnow()

def probe(args, wait = 0):
	if wait > 0:
		time.sleep(wait)
	
	target = rand.random()	

	tn = telnetlib.Telnet(args.host, args.port)
	
	#Read through intial help message.
	tn.read_until(prompt)
	
	if args.verbosity > 0:
		print("{0}: Starting probe to {1}.".format(datetime.datetime.now(), target))
	
	tn.write("PROBE: {0}\n".format(target))
	
	result = probeResult(target)
	raw = tn.read_until(prompt, args.probeTimeout)
	
	#TODO: What if timeout elapses? Need to skip parsing attempt.
	if args.verbosity > 0:
		print("{0}: Probe finished. Took {1} sec.".format(datetime.datetime.now(), (datetime.datetime.utcnow() - result.start).seconds))

	if args.verbosity > 1:
		#TODO: Reasonable to start and end block with newlines? Might be misleading for the end.
		print("---Begin raw response---\n{0}\n---End raw response---".format(raw))
	
	#Check for closest location to target location reached. If no such entry exists, insert NULL/None.
	closest = closestGreater.search(raw)
	if closest is not None:
		closest = closest.group(1)
	
	result.closest = closest
	
	#Parse for locations and UIDs of each trace's node and its peers.
	for trace in parseTrace.findall(raw):
		#Of node described by current trace.
		location = trace[0]
		UID = trace[1]
		#TODO: Ideally there'd be a way to find just the numbers with the regex,
		#but that's been difficult.
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
	return result

parser = argparse.ArgumentParser(description="Make probes to random network locations, saving the results to the specified database.")

parser.add_argument('-t', dest="numThreads", default=5, type=int,\
                    help="Number of simultanious probe threads to run. Default 5 threads.")
parser.add_argument('--host', dest="host", default="127.0.0.1",\
                    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
parser.add_argument('-p', dest="port", default=2323, type=int,\
                    help="Port the target node is running TMCI on. Default port 2323.")
#TODO: How much do higher values affect results?
parser.add_argument('--timeout', dest="probeTimeout", default=30, type=int,\
                    help="Number of seconds before timeout when waiting for probe. Default 30 seconds.")
parser.add_argument('--wait', dest="probeWait", default=30, type=int,\
                    help="Minimum amount of time to wait between probes. Default 30 seconds.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-v', dest="verbosity", action='count',\
                   help="Increase verbosity level. First level adds probe and database operation timing, second adds raw probe response. Default none.")

args = parser.parse_args()

#Ensure the database holds the required tables, columns, and indicies. Better now than during each thread.
db = sqlite3.connect(args.databaseFile)
db.execute("create table if not exists uids(uid, time)")
#Index to speed up time-based UID analysis.
db.execute("create index if not exists uid_index on uids(uid)")
db.execute("create index if not exists time_index on uids(time)")

#probeID is unique among probes
db.execute("create table if not exists probes(probeID INTEGER PRIMARY KEY, time, target, closest)")

#traceID is not unique among traces for a given probe; only one peer location or UID is stored per entry.
db.execute("create table if not exists traces(probeID, traceNum, uid, location, peerLoc, peerUID)")
#Index to speed up histogram generation. TODO: Remove any indicies which end up being misguided.
db.execute("create index if not exists probeID_index on traces(traceNum, probeID)")
db.execute("create index if not exists UID_index on traces(uid)")

db.commit()

if args.numThreads < 1:
	print("Cannot run fewer than one thread.")
	exit(1)

#Cursor needed for lastrowid so that traces can be inserted under the correct ProbeID.
cursor = db.cursor()


executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.numThreads)
#TODO: Duplication between this and the refilling line.
threads = []
#Stagger starting time throughout wait period.
staggerTime = args.probeWait / args.numThreads
for i in range(args.numThreads):
	threads += [executor.submit(probe, args, i*staggerTime)]

#Keep numThreads probe threads running until terminated. Must refill container.
for thread in concurrent.futures.as_completed(threads):
	if thread.exception() is not None:
		#TODO: logger
		print("Probe thread exited with exception: {0}".format(thread.exception()))
	else:
		result = thread.result()
		
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
	
		db.commit()

		#If the minimum wait time between probes has not elapsed, wait that long.
		#TODO: http://twistedmatrix.com/documents/current/api/twisted.internet.task.LoopingCall.html
		afterDatabase = datetime.datetime.utcnow()
		databaseTime = (afterDatabase - result.end).seconds
		sinceProbe = (afterDatabase - result.start).seconds
		wait = args.probeWait - sinceProbe
		if args.verbosity > 0:
			print("{0}: {1} traces committed to database in {2} seconds. {3} sec since probe. Waiting {4} sec.".format(datetime.datetime.now(), traceID, databaseTime, sinceProbe, wait))

		#Replace completed thread. TODO: Does this actually work?
		threads += [executor.submit(probe, args, wait)]
