import sqlite3
import argparse
import locale
import sys

locale.setlocale(locale.LC_ALL, '')

parser = argparse.ArgumentParser(description="Offer statistics on the amount of information the database holds and expose sqlite3 \"vaccum\" and \"analyze\" operations.")
parser.add_argument('-d, --database-file', dest="databaseFile", default="database.sql",\
                    help="Database file to open, default \"database.sql\"")

args = parser.parse_args()

choice = str(raw_input("Enter:\n * a to analyze\n * s to view statistics\n * v to vaccuum (requires no open transactions or active SQL statements)\n * anything else to exit.\n> "))
with sqlite3.connect(args.databaseFile) as db:
    if choice == 'a':
        print("Analyzing...")
        db.execute("analyze")
        db.commit()
    elif choice == 's':
        tables = [ "error", "refused", "bandwidth", "build", "identifier", "link_lengths", "store_size", "uptime_48h", "uptime_7d" ]
        #Use single quotes for values; double quotes for identifiers.
        print("Database contains:")
        print("* {0:n} distinct UIDs seen.".format(db.execute("""select count(distinct "identifier") from "identifier" """).fetchone()[0]))
        total = 0
        print("* Responses stored:")
        for table in tables:
            count = db.execute("""select count(*) from "{0}" """.format(table)).fetchone()[0]
            print("*     {0}: {1:n}".format(table, count))
            total += count
        print("* {0:n} total probes sent.".format(total))
        print("* Error counts:")
        for error in db.execute("""select "type", count("type") from "error" group by "type" order by "type" """).fetchall():
            print("*     {0}: {1:n}".format(error[0], error[1]))

        def times(func):
            results = []
            for table in tables:
                results.append(db.execute("""select {0}("time") from "{1}" """.format(func, table)).fetchone()[0])
            #None evaluates to False; remove None.
            return filter(None, results)

        print("* First response written {0}".format(min(times("min"))))
        print("* Latest response written {0}".format(max(times("max"))))
    elif choice == 'v':
        print("Vacuuming...")
        db.execute("vacuum")
        db.commit()

    print("Done.")
