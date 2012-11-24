from __future__ import division
import argparse
import sqlite3
import datetime
from subprocess import call
import rrdtool
import calendar
import math
import time
from ConfigParser import SafeConfigParser
from twistedfcp.protocol import FreenetClientProtocol, Message
from twistedfcp import message
from twisted.internet import reactor, protocol
import sys
from string import split
import os
import markdown
import re
import logging
import codecs

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of peer distribution and network interconnectedness; generate plots.")

# Options.
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-T', '--recentHours', dest="recentHours", default=168, type=int,\
                    help="Number of hours for which a probe is considered recent. Used for peer count histogram and link lengths. Default 168 - one week.")
parser.add_argument('--histogram-max', dest="histogramMax", default=50, type=int,\
                    help="Maximum number of peers to consider for histogram generation; anything more than that is included in the maximum. Default 50.")
parser.add_argument('-q', dest='quiet', default=False, action='store_true',\
                    help='Do not print status updates.')
parser.add_argument('--round-robin', dest='rrd', default='size.rrd',
                    help='Path to round robin network and store size database file.')
parser.add_argument('--size-graph', dest='sizeGraph', default='plot_network_size.png',
                    help='Path to the network size graph.')
parser.add_argument('--store-graph', dest='storeGraph', default='plot_store_capacity.png',
                    help='Path to the store capacity graph.')

# Which segments of analysis to run.
parser.add_argument('--upload', dest='uploadConfig', default=None,
                    help='Path to the upload configuration file. See upload.conf_sample. No uploading is attempted if this is not specified.')
parser.add_argument('--markdown', dest='markdownFiles', default=None,
                    help='Comma-separated list of markdown files to parse. Output filenames are the input filename appended with ".html".')
parser.add_argument('--rrd', dest='runRRD', default=False, action='store_true',
                    help='If specified updates and renders the RRDTool plots.')
parser.add_argument('--location', dest='runLocation', default=False, action='store_true',
                    help='If specified plots location distribution over the last recency period.')
parser.add_argument('--peer-count', dest='runPeerCount', default=False, action='store_true',
                    help='If specified plots peer count distribution over the last recency period.')
parser.add_argument('--link-lengths', dest='runLinkLengths', default=False, action='store_true',
                    help='If specified plots link length distribution over the last recency period.')

args = parser.parse_args()

def log(msg):
    if not args.quiet:
        print("{0}: {1}".format(datetime.datetime.now(), msg))

# Store the time the script started so that all database queries can cover
# the same time span by only including up to this point in time.
startTime = datetime.datetime.utcnow()
recent = startTime - datetime.timedelta(hours=args.recentHours)
log("Recency boundary is {0}.".format(recent))

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

# Period of time to consider samples in a group for a short effective
# size estimate.  The thought is that while nodes may not be online
# all the time, many will be online regularly enough that they still
# contribute to the network's capacity.  Despite considering a longer
# period, it is still made every shortPeriod.  One week: 24 hours/day
# * 7 days = 168 hours.
mediumPeriod = datetime.timedelta(hours=24)

# Period of time to consider samples in a group for an effective size estimate.
# The thought is that while nodes may not be online all the time, many will be
# online regularly enough that they still contribute to the network's capacity.
# Despite considering a longer period, it is still made every shortPeriod.
# One week: 24 hours/day * 7 days = 168 hours.
longPeriod = datetime.timedelta(hours=168)

