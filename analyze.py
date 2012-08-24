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

# Period of time to consider samples in a group for an instantaneous estimate.
# Must be a day or less. If it is more than a day the RRDTool 5-year daily
# archive will not be valid.
shortPeriod = datetime.timedelta(hours=1)

# Period of time to consider samples in a group for an effective size estimate.
# The thought is that while nodes may not be online all the time, many will be
# online regularly enough that they still contribute to the network's capacity.
# Despite considering a longer period, it is still made every shortPeriod.
# One week: 24 hours/day * 7 days = 168 hours.
longPeriod = datetime.timedelta(hours=168)

#
# Latest stored identifier result. A time shortPeriod including this time is
# incomplete and will not be computed.
#
latestIdentifier = timestamp(db.execute("""select max("time") from "identifier" """).fetchone()[0])

def toPosix(dt):
    return int(calendar.timegm(dt.utctimetuple()))

def totalSeconds(delta):
    # Duration in seconds. Python 2.7 introduced timedelta.total_seconds()
    # but this should run on Python 2.6. (Version in Debian Squeeze.)
    # Seconds per day: 24 hours per day * 60 minutes per hour * 60 seconds per minute = 86400
    # Seconds per microsecond: 1/1000000
    return delta.days * 86400 + delta.seconds + delta.microseconds / 1000000

try:
    f = open(args.rrd, "r")
    f.close()
except:
    # Database does not exist - create it.
    fromTime = timestamp(db.execute("""select min("time") from "identifier" """).fetchone()[0])
    toTime = fromTime + shortPeriod
    shortPeriodSeconds = int(totalSeconds(shortPeriod))
    log("Creating round robin network size database.")
    rrdtool.create( args.rrd,
                # If the database already exists don't overwrite it.
                '--no-overwrite',
                '--start', str(toPosix(toTime) - 1),
                # Once each hour.
                '--step', '{0}'.format(shortPeriodSeconds),
                # Data source for instantaneous size once each shortPeriod; values greater than zero.
                'DS:instantaneous-size:GAUGE:{0}:0:U'.format(shortPeriodSeconds),
                # Data source for effective size estimate; greater than zero.
                'DS:effective-size:GAUGE:{0}:0:U'.format(shortPeriodSeconds),
                # Lossless for a year of instantanious; longer for effective estimate. No unknowns allowed.
                # (60 * 60 * 24 * 365 = 31536000 seconds per year)
                'RRA:AVERAGE:0:1:{0}'.format(int(31536000/shortPeriodSeconds)),
                # Daily average for five years; longer for effective estimate.
                # (3600 * 24 = 86400 seconds in a day;365 * 5 = 1825 days)
                'RRA:AVERAGE:0:{0}:1825'.format(int(86400/shortPeriodSeconds))
              )

#
# Start computation where the stored values left off, provided there are any.
#
last = rrdtool.last(args.rrd)
fromTime = datetime.datetime.utcfromtimestamp(int(last))
toTime = fromTime + shortPeriod
log("Resuming network size computation for {0}.".format(toTime))


def formula(samples, networkSize):
    return networkSize * (1 - math.e**(-samples/networkSize))

def binarySearch(distinctSamples, samples):
    if math.fabs(samples - distinctSamples) < 3:
        """Not enough information to make an estimate."""
        return float('NaN')
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
# ----Effective size estimate:
# Identifiers that appear in the current long time period in the past, as well as
# the period of the same length farther back.
# ----Instantaneous size estimate:
# Identifiers that appear in the current short time period in the past.
while latestIdentifier > toTime:

    # Start of current effective size estimate period.
    fromTimeEffective = toTime - longPeriod
    # Start of previous effective size estimate period.
    fromTimeEffectivePrevious = toTime - 2*longPeriod

    # Intersect removes duplicates.
    distinctEffectiveSamples = db.execute("""
    select
      count ("identifier")
    from
      (
        select
          "identifier"
        from
          "identifier"
        where
          "time" >= datetime('{0}') and
          "time" <  datetime('{1}')
      intersect
        select
          "identifier"
        from
          "identifier"
        where
          "time" >= datetime('{1}') and
          "time" <  datetime('{2}')
      );
    """.format(fromTimeEffectivePrevious, fromTimeEffective, toTime)).fetchone()[0]

    effectiveSamples = db.execute("""
    select
      count("identifier")
    from
      (
        select
          "identifier" as "previous_identifier"
        from
          "identifier"
        where
          "time" >= datetime('{0}') and
          "time" <  datetime('{1}')
      )
    join
      "identifier"
        on
        "previous_identifier" == "identifier"
      where
        "time" >= datetime('{1}') and
        "time" <  datetime('{2}')
    ;
    """.format(fromTimeEffectivePrevious, fromTimeEffective, toTime)).fetchone()[0]

    effectiveSize = binarySearch(distinctEffectiveSamples, effectiveSamples)

    print("{0}: {1} effective samples | {2} distinct effective samples | {3} estimated effective size"
           .format(toTime, effectiveSamples, distinctEffectiveSamples, effectiveSize))

    # TODO: Add / remove / ignore refusals to provide error bars? More than that needs to be error bars though.
    # TODO: Take into account refuals for error bars.
    distinctInstantaneousSamples = db.execute("""
    select
      count(distinct "identifier")
    from
      "identifier"
    where
      "time" >= datetime('{0}') and
      "time" <  datetime('{1}')
    """.format(fromTime, toTime)).fetchone()[0]
    instantaneousSamples = db.execute("""
    select
      count("identifier")
    from
      "identifier"
    where
      "time" >= datetime('{0}') and
      "time" <  datetime('{1}')
    """.format(fromTime, toTime)).fetchone()[0]

    instantaneousSize = binarySearch(distinctInstantaneousSamples, instantaneousSamples)
    print("{0}: {1} instantaneous samples | {2} distinct instantaneous samples | {3} estimated instantaneous size"
           .format(toTime, instantaneousSamples, distinctInstantaneousSamples, instantaneousSize))

    rrdtool.update( args.rrd,
            '-t', 'instantaneous-size:effective-size',
                    '{0}:{1}:{2}'.format(toPosix(toTime), instantaneousSize, effectiveSize))

    fromTime = toTime
    toTime = fromTime + shortPeriod

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
                'DEF:instantaneous-size=network-size.rrd:instantaneous-size:AVERAGE:step={0}'.format(int(totalSeconds(shortPeriod))),
                'DEF:effective-size=network-size.rrd:effective-size:AVERAGE:step={0}'.format(int(totalSeconds(shortPeriod))),
                'LINE2:instantaneous-size#FF0000:Hourly Instantaneous',
                'LINE2:effective-size#0000FF:Weekly Effective',
                '-v', 'Size Estimate',
                '--right-axis', '1:0',
                '--width', '1200',
                '--height', '300'
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
    # Lambda: get result out of singleton list so it can be sorted as a number.
    for link in sorted(map(lambda link: link[0], links)):
        linkFile.write("{0} {1}\n".format(link, 1.0/len(links)))

log("Plotting.")
call(["gnuplot","link_length.gnu"])

log("Closing database.")
db.close()
