import sqlite3
from array import array
from sys import exit

db = sqlite3.connect("database.sql")

print("Database contains:")
print("* {0} distinct UIDs".format(db.execute("select count(distinct uid) from uids").fetchone()[0]))
print("* {0} probes".format(db.execute("select count(probeID) from probes").fetchone()[0]))
print("* {0} traces".format(db.execute("select count(traceNum) from traces").fetchone()[0]))
#print("{0} new nodes.".format(db.execute("select min(time) as mintime from uids group by uid").fetchall()))

uidblah = str(raw_input("h: calculate histogram of number of peers\nv: vaccuum database (requires no open transactions or active SQL statements)\nEnter choice, or anything else to exit >"))

if uidblah == 'v':
	print("Vacuuming")
	db.execute("vacuum")
	#TODO: Any way to have progress bar?
	print("Complete")
	exit(0)
elif uidblah != 'h':
	print("No option recognized; exiting.")
	exit(1)

histogramMax = 100
histogram = array('I')
for _ in range(histogramMax):
	histogram.append(0)

for uid in db.execute("select distinct uid from uids").fetchall():
	probes = db.execute("select count(distinct probeID) from traces where uid == ?", uid).fetchone()[0]
	peerUIDs = db.execute("select count(traceNum) from traces where uid == ?", uid).fetchone()[0]
	if probes > 0:
		avgPeers = peerUIDs/probes
		if avgPeers >= histogramMax:
			histogram[histogramMax - 1] += 1
		else:
			histogram[avgPeers] += 1
		#print("UID {0} has been a node along {1} probes, over which it has been seen with {2} distinct peers.".format(uid[0], len(probes), len(peerUIDs)))
	#else:
	#	print("UID {0} has only been seen indirectly.".format(uid[0]))

print(histogram)
