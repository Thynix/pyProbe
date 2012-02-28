import sqlite3
from array import array
from sys import exit
from ProgressBar import ProgressBar
from subprocess import call

print("Connecting to database.")
db = sqlite3.connect("database.sql")

print("Database contains:")
print("* {0} distinct UIDs".format(db.execute("select count(distinct uid) from uids").fetchone()[0]))
print("* {0} probes".format(db.execute("select count(probeID) from probes").fetchone()[0]))
print("* {0} traces".format(db.execute("select count(traceNum) from traces").fetchone()[0]))

uidblah = str(raw_input("h: calculate histogram of number of peers\nn: list of UIDs first seen in the last day\nv: vaccuum database (requires no open transactions or active SQL statements)\nEnter choice, or anything else to exit >"))

if uidblah == 'v':
	print("Vacuuming")
	db.execute("vacuum")
	#TODO: Any way to have progress bar?
	print("Complete")
	exit(0)
elif uidblah == 'n':
	numEntries = 0
	print("-----First seen less than a day ago:-----")
	for entry in db.execute("select uid, firstSeen from (select uid, min(time) as firstSeen from uids group by uid) where firstSeen > datetime('now','-1 day')").fetchall():
		print(entry)
		numEntries += 1
	print("---------------------")
	print("Total {0} UIDs".format(numEntries))
	exit(0)
elif uidblah != 'h':
	print("No option recognized; exiting.")
	exit(1)

histogramMax = 100
histogram = array('I')
for _ in range(histogramMax):
	histogram.append(0)

numUIDs = db.execute("select count(distinct uid) from traces").fetchone()[0]
bar = ProgressBar(0, numUIDs)

print("Querying database for traces through {0} distinct UIDs.".format(numUIDs))
probeStats = db.execute("select count(traceNum), count(distinct probeID) from traces group by uid").fetchall() 
print("Analyzing results")

for traceAggregate in probeStats:
	bar.print_changed()
	peerUIDs = traceAggregate[0]
	probes = traceAggregate[1]
	if probes > 0:
		avgPeers = peerUIDs/probes
		if avgPeers >= histogramMax:
			histogram[histogramMax - 1] += 1
		else:
			histogram[avgPeers] += 1
	bar.increment_amount()

#Newline so progress bar doesn't take up part of prompt on exit.
print("")

with open("peerDist.dat", 'w') as output:
	numberOfPeers = 0
	for nodeCount in histogram:
		output.write("{0} {1}\n".format(numberOfPeers, nodeCount))
		numberOfPeers += 1

call(["gnuplot","peer_dist.gnu"])
