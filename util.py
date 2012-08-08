from __future__ import division
import sqlite3
import argparse
import locale
import sys
from string import upper
from itertools import izip_longest

locale.setlocale(locale.LC_ALL, '')

parser = argparse.ArgumentParser(description="Offer statistics on the amount of information the database holds and expose sqlite3 \"vaccum\" and \"analyze\" operations.")
parser.add_argument('-d, --database-file', dest="databaseFile", default="database.sql",\
                    help="Database file to open, default \"database.sql\"")

args = parser.parse_args()

#If something totals to zero, a subset will of course also be zero.
#In that case, divide by something other than zero to not crash.
def DivSafe(num):
    if num == 0:
        return 1
    else:
        return num

choice = str(raw_input("Enter:\n * a to analyze\n * e to view per-type error breakdown\n * s to view overall statistics\n * v to vaccuum (requires no open transactions or active SQL statements)\n * anything else to exit\n> "))
def times(func, tables):
    results = []
    for table in tables:
        results.append(db.execute("""select {0}("time") from "{1}" """.format(func, table)).fetchone()[0])
    #None evaluates to False; remove None.
    return filter(None, results)

with sqlite3.connect(args.databaseFile) as db:
    if choice == 'a':
        print("Analyzing...")
        db.execute("analyze")
        db.commit()
    elif choice == 'e':
        probe_types = [ "BANDWIDTH", "BUILD", "IDENTIFIER", "LINK_LENGTHS", "LOCATION", "STORE_SIZE", "UPTIME_48H", "UPTIME_7D" ]
        errors = {}
        total_count = 0

        class error_occurences:
            def __init__(self, error_list):
                self.error_list = error_list
                self.count = 0
                for error in self.error_list:
                    self.count += error[1]

        for probe_type in probe_types:
            errors[probe_type] = error_occurences(db.execute("""select "error_type", count(*) from "error" where "probe_type" == '{0}' group by "error_type" """.format(probe_type)).fetchall())
            total_count += errors[probe_type].count

        print("Errors stored: {0:n} total".format(total_count))
        for probe_type in probe_types:
            error = errors[probe_type]
            print(" * {0}: {1:n} ({2:.1f}%)".format(probe_type, error.count, error.count/DivSafe(total_count)*100))
            for error_entry in error.error_list:
                print(" *     {0}: {1:n} ({2:.1f}%)".format(error_entry[0], error_entry[1], error_entry[1]/DivSafe(error.count)*100))

    elif choice == 's':
        tables = [ "bandwidth", "build", "identifier", "link_lengths", "location", "store_size", "uptime_48h", "uptime_7d" ]
        #Use single quotes for values; double quotes for identifiers.
        success = []
        refused = []
        error = []

        for table in tables:
            #link_lengths has one entry for each length, not each result.
            if table == "link_lengths":
                success.append(db.execute("""select count(*) from (select "time" from "link_lengths" group by "id")""").fetchone()[0])
            else:
                success.append(db.execute("""select count(*) from "{0}" """.format(table)).fetchone()[0])

            #NOTE: Assumes probe_type value is uppercase table name.
            refused.append(db.execute("""select count(*) from "refused" where "probe_type" == '{0}' """.format(upper(table))).fetchone()[0])
            error.append(db.execute("""select count(*) from "error" where "probe_type" == '{0}' """.format(upper(table))).fetchone()[0])

        refusals = sum(refused)
        errors = sum(error)
        successes = sum(success)
        total = successes + refusals + errors

        print("Responses stored: {0:n} total, of which {1:n} ({2:.1f}%) are successes".format(total, successes, successes/DivSafe(total)*100))

        for table in zip(tables, success, refused, error):
            responses = table[1] + table[2] + table[3]
            print(" * {0}: {1:n} responses ({2:.1f}%), {3:n} successes ({4:.1f}%)".format(table[0], responses, responses/DivSafe(total)*100, table[1], table[1]/DivSafe(total)*100))
            print("     * Of responses: {0:n} refused ({1:.1f}%), {2:n} error ({3:.1f}%)".format(table[2], table[2]/DivSafe(responses)*100, table[3], table[3]/DivSafe(responses)*100))

            if table[0] == "identifier" or table[0] == "location":
                duplicate = db.execute("""select count(distinct "{0}") from "{0}" """.format(table[0])).fetchone()[0]
                print("     * {0:n} distinct successes ({1:.1f}%)".format(duplicate, duplicate/DivSafe(table[1])*100))

        print("Refusals stored: {0:n} total ({1:.1f}%)".format(refusals, refusals/DivSafe(total)*100))
        for refusal in db.execute("""select "probe_type", count("probe_type") from "refused" group by "probe_type" order by "probe_type" """).fetchall():
            print(" * {0}: {1:n} ({2:.1f}%)".format(refusal[0], refusal[1], refusal[1]/DivSafe(refusals)*100))

        print("Errors stored: {0:n} total ({1:.1f}%)".format(errors, errors/DivSafe(total)*100))
        for error in db.execute("""select "error_type", count("error_type") from "error" group by "error_type" order by "error_type" """).fetchall():
            print(" * {0}: {1:n} ({2:.1f}%)".format(error[0], error[1], error[1]/DivSafe(errors)*100))


        #TODO: This does not consider errors or refusals.
        print("Earliest response written {0}".format(min(times("min", tables))))
        print("Latest response written {0}".format(max(times("max", tables))))
    elif choice == 'v':
        print("Vacuuming...")
        db.execute("vacuum")
        db.commit()
