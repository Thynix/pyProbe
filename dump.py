import sqlite3
from array import array
from sys import exit
from ProgressBar import ProgressBar
from subprocess import call

print("Connecting to database.")
db = sqlite3.connect("database.sql")

print("Database contains:")
numUIDs = db.execute("select count(distinct uid) from uids").fetchone()[0]
print("* {0} distinct UIDs".format(numUIDs))
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

print("Processing {0} unique UIDs.".format(numUIDs))
bar = ProgressBar(0, numUIDs, format='fixed')

for uid in db.execute("select distinct uid from uids").fetchall():
	bar.print_changed()
	probes = db.execute("select count(distinct probeID) from traces where uid == ?", uid).fetchone()[0]
	peerUIDs = db.execute("select count(traceNum) from traces where uid == ?", uid).fetchone()[0]
	if probes > 0:
		avgPeers = peerUIDs/probes
		if avgPeers >= histogramMax:
			histogram[histogramMax - 1] += 1
		else:
			histogram[avgPeers] += 1
	bar.increment_amount()

with open("peerDist.dat", 'w') as output:
	numberOfPeers = 0
	for nodeCount in histogram:
		output.write("{0} {1}\n".format(numberOfPeers, nodeCount))

call(["gnuplot","peer_dist.gnu"])
