from __future__ import division
import argparse
import sqlite3
import datetime
from subprocess import call
import rrdtool
import calendar
import math
import time

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of peer distribution and network interconnectedness; generate plots.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-T', '--recentHours', dest="recentHours", default=168, type=int,\
                    help="Number of hours for which a probe is considered recent. Used for peer count histogram and link lengths. Default 168 - one week.")
parser.add_argument('--histogram-max', dest="histogramMax", default=50, type=int,\
                    help="Maximum number of peers to consider for histogram generation; anything more than that is included in the maximum. Default 50.")
parser.add_argument('-q', dest='quiet', default=False, action='store_true',\
                    help='Do not print status updates.')
parser.add_argument('--round-robin', dest='rrd', default='network-size.rrd',
                    help='Path to round robin database file.')
parser.add_argument('--size-graph', dest='sizeGraph', default='network-size.png',
                    help='Path to the network size graph.')

args = parser.parse_args()

def log(msg):
    if not args.quiet:
        print("{0}: {1}".format(datetime.datetime.now(), msg))

recent = datetime.datetime.utcnow() - datetime.timedelta(hours=args.recentHours)
print("Recency boundary is {0}.".format(recent))

log("Connecting to database.")
db = sqlite3.connect(args.databaseFile)

#
# Data cannot be added at the time the database starts, and it should have an
# entire hour of data before it just like all the rest. As the first entry
# should be added after the first hour of data, the database should begin
# a second before one hour after the first data.
#
# An entry is computed from the data over the past hour. Start inclusive; end
# exclusive.
#
timestampFormat = u"%Y-%m-%d %H:%M:%S.%f"
def timestamp(string):
    """
    Parses a database-formatted timestamp into a datetime.
    """
    return datetime.datetime.strptime(string, timestampFormat)

fromTime = timestamp(db.execute("""select min("time") from "identifier" """).fetchone()[0])
day = datetime.timedelta(hours=24)
toTime = fromTime + day

#
# Latest stored identifier result. A time period including this time is
# incomplete and will not be computed.
#
latestIdentifier = timestamp(db.execute("""select max("time") from "identifier" """).fetchone()[0])

def toPosix(dt):
    return int(calendar.timegm(dt.utctimetuple()))

try:
    f = open(args.rrd, "r")
    f.close()
except:
    # Database does not exist - create it.
    log("Creating round robin network size database.")
    rrdtool.create( args.rrd,
                # If the database already exists don't overwrite it.
                '--no-overwrite',
                '--start', str(toPosix(toTime) - 1),
                # Once each day.
                '--step', '86400',
                # Data source once each hour; values greater than zero.
                'DS:size:GAUGE:87400:0:U',
                # Lossless for a year. No unknowns allowed. (TODO: What about hours the node is down?)
                'RRA:AVERAGE:0:1:365',
                # Weekly average for five years. (365 * 5 = 1825 days)
                'RRA:AVERAGE:0:7:1825'
              )

#
# Start computation where the stored values left off, provided there are any.
# If not, computation starts at the first stored identifier.
#
if rrdtool.last(args.rrd) is not None:
    fromTime = datetime.datetime.utcfromtimestamp(int(rrdtool.last(args.rrd)))
    toTime = fromTime + day
    log("Resuming network size computation at {0}. {1}".format(fromTime, toPosix(fromTime)))


def formula(samples, networkSize):
    return networkSize * (1 - math.e**(-samples/networkSize))

def binarySearch(distinctSamples, samples):
    if distinctSamples == 0 or samples == 0:
        return 0
    # Upper and lower are network size guesses.
    lower = distinctSamples
    upper = distinctSamples * 2

    #log("Starting: distinct {0}, samples {1}, lower {2}, upper {3}".format(distinctSamples, samples, lower, upper))

    # Find an upper bound - multiply by two until too large.
    while formula(samples, upper) < distinctSamples:
        upper *= 2

    while True:
        #log("lower {0}, upper {1}".format(lower, upper))
        # Got as close as possible. Lower can be greater than upper with certain
        # values of mid.
        if lower >= upper:
            return lower

        mid = int((upper - lower) / 2) + lower
        current = formula(samples, mid)

        if current < distinctSamples:
            lower = mid + 1
            continue
        elif current > distinctSamples:
            upper = mid - 1
            continue
        else:
            # current == distinctSamples:
            return mid

log("Computing network size estimates. In-progress segement is {0}. ({1})".format(latestIdentifier, toPosix(latestIdentifier)))

#
# Perform binary search for network size in:
# (distinct samples) = (network size) * (1 - e^(-1 * (samples)/(network size)))
#
while latestIdentifier > toTime:
    # TODO: Add / remove / ignore refusals to provide error bars? More than that needs to be error bars though.
    # TODO: Take into account refuals for error bars.
    distinctSamples = db.execute("""select count(distinct "identifier") from "identifier" where "time" >= datetime('{0}') and "time" < datetime('{1}')""".format(fromTime, toTime)).fetchone()[0]
    samples = db.execute("""select count("identifier") from "identifier" where "time" >= datetime('{0}') and "time" < datetime('{1}')""".format(fromTime, toTime)).fetchone()[0]

    if distinctSamples == 0:
        print("Zero distinct samples from {0} to {1}. {2} samples.".format(fromTime, toTime, samples))

    size = binarySearch(distinctSamples, samples)
    print(size)
    rrdtool.update( args.rrd,
                    '{0}:{1}'.format(toPosix(toTime), size))
    #                '{0}:{1}'.format(toPosix(toTime), binarySearch(distinctSamples, samples)))

    fromTime = toTime
    toTime = fromTime + day

# Graph all available information with a 2-pixel red line.
# TODO: RRD isn't starting when intended - querying the database like so
#       will mean that the database will have to maintain the time of the first
#       sample, which is not desirable.
#
start = toPosix(timestamp(db.execute(""" select min("time") from "identifier" """).fetchone()[0]))
end = rrdtool.last(args.rrd)
rrdtool.graph(  args.sizeGraph,
                '--start', str(start),
                '--end', str(end),
                'DEF:size=network-size.rrd:size:AVERAGE',
                'LINE2:size#FF0000',
                '-v', 'Size Estimate'
             )

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