#
# Latest stored identifier result. A shortPeriod including this time is
# incomplete and will not be computed.
#
latestIdentifier = timestamp(db.execute("""select max("time") from "identifier" where "time" < datetime('{0}')""".format(startTime)).fetchone()[0])

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
                'DS:daily-size:GAUGE:{0}:0:U'.format(shortPeriodSeconds),
                # Data source for effective size estimate; greater than zero.
                'DS:effective-size:GAUGE:{0}:0:U'.format(shortPeriodSeconds),
                # Data source for usable store capacity estimate. Size in bytes, so RRDTool can use prefixes. Greater than zero.
                'DS:store-capacity:GAUGE:{0}:0:U'.format(shortPeriodSeconds),
                # Lossless for a year of instantanious; longer for effective estimate. No unknowns allowed.
                # (60 * 60 * 24 * 365 = 31536000 seconds per year)
                'RRA:AVERAGE:0:1:{0}'.format(int(31536000/shortPeriodSeconds)),
                # Daily average for five years; longer for effective estimate.
                # (3600 * 24 = 86400 seconds in a day;365 * 5 = 1825 days)
                'RRA:AVERAGE:0:{0}:1825'.format(int(86400/shortPeriodSeconds))
              )

if args.runRRD:
    #
    # Start computation where the stored values left off, if any.
    # If the database is new rrdtool last returns the database start time.
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
    # latestIdentifier can be up to the start time.
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

        log("{0}: {1} effective samples | {2} distinct effective samples | {3} estimated effective size"
               .format(toTime, effectiveSamples, distinctEffectiveSamples, effectiveSize))

        # Start of current daily effective size estimate period.
        fromTimeDaily = toTime - mediumPeriod
        # Start of previous daily effective size estimate period.
        fromTimeDailyPrevious = toTime - 2*mediumPeriod

        # Intersect removes duplicates.
        distinctDailySamples = db.execute("""
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
        """.format(fromTimeDailyPrevious, fromTimeDaily, toTime)).fetchone()[0]

        dailySamples = db.execute("""
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
        """.format(fromTimeDailyPrevious, fromTimeDaily, toTime)).fetchone()[0]

        dailySize = binarySearch(distinctDailySamples, dailySamples)

        log("{0}: {1} effective samples | {2} distinct effective samples | {3} estimated effective size"
               .format(toTime, dailySamples, distinctDailySamples, dailySize))

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
        log("{0}: {1} instantaneous samples | {2} distinct instantaneous samples | {3} estimated instantaneous size"
               .format(toTime, instantaneousSamples, distinctInstantaneousSamples, instantaneousSize))

        # Past week of datastore sizes.
        sizeResult = db.execute("""
        select
          sum("GiB"), count("GiB")
        from
          "store_size"
        where
          "time" >= datetime('{0}') and
          "time" <  datetime('{1}')
        """.format(fromTimeEffective, toTime)).fetchone()

        storeCapacity = float('nan')
        if sizeResult[1] != 0:
            meanDatastoreSize = sizeResult[0] / sizeResult[1]
            # Half of datastore is store; blocks are doubled for FEC, then each
            # stored ~3 times for redundancy. 1073741824 bytes per GiB, 1/12 of
            # datastore size is store capacity.
            storeCapacity = meanDatastoreSize * effectiveSize * 1073741824 / 12

        rrdtool.update( args.rrd,
                '-t', 'instantaneous-size:daily-size:effective-size:store-capacity',
                '{0}:{1}:{2}:{3}'.format(toPosix(toTime), instantaneousSize, dailySize, effectiveSize, storeCapacity))

        fromTime = toTime
        toTime = fromTime + shortPeriod

    # Graph all available information with a 2-pixel red line.
    # TODO: RRD isn't starting when intended - querying the database like so
    #       will mean that the database will have to maintain the time of the first
    #       sample, which is not desirable.
    #
    firstResult = toPosix(timestamp(db.execute(""" select min("time") from "identifier" """).fetchone()[0]))
    lastResult = rrdtool.last(args.rrd)

    # Month: 3600 * 24 * 30 = 2592000 seconds
    # Week: 3600 * 24 * 7 = 604800 seconds
    # Period name, start.
    for period in [ ('all', firstResult), ('month', lastResult - 2592000), ('week', lastResult - 604800) ]:
        # Width, height.
        for dimension in [ (900, 300), (1200, 400) ]:
            rrdtool.graph(  '{0}_{1}x{2}_{3}'.format(period[0], dimension[0], dimension[1], args.sizeGraph),
                            '--start', str(period[1]),
                            '--end', str(lastResult),
                            'DEF:instantaneous-size={0}:instantaneous-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                            'DEF:daily-size={0}:effective-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(mediumPeriod))),
                            'DEF:effective-size={0}:effective-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                            'LINE2:instantaneous-size#FF0000:Hourly Instantaneous',
                            'LINE2:daily-size#0000FF:Daily Effective',
                            'LINE2:effective-size#0000FF:Weekly Effective',
                            '-v', 'Size Estimate',
                            '--right-axis', '1:0',
                            '--full-size-mode',
                            '--width', str(dimension[0]),
                            '--height', str(dimension[1])
                         )

            rrdtool.graph(  '{0}_{1}x{2}_{3}'.format(period[0], dimension[0], dimension[1], args.storeGraph),
                            '--start', str(period[1]),
                            '--end', str(lastResult),
                            'DEF:store-capacity={0}:store-capacity:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                            'AREA:store-capacity#0000FF',
                            '-v', 'Store Capacity',
                            '--right-axis', '1:0',
                            '--full-size-mode',
                            '--width', str(dimension[0]),
                            '--height', str(dimension[1])
                         )

