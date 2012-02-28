import sqlite3

print("Connecting to database.")
with sqlite3.connect("database.sql") as db:

	print("Database contains:")
	print("* {0} distinct UIDs seen".format(db.execute("select count(distinct uid) from uids").fetchone()[0]))
	print("* {0} distinct UIDs probes have passed through".format(db.execute("select count(distinct uid) from traces").fetchone()[0]))
	print("* {0} probes".format(db.execute("select count(probeID) from probes").fetchone()[0]))
	print("* {0} traces".format(db.execute("select count(traceNum) from traces").fetchone()[0]))

	if str(raw_input("Enter 'v' to vaccuum (requires no open transactions or active SQL statements); anything else to exit: ")) == 'v':
		print("Vacuuming...")
		db.execute("vacuum")
		print("Vacuuming complete. Committing...")
		db.commit()
		print("Done.")	
