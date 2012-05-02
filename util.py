import sqlite3
import argparse
import locale

locale.setlocale(locale.LC_ALL, '')

parser = argparse.ArgumentParser(description="Offer statistics on the amount of information the database holds and expose sqlite3 \"vaccum\" and \"analyze\" operations.")
parser.add_argument('-d, --database-file', dest="databaseFile", default="database.sql",\
                    help="Database file to open, default \"database.sql\"")

args = parser.parse_args()

choice = str(raw_input("Enter:\n * a to analyze\n * s to view statistics\n * v to vaccuum (requires no open transactions or active SQL statements)\n * anything else to exit.\n> "))
with sqlite3.connect(args.databaseFile) as db:
    if choice == 'v':
        print("Vacuuming...")
        db.execute("vacuum")
        db.commit()
    elif choice == 'a':
        print("Analyzing...")
        db.execute("analyze")
        db.commit()
    elif choice == 's':
        print("Database contains:")
        print("* {0:n} distinct UIDs seen".format(db.execute("select count(distinct uid) from uids").fetchone()[0]))
        print("* {0:n} distinct UIDs probes have passed through".format(db.execute("select count(distinct uid) from traces").fetchone()[0]))
        print("* {0:n} probes".format(db.execute("select count(probeID) from probes").fetchone()[0]))
        print("* {0:n} traces".format(len(db.execute("select uid from traces group by traceNum, probeID").fetchall())))
        #Using uids because it has an index on time, unlike probes
        print("* First trace taken {0}".format(db.execute("select min(time) from uids").fetchone()[0]))
        print("* Most recent trace taken {0}".format(db.execute("select max(time) from uids").fetchone()[0]))
    
    print("Done.")
