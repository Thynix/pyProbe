import telnetlib
import argparse
import random
import re
import sqlite3
import datetime
import time

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
#TODO: How much do higher values affect results?
parser.add_argument('--timeout', dest="probeTimeout", default=30, type=int,\
                    help="Number of seconds before timeout when waiting for probe. Default 30 seconds.")
parser.add_argument('--wait', dest="probeWait", default=30, type=int,\
                    help="Minimum amount of time to wait between probes. Default 30 seconds.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-v', dest="verbosity", action='count',\
                   help="Increase verbosity level. First level probe start and stop, second adds probe results, third adds raw probe data. Default none.")

args = parser.parse_args()

db = sqlite3.connect(args.databaseFile)

db.execute("create table if not exists uids(uid, time)")

prompt="TMCI> "
tn = telnetlib.Telnet(args.host, args.port)

#Read through intial help message.
tn.read_until(prompt)

#Don't wait before starting first probe.
startProbe = datetime.datetime.utcfromtimestamp(time.time() - args.probeWait)
timeTaken = 0

#TODO: Thread this out into requested number of processes.
#Each thread will need its own sqlite and telnet connection.
for _ in range(args.numProbes):
	target = rand.random()
	
	if args.verbosity > 0:
		print("{0}: Starting probe to {1}.".format(datetime.datetime.now(), target))
	
	tn.write("PROBE: {0}\n".format(target))
	startProbe = datetime.datetime.utcnow()
	raw = tn.read_until(prompt, args.probeTimeout)
	#TODO: What if timeout elapses? Need to skip parsing attempt.
	if args.verbosity > 0:
		print("{0}: Probe finished. Took {1} sec. Saving traces.".format(datetime.datetime.now(), (datetime.datetime.utcnow() - startProbe).seconds))

	if args.verbosity > 2:
		#TODO: Reasonable to start and end block with newlines? Might be misleading for the end.
		print("---Begin raw response---\n{0}\n---End raw response---".format(raw))

	currentTime = datetime.datetime.utcnow()
	
	#Take the right side of "Completed probe request: <target location> -> <closest found location>"
	location = closestGreater.search(raw)
	#if location is not None:
		#print("Closest greater location to target {0} was {1}".format(target, location.group(1)))
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
		
		if args.verbosity > 1:
			print("Trace went through location {0} with UID {1} (previously through UID {2}) with peer locations:\n {3}\nand peer UIDs: \n{4}".format(location, UID, prevUID, peerLocs, peerUIDs))

	#If the minimum wait time between probes has not elapsed, wait that long.
	#TODO: http://twistedmatrix.com/documents/current/api/twisted.internet.task.LoopingCall.html
	timeTaken = (datetime.datetime.utcnow() - startProbe).seconds
	wait = args.probeWait - timeTaken
	if args.verbosity > 0:
		print("{0}: {1} sec since probe. Waiting {2} sec.".format(datetime.datetime.now(), timeTaken, wait))
	if wait > 0:
		time.sleep(wait)
	
	#Commit after parsing and inserting each probe.
	db.commit()

db.close()