if args.runLocation:
    log("Querying database for locations.")
    locations = db.execute("""select distinct "location" from "location" where "time" > datetime('{0}') and "time" < datetime('{1}')""".format(recent, startTime)).fetchall()

    log("Writing results.")
    with open("locations_output", "w") as output:
        for location in locations:
            output.write("{0} {1}\n".format(location[0], 1/len(locations)))

    log("Plotting.")
    call(["gnuplot","location_dist.gnu"])

if args.runPeerCount:
    log("Querying database for peer distribution histogram.")
    rawPeerCounts = db.execute("""select peers, count("peers") from "peer_count" where "time" > datetime('{0}') and "time" < datetime('{1}') group by "peers" order by "peers" """.format(recent, startTime)).fetchall()

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
                    output.write("{0} {1:%}\n".format(numberOfPeers, nodes/totalNodes))
                    numberOfPeers += 1

    log("Plotting.")
    call(["gnuplot","peer_count.gnu"])

if args.runLinkLengths:
    log("Querying database for link lengths.")
    links = db.execute("""select "length" from "link_lengths" where "time" > datetime('{0}') and "time" < datetime('{1}')""".format(recent, startTime)).fetchall()

    log("Writing results.")
    with open('links_output', "w") as linkFile:
        #GNUPlot cumulative adds y values, should add to 1.0 in total.
        # Lambda: get result out of singleton list so it can be sorted as a number.
        for link in sorted(map(lambda link: link[0], links)):
            linkFile.write("{0} {1:%}\n".format(link, 1.0/len(links)))

    log("Plotting.")
    call(["gnuplot","link_length.gnu"])

log("Closing database.")
db.close()

