import sqlite3
import argparse

parser = argparse.ArgumentParser(description="Offer statistics on the amount of information the database holds and expose sqlite3 \"vaccum\" and \"analyze\" operations.")
parser.add_argument('-d, --database-file', dest="databaseFile", default="database.sql",\
                    help="Database file to open, default \"database.sql\"")

args = parser.parse_args()

with sqlite3.connect(args.databaseFile) as db:
	print("Database contains:")
	print("* {0} distinct UIDs seen".format(db.execute("select count(distinct uid) from uids").fetchone()[0]))
	print("* {0} distinct UIDs probes have passed through".format(db.execute("select count(distinct uid) from traces").fetchone()[0]))
	print("* {0} probes".format(db.execute("select count(probeID) from probes").fetchone()[0]))
	print("* {0} traces".format(db.execute("select count(traceNum) from traces").fetchone()[0]))

#Don't have the database open while waiting for user input lest it cause other attempt to access it to timeout.
choice = str(raw_input("\nEnter:\n * v to vaccuum (requires no open transactions or active SQL statements)\n * a to analyze\n * anything else to exit.\n> "))
with sqlite3.connect(args.databaseFile):
	if choice == 'v':
		print("Vacuuming...")
		db.execute("vacuum")
		db.commit()
	elif choice == 'a':
		print("Analyzing...")
		db.execute("analyze")
		db.commit()
	
	print("Done.")
