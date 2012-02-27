import sqlite3

db = sqlite3.connect("database.sql")
rows = db.execute("select distinct uid from uids").fetchall()

print("{0} known UIDs.".format(len(rows)))
#print(rows)

for uid in rows:
	probes = db.execute("select distinct probeID from traces where uid == ?", uid).fetchall()
	peerUIDs = db.execute("select distinct peerUID from traces where uid == ?", uid).fetchall()
	if len(probes) > 0:
		print("UID {0} has been a node along {1} probes, over which it has been seen with {2} distinct peers.".format(uid[0], len(probes), len(peerUIDs)))
	#else:
	#	print("UID {0} has only been seen indirectly.".format(uid[0]))
