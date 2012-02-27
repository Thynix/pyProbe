import telnetlib
import argparse
import random
import re
import sqlite3
import datetime
import time

rand = random.SystemRandom()
#Not much use; stored anyway.
closestGreater = re.compile(r"Completed probe request: 0\.\d+ -> (0\.\d+)")

#Parse current node's location and UID, previous UID, and peer locations and UIDs.
#UIDs are integers, and locations are decimals.
#group 1: current location
#group 2: current UID
#group 3: comma-separated peer locations
#group 4: comma-separated peer UIDs
parseTrace = re.compile(r"location=(0\.\d+)node UID=([-\d]*) prev UID=[-\d]* peer locs=\[([-\d ,.]*)\] peer UIDs=\[([-\d ,]*)\]")

parser = argparse.ArgumentParser(description="Make probes to random network locations, saving the results to the specified database.")
parser.add_argument('-t', dest="numThreads", default=5, type=int,\
                    help="Number of simultanious probe threads to run. Default 5 threads.")
parser.add_argument('--host', dest="host", default="127.0.0.1",\
                    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
parser.add_argument('-p', dest="port", default=2323, type=int,\
                    help="Port the target node is running TMCI on. Default port 2323.")
parser.add_argument('-N', dest="numProbes", default=120, type=int,\
                    help="Number of total probes to make in each thread. Default 120 probes.")
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

db = sqlite3.connect(args.databaseFile)
cursor = db.cursor()

db.execute("create table if not exists uids(uid, time)")
#Index to speed up time-based UID analysis.
db.execute("create index if not exists uid_index on uids(uid)")
db.execute("create index if not exists time_index on uids(time)")

#probeID is unique among probes
db.execute("create table if not exists probes(probeID INTEGER PRIMARY KEY, time, target, closest)")

#traceID is not unique among traces for a given probe; only one peer location or UID is stored per entry.
db.execute("create table if not exists traces(probeID, traceNum, time, uid, location, peerLoc, peerUID)")
#Index to speed up histogram generation. TODO: May want to remove any indicies that end up being misguided.
db.execute("create index if not exists peerUIDs_index on traces(traceNum, uid)")
db.execute("create index if not exists numProbes_index on traces(probeID, uid)")

prompt="TMCI> "
tn = telnetlib.Telnet(args.host, args.port)

#Read through intial help message.
tn.read_until(prompt)

#TODO: Thread this out into requested number of processes.
#Each thread will need its own sqlite and telnet connection.
for _ in range(args.numProbes):
	target = rand.random()
	
	if args.verbosity > 0:
		print("{0}: Starting probe to {1}.".format(datetime.datetime.now(), target))
	
	tn.write("PROBE: {0}\n".format(target))
	
	beforeProbe = datetime.datetime.utcnow()
	raw = tn.read_until(prompt, args.probeTimeout)
	afterProbe = datetime.datetime.utcnow()
	
	#TODO: What if timeout elapses? Need to skip parsing attempt.
	if args.verbosity > 0:
		print("{0}: Probe finished. Took {1} sec. Saving traces.".format(datetime.datetime.now(), (afterProbe - beforeProbe).seconds))

	if args.verbosity > 1:
		#TODO: Reasonable to start and end block with newlines? Might be misleading for the end.
		print("---Begin raw response---\n{0}\n---End raw response---".format(raw))
	
	#Check for closest location to target location reached. If no such entry exists, insert NULL/None.
	closest = None
	location = closestGreater.search(raw)
	if location is not None:
		closest = location.group(1)
	
	#NULL prompt the database to assign a key as probeID is an INTEGER PRIMARY KEY.
	cursor.execute("insert into probes(probeID, time, target, closest) values (NULL, ?, ?, ?)", [afterProbe, target, closest])
	probeID = cursor.lastrowid
	
	#Parse for locations and UIDs of each trace's node and its peers.
	traceID = 0
	for trace in parseTrace.findall(raw):
		#Of node described by current trace.
		location = trace[0]
		UID = trace[1]
		#Remove whitespace so that numerically identical values aren't considered different.
		peerLocs = filter(None, trace[2].split(','))
		peerUIDs = filter(None, trace[3].split(','))

		for uid in peerUIDs + [UID]:
			db.execute("insert into uids(uid, time) values (?, ?)", (uid, afterProbe))
		
		assert len(peerLocs) == len(peerUIDs)
		for i in range(len(peerLocs)):
			db.execute("insert into traces(probeID, traceNum, time, uid, location, peerLoc, peerUID) values (?, ?, ?, ?, ?, ?, ?)", (probeID, traceID, afterProbe, UID, location, peerLocs[i], peerUIDs[i]))
		traceID += 1
	
	#Commit after inserting each probe and before waiting.
	db.commit()
	
	#If the minimum wait time between probes has not elapsed, wait that long.
	#TODO: http://twistedmatrix.com/documents/current/api/twisted.internet.task.LoopingCall.html
	afterDatabase = datetime.datetime.utcnow()
	databaseTime = (afterDatabase - afterProbe).seconds
	sinceProbe = (afterDatabase - beforeProbe).seconds
	wait = args.probeWait - sinceProbe
	if args.verbosity > 0:
		print("{0}: {1} traces committed to database in {2} seconds. {3} sec since probe. Waiting {4} sec.".format(datetime.datetime.now(), traceID, databaseTime, sinceProbe, wait))
	if wait > 0:
		time.sleep(wait)

cursor.close()
db.close()
