from __future__ import division
import argparse
import sqlite3
import datetime
from subprocess import call

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of peer distribution and network interconnectedness; generate plots.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-T', '--recentHours', dest="recentHours", default=168, type=int,\
                    help="Number of hours for which a probe is considered recent. Used for peer count histogram and link lengths. Default 168 - one week.")
parser.add_argument('--histogram-max', dest="histogramMax", default=50, type=int,\
                    help="Maximum number of peers to consider for histogram generation; anything more than that is included in the maximum. Default 50.")
parser.add_argument('-q', dest='quiet', default=False, action='store_true',\
                    help='Do not print status updates.')

args = parser.parse_args()

def log(msg):
    if not args.quiet:
        print("{0}: {1}".format(datetime.datetime.now(), msg))

recent = datetime.datetime.utcnow() - datetime.timedelta(hours=args.recentHours)
print("Recency boundary is {0}.".format(recent))

log("Connecting to database.")
db = sqlite3.connect(args.databaseFile)

log("Querying database for network size estimates.")

samples = db.execute("""select count("identifier") from "identifier" where "time" > datetime('{0}')""".format(recent)).fetchone()[0]
nonresponses = db.execute("""select count(*) from "error" where "time" > datetime('{0}') and "probe_type" == 'IDENTIFIER' """.format(recent)).fetchone()[0]
nonresponses += db.execute("""select count(*) from "refused" where "time" > datetime('{0}') and "probe_type" == 'IDENTIFIER' """.format(recent)).fetchone()[0]
duplicates = samples - db.execute("""select count(distinct "identifier") from identifier where "time" > datetime('{0}')""".format(recent)).fetchone()[0]

print("Estimating network size as {0:n} to {1:n}. {2:n} nonresponses.".format( (samples**2 / (2 * duplicates)), ((samples + nonresponses)**2 / (2 * duplicates)), nonresponses ))

log("Querying database for locations.")
locations = db.execute("""select distinct "location" from "location" where "time" > datetime('{0}')""".format(recent)).fetchall()

log("Writing results.")
with open("locations_output", "w") as output:
    for location in locations:
        output.write("{0} {1}\n".format(location[0], 1/len(locations)))

log("Plotting.")
call(["gnuplot","location_dist.gnu"])

log("Querying database for peer distribution histogram.")
rawPeerCounts = db.execute("""select peers, count("peers") from "peer_count" where "time" > datetime('{0}') group by "peers" order by "peers" """.format(recent)).fetchall()

peerCounts = [ 0, ] * (args.histogramMax + 1)

#Database does not return empty entries for unseen peer counts, so fill them in.
for count in rawPeerCounts:
    if count[0] < len(peerCounts):
        peerCounts[count[0]] = count[1]
    else:
        peerCounts[len(peerCounts) - 1] = count[1]

log("Writing results.")
with open("peerDist.dat", 'w') as output:
        totalNodes = sum(peerCounts)
        numberOfPeers = 0
        for nodes in peerCounts:
                output.write("{0} {1}\n".format(numberOfPeers, nodes/totalNodes))
                numberOfPeers += 1

log("Plotting.")
call(["gnuplot","peer_dist.gnu"])

log("Querying database for link lengths.")
#TODO: time-limited period?
links = db.execute("""select "length" from "link_lengths" where "time" > datetime('{0}')""".format(recent)).fetchall()

log("Writing results.")
with open('links_output', "w") as linkFile:
    #GNUPlot cumulative adds y values, should add to 1.0 in total.
    for link in links:
        linkFile.write("{0} {1}\n".format(link[0], 1.0/len(links)))

log("Plotting.")
call(["gnuplot","link_length.gnu"])

log("Closing database.")
db.close()