# TODO: Instead of always appending ".html", replace an extension if it exists, otherwise append.
# TODO: Different headers for different pages.
header = '<title>Freenet Statistics</title>'
if args.markdownFiles is not None:
    # The Markdown module uses Python logging.
    logging.basicConfig(filename="markdown.log")

    for markdownFile in split(args.markdownFiles, ','):
        with codecs.open(markdownFile, mode='r', encoding='utf-8') as markdownInput:
            with codecs.open(markdownFile + '.html', 'w', encoding='utf-8') as markdownOutput:

                # NOTE: If the input file is large this will mean lots of memory usage
                # when it is all read into memory. Perhaps if it is a problem one could
                # pass in text which behaves like a string but actually pulls data from
                # the disk as needed.
                body = markdown.markdown(markdownInput.read(),
                                  extensions=['generateddate'],
                                  encoding='utf8',
                                  output_format='xhtml1',
                                  # Not using user-supplied content; want image tags with size.
                                  safe=False)

                # Root element and doctype, conforming with XHTML 1.1
                # Via http://www.w3.org/TR/xhtml11/conformance.html#docconf
                markdownOutput.write("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
    "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html version="-//W3C//DTD XHTML 1.1//EN"
      xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.w3.org/1999/xhtml
                          http://www.w3.org/MarkUp/SCHEMA/xhtml11.xsd"
>
""")
                # Header
                markdownOutput.write("<head>" + header + "</head>\n")

                # Content
                markdownOutput.write("<body>" + body + "</body>")

                # Close
                markdownOutput.write("</html>")

if args.uploadConfig is None:
    # Upload config not specified; no further operations needed.
    sys.exit(0)


config = SafeConfigParser()
config.read(args.uploadConfig)
defaults = config.defaults()

privkey = defaults['privkey']
path = defaults['path']
files = split(defaults['insertfiles'], ';')
host = defaults['host']
port = int(defaults['port'])
scriptPath = os.path.dirname(os.path.realpath(__file__))

class InsertFCPFactory(protocol.ClientFactory):
    """
    Upon connection, inserts the requested statistics site, then disconnects
    and ends the program.
    """
    protocol = FreenetClientProtocol

    def __init__(self):
        self.fields = [
                    ('URI', '{0}/{1}/0/'.format(privkey, path)),
                    ('Identifier', 'Statistics Page Insert {0}'.format(startTime)),
                    ('MaxRetries', '-1'),
                    ('Global', 'true'),
                    ('Persistence', 'forever'),
                    ('DefaultName', 'index.html')
                 ]

        fileNum = 0
        for filename in files:
            base = 'Files.{0}'.format(fileNum)
            fileNum += 1

            def attr(field):
                return '{0}.{1}'.format(base, field)

            self.fields.append((attr('Name'), filename))
            self.fields.append((attr('UploadFrom'), 'disk'))
            self.fields.append((attr('Filename'), '{0}/{1}'.format(scriptPath, filename)))

    def Done(self, message):
        print message.name, message.args
        self.proto.sendMessage(Message('Disconnect', []))

    def ProtocolError(self, message):
        sys.stderr.write('Permissions error in insert!')
        sys.stderr.write('Does "Core Settings" > "Directories uploading is allowed from" include all used directories?')
        self.Done(message)

    def clientConnectionLost(self, connection, reason):
        """
        Disconnection complete.
        """
        log("Disconnected.")
        reactor.stop()

    def IdentifierCollision(self, message):
        sys.stderr.write('Error in insert!')
        sys.stderr.write('The previous upload was done the same day as the last.')
        sys.stderr.write('Please remove the upload from the queue.')
        self.Done(message)

    def PutFetchable(self, message):
        log("Insert successful.")
        self.Done(message)

    def Insert(self, message):
        # TODO: Run custom Fred build which prints names of messages as they are received - is the disconnect beind receivied first? Why would disconnecting without a delay lead to the upload not being queued?
        log("Connected. Sending insert request.")
        self.proto.sendMessage(Message('ClientPutComplexDir', self.fields))
        # TODO: What other messages can be used? Perhaps have a do_session() for a timeout?
        self.proto.sendMessage(Message('Disconnect', []))

    def buildProtocol(self, addr):
        log("Connecting.")
        proto = FreenetClientProtocol()
        proto.factory = self
        self.proto = proto

        proto.deferred['NodeHello'].addCallback(self.Insert)
        proto.deferred['PutFetchable'].addCallback(self.PutFetchable)

        proto.deferred['ProtocolError'].addCallback(self.ProtocolError)
        proto.deferred['IdentifierCollision'].addCallback(self.IdentifierCollision)

        return proto

reactor.connectTCP(host, port, InsertFCPFactory())
reactor.run()

