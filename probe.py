import telnetlib
import argparse
import random
import re
import sqlite3
import datetime

rand = random.SystemRandom()
closestGreater = re.compile(r"Completed probe request: 0\.\d+ -> (0\.\d+)")

#Parse current node's location and UID, previous UID, and peer locations and UIDs.
#UIDs are integers, and locations are decimals.
#group 1: current location
#group 2: current UID
#group 3: previous UID
#group 4: comma-separated peer locations
#group 5: comma-separated peer UIDs
parseTrace = re.compile(r"location=(0\.\d+)node UID=([-\d]*) prev UID=([-\d]*) peer locs=\[([-\d ,.]*)\] peer UIDs=\[([-\d ,]*)\]")

parser = argparse.ArgumentParser(description="Make probes to random network locations, saving the results to the specified database.")
parser.add_argument('-t', dest="numThreads", default=5, type=int,\
                    help="Number of simultanious probe threads to run. Default 5 threads.")
parser.add_argument('--host', dest="host", default="127.0.0.1",\
                    help="Telnet host; Freenet node to connect to. Default 127.0.0.1.")
parser.add_argument('-p', dest="port", default=2323, type=int,\
                    help="Port the target node is running TMCI on. Default port 2323.")
parser.add_argument('-N', dest="numProbes", default=120, type=int,\
                    help="Number of total probes to make in each thread. Default 120 probes.")
parser.add_argument('-w', dest="probeWait", default=30, type=int,\
                    help="Number of seconds to wait for a probe response. Default 30 seconds.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")

args = parser.parse_args()

db = sqlite3.connect(args.databaseFile)

db.execute("create table if not exists uids(uid, time)")

prompt="TMCI> "
tn = telnetlib.Telnet(args.host, args.port)

#Read through intial help message.
tn.read_until(prompt)

#TODO: Thread this out into requested number of processes.
#Each thread will need its own sqlite and telnet connection.
for _ in range(args.numProbes):
	target = rand.random()
	tn.write("PROBE: {0}\n".format(target))
	raw = tn.read_until(prompt, args.probeWait)
	#TODO: What if timeout elapses? Need to skip parsing attempt.
	#TODO: Wait time between probe attempts.

	currentTime = datetime.datetime.utcnow()
	
	#Take the right side of "Completed probe request: <target location> -> <closest found location>"
	location = closestGreater.search(raw)
	if location is not None:
		#print("Closest greater location from target ", location.group(1))
	#else:
		#TODO: Is this something worth logging?
		#print("Probe request to {0} did not complete: {1} ".format(target, raw))
	
	#Parse for locations and UIDs of each trace's node and its peers.
	for trace in parseTrace.findall(raw):
		#Of node described by current trace.
		location = trace[0]
		UID = trace[1]
		prevUID = trace[2]
		peerLocs = trace[3].split(',')
		peerUIDs = trace[4].split(',')

		for uid in peerUIDs + [UID, prevUID]:
			db.execute("insert into uids(uid, time) values (?, ?)", (uid, currentTime))
		
		#print("Trace through location ", location, " with UID ", UID, ", previously through UID ", prevUID, " with peer locations ", peerLocs, " and peer UIDs ", peerUIDs)
	
	#Commit after parsing and inserting each probe.
	db.commit()

db.close()
