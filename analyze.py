from __future__ import division
import argparse
import datetime
import rrdtool
import math
from ConfigParser import SafeConfigParser
from psycopg2.tz import LocalTimezone
from twistedfcp.protocol import FreenetClientProtocol, Message
from twisted.internet import reactor, protocol
import sys
from string import split, join
import os
import markdown
import logging
import codecs
from fnprobe.time_utils import toPosix, fromPosix, get_midnight, totalSeconds,\
    clamp_to_hour
from fnprobe.gnuplots import plot_link_length, plot_location_dist, plot_peer_count, plot_bulk_reject, reject_types, plot_uptime
from fnprobe.db import Database, errorTypes
import locale

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of peer distribution and network interconnectedness; generate plots.")

# Options.
parser.add_argument('-T', '--recentHours', dest="recentHours", default=24,
                    type=int,
                    help="Number of hours for which a probe is considered "
                         "recent. Used for peer count histogram and link "
                         "lengths. Default 24.")
parser.add_argument('--histogram-max', dest="histogramMax", default=152,
                    type=int,
                    help="Maximum number of peers to consider for histogram "
                         "generation; anything more than that is included in "
                         "the maximum. Default 110.")
parser.add_argument('-q', dest='quiet', default=False, action='store_true',
                    help='Do not print status updates.')
parser.add_argument('--round-robin', dest='rrd', default='size.rrd',
                    help='Path to round robin network and store size database file.')
parser.add_argument('--size-graph', dest='sizeGraph', default='plot_network_size.png',
                    help='Path to the network size graph.')
parser.add_argument('--datastore-graph', dest='datastoreGraph',
                    default='plot_datastore.png',
                    help='Path to the datastore size graph.')
parser.add_argument('--error-refused-graph', dest='errorRefusedGraph', default='plot_error_refused.png',
                    help='Path to the errors and refusals graph.')
parser.add_argument('--uptime-histogram-max', dest="uptimeHistogramMax", default=120, type=int,
                    help='Maximum percentage to include in the uptime histogram. Default 120')
# Default to midnight today in the local timezone. Allow specifying date and
# time zone.
parser.add_argument('--up-to', dest='up_to', default='',
                    help='Analyze up to midnight on the given date. Defaults '
                         'to today. 2013-02-27 is February 27th, '
                         '2013. The time zone used is the local one.')
parser.add_argument('--hourly', dest='hourly', action='store_true',
                    help='Analyze up to the start of the current hour instead'
                         ' of midnight.')

parser.add_argument('--output-dir', dest='outputDir', default='output',
                    help='Path to output directory.')

# Gnuplot Output filenames

parser.add_argument('--locations-filename', dest='locationGraphFile',
                    default='plot_location_dist.png')
parser.add_argument('--peer-count-filename', dest='peerCountGraphFile',
                    default='plot_peer_count.png')
parser.add_argument('--link-length-filename', dest='linkGraphFile',
                    default='plot_link_length.png')
parser.add_argument('--uptime-filename', dest='uptimeGraphFile',
                    default='plot_week_uptime.png')
parser.add_argument('--bulk-reject-filename', dest='bulkRejectFile',
                    default='plot_week_reject.png')

# Which segments of analysis to run.
parser.add_argument('--upload', dest='uploadConfig', default=None,
                    help='Path to the upload configuration file. See upload.conf_sample. No uploading is attempted if this is not specified.')
parser.add_argument('--markdown', dest='markdownFiles', default=None,
                    help='Comma-separated list of markdown files to parse. '
                         'The output filename is the input filename '
                         'appended with ".html".')
parser.add_argument('--rrd', dest='runRRD', default=False, action='store_true',
                    help='If specified updates and renders the RRDTool plots.')

parser.add_argument('--location', dest='runLocation', default=False, action='store_true',
                    help='If specified plots location distribution over the last recency period.')
parser.add_argument('--peer-count', dest='runPeerCount', default=False, action='store_true',
                    help='If specified plots peer count distribution over the last recency period.')
parser.add_argument('--link-lengths', dest='runLinkLengths', default=False, action='store_true',
                    help='If specified plots link length distribution over the last recency period.')
parser.add_argument('--uptime', dest='runUptime', default=False, action='store_true',
                    help='If specified plots uptime distribution over the last recency period.')
parser.add_argument('--bulk-reject', dest='bulkReject', default=False, action='store_true',
                    help='If specified plots bulk reject distribution over the last recency period.')

args = parser.parse_args()

parser = SafeConfigParser()
parser.read("database.config")
config = parser.defaults()

# Set default locale for number formatting.
locale.setlocale(locale.LC_ALL, '')


def log(msg):
    if not args.quiet:
        print("{0}: {1}".format(datetime.datetime.now(), msg))

# Store the time the script started so that all database queries can cover
# the same time span by only including up to this point in time.
# This allows times other than the current one.
# If a time period for RRD includes this start time it is considered
# incomplete and not computed.
if args.hourly:
    startTime = clamp_to_hour(datetime.datetime.now(LocalTimezone()))
else:
    startTime = get_midnight(args.up_to)

recent = startTime - datetime.timedelta(hours=args.recentHours)
log("Analyzing up to %s. Recency boundary is %s." % (startTime, recent))

log("Connecting to database.")
db = Database(config)

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

# The order and length of these must match. It'd be more nested and thus less
# convenient as a list of tuples though. See also the db.errorTypes enum.

# Names can be up to 19 characters.
errorDataSources = ['error-disconnected',   # Error occurrences in the past shortPeriod.
                    'error-overload',       # TODO: This will include both local and remote errors.
                    'error-timeout',        # It may be more informative to treat local and remote separately.
                    'error-unknown',
                    'error-unrecognized',
                    'error-cannot-frwrd'
                    ]

errorPlotNames = ['Disconnected',
                  'Overload',
                  'Timeout',
                  'Unknown Error',
                  'Unrecognized Type',
                  'Cannot Forward'
                  ]

try:
    f = open(args.rrd, "r")
    f.close()
except IOError:
    # Database does not exist - create it.
    #
    # Data cannot be added at the time the database starts, and it should have
    # an entire hour of data before it just like all the rest. As the first
    # entry should be added after the first hour of data, the database should
    # begin a second before one hour after the first data.
    #
    # An entry is computed including the start of the period and excluding the
    # end.
    #
    fromTime = db.earliest_result()

    if not fromTime:
        print("No probe results exist.")
        sys.exit(1)

    toTime = fromTime + shortPeriod
    shortPeriodSeconds = int(totalSeconds(shortPeriod))

    # Start at the beginning of an hour.
    rrdStart = clamp_to_hour(fromTime - datetime.timedelta(seconds=1))
    rrdPOSIXStart = str(toPosix(rrdStart))

    log("Creating round robin network size database starting %s. (POSIX %s)"
        % (rrdStart, rrdPOSIXStart))

    # Generate list of data sources to reduce repetition. All sources contain only values greater than zero.
    datasources = ['DS:{0}:GAUGE:{1}:0:U'.format(name, shortPeriodSeconds) for name in
                   ['instantaneous-size',   # Size estimated over a shortPeriod.
                    'effective-size',       # Effective size estimated over a longPeriod.
                    'datastore-capacity',   # Usable datastore capacity. In bytes so RRDTool can use prefixes.
                    'daily-size',           # Effective size estimated over the past 2 days.
                    'refused'               # Refused, for all probe types.
                    ] + errorDataSources
                   ]

    rrdtool.create(args.rrd,
                   # If the database already exists don't overwrite it.
                   '--no-overwrite',
                   '--start', rrdPOSIXStart,
                   # Once each hour.
                   '--step', '{0}'.format(shortPeriodSeconds),
                   # Lossless for a year of instantaneous; longer for effective estimate. No unknowns allowed.
                   # (60 * 60 * 24 * 365 = 31536000 seconds per year)
                   'RRA:AVERAGE:0:1:{0}'.format(int(31536000/shortPeriodSeconds)),
                   # Daily average for five years; longer for effective estimate.
                   # (3600 * 24 = 86400 seconds in a day;365 * 5 = 1825 days)
                   'RRA:AVERAGE:0:{0}:1825'.format(int(86400/shortPeriodSeconds)),
                   *datasources
                   )

if args.runRRD:
    #
    # Start computation where the stored values left off, if any.
    # If the database is new rrdtool last returns the database start time.
    #
    last = rrdtool.last(args.rrd)
    fromTime = fromPosix(int(last))
    toTime = fromTime + shortPeriod
    log("Resuming network size computation for %s to %s." % (fromTime, toTime))

    def formula(samples, networkSize):
        return networkSize * (1 - math.e**(-samples/networkSize))

    def binarySearch(distinctSamples, samples):
        # TODO: Is 3 reasonable? Seems arbitrary. How to tell better?
        if math.fabs(samples - distinctSamples) < 3:
            # Not enough information to make an estimate.
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

    log("Computing network plot data. In-progress segment is %s. (POSIX %s)" %
        (startTime, toPosix(startTime)))

    #
    # Perform binary search for network size in:
    # (distinct samples) = (network size) * (1 - e^(-1 * (samples)/(network size)))
    # ----Effective size estimate:
    # Identifiers that appear in the current long time period in the past, as well as
    # the period of the same length farther back.
    # ----Instantaneous size estimate:
    # Identifiers that appear in the current short time period in the past.
    while startTime >= toTime:

        # Start of current effective size estimate period.
        fromTimeEffective = toTime - longPeriod
        # Start of previous effective size estimate period.
        fromTimeEffectivePrevious = toTime - 2*longPeriod

        log("Computing %s to %s." % (fromTime, toTime))

        weekEffectiveResult = db.intersect_identifier(fromTimeEffectivePrevious, fromTimeEffective, toTime)

        effectiveSize = binarySearch(weekEffectiveResult[0], weekEffectiveResult[1])

        log("%s samples | %s distinct samples | %s estimated weekly effective"
            " size" % (weekEffectiveResult[1], weekEffectiveResult[0],
                       effectiveSize))

        # Start of current daily effective size estimate period.
        fromTimeDaily = toTime - mediumPeriod
        # Start of previous daily effective size estimate period.
        fromTimeDailyPrevious = toTime - 2*mediumPeriod

        dailyEffectiveResult = db.intersect_identifier(fromTimeDailyPrevious, fromTimeDaily, toTime)

        dailySize = binarySearch(dailyEffectiveResult[0], dailyEffectiveResult[1])

        log("%s samples | %s distinct samples | %s estimated daily effective "
            "size" % (dailyEffectiveResult[1], dailyEffectiveResult[0],
                      dailySize))

        instantaneousResult = db.span_identifier(fromTime, toTime)

        instantaneousSize = binarySearch(instantaneousResult[0], instantaneousResult[1])
        log("%s samples | %s distinct samples | %s estimated instantaneous "
            "size" % (instantaneousResult[1], instantaneousResult[0],
                      instantaneousSize))

        # Past week of datastore sizes.
        meanDatastoreSize = db.span_store_size(fromTimeEffective, toTime)

        # 1073741824 bytes per GiB,
        estimatedDatastore = meanDatastoreSize * effectiveSize * 1073741824

        refused = db.span_refused(fromTime, toTime)

        # Get numbers of each error type. An error type with zero count does
        # not return a row, so list entries must be made manually.
        errors = [0] * len(errorTypes)
        for index, count in db.span_error_count(fromTime, toTime):
            try:
                errors[index] = count
            except IndexError as e:
                print("could not track error with index", index, "and count", count, "in list", errors, "for error types", errorTypes)

        # RRDTool format string to explicitly specify the order of the data sources.
        # The first one is implicitly the time of the sample.
        try:
            rrdtool.update(args.rrd,
                       '-t', 'instantaneous-size:daily-size:effective-size:datastore-capacity:refused:' + join(errorDataSources, ':'),
                       join(map(str, [toPosix(toTime), instantaneousSize, dailySize, effectiveSize, estimatedDatastore, refused] + errors), ':'))
        except rrdtool.error as e:
            log("Failed to update RRD: {0}".format(e))

        fromTime = toTime
        toTime = fromTime + shortPeriod

    # Graph all available information with a 2-pixel red line.
    lastResult = rrdtool.last(args.rrd)

    # Distant colors are not easily confused.
    # See http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.65.2790
    # Should be at least as long as len(sourcesNames) because zip()
    # truncates to the length of the shortest argument.
    colors = [
              '#5B000D',  # Brown
              '#00FFFD',  # Cyan
              '#23A9FF',  # Light blue
              '#FFE800',  # Yellow
              '#08005B',  # Dark blue
              '#FFD0C6',  # Light pink
              '#04FF04',  # Light green
              '#0000FF',  # Blue
              '#004F00',  # Dark green
              '#FF15CD',  # Dark pink
              '#FF0000'   # Red
    ]

    # List for error sources and lines to avoid repetition.
    # Without a manually specified color RRDTool assigns them.
    sourcesNames = zip(errorDataSources + ['refused'],
                       errorPlotNames + ['Refused'],
                       colors)

    refusedAndErrors = ['DEF:{0}={1}:{0}:AVERAGE:step={2}'.format(pair[0], args.rrd, int(totalSeconds(shortPeriod)))
                        for pair in sourcesNames]
    refusedAndErrors += ['AREA:{0}{1}:{2}:STACK'.format(pair[0], pair[2], pair[1])
                         for pair in sourcesNames]

    # Year: 3600 * 24 * 365 = 31536000 seconds
    # Month: 3600 * 24 * 30 = 2592000 seconds
    # Week: 3600 * 24 * 7 = 604800 seconds
    # Period name, start.
    for period in [('decade', lastResult - 31536000 * 10), ('year', lastResult - 31536000), ('month', lastResult - 2592000), ('week', lastResult - 604800)]:
        # Width, height.
        for dimension in [(900, 300), (1200, 400)]:
            rrdtool.graph(args.outputDir + '/{0}_{1}x{2}_{3}'.format(period[0], dimension[0], dimension[1], args.sizeGraph),
                          '--start', str(period[1]),
                          '--end', str(lastResult),
                          # Each data source has a new value each shortPeriod,
                          # even if it involves data over a longer period.
                          'DEF:instantaneous-size={0}:instantaneous-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                          'DEF:daily-size={0}:daily-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                          'DEF:effective-size={0}:effective-size:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                          'LINE2:instantaneous-size#FF0000:Hourly Instantaneous',
                          'LINE2:daily-size#0099FF:Daily Effective',
                          'LINE2:effective-size#0000FF:Weekly Effective',
                          '-v', 'Size Estimate',
                          '--right-axis', '1:0',
                          '--full-size-mode',
                          '--width', str(dimension[0]),
                          '--height', str(dimension[1])
                          )

            rrdtool.graph(args.outputDir + '/{0}_{1}x{2}_{3}'.format(period[0], dimension[0], dimension[1], args.datastoreGraph),
                          '--start', str(period[1]),
                          '--end', str(lastResult),
                          'DEF:datastore-capacity={0}:datastore-capacity:AVERAGE:step={1}'.format(args.rrd, int(totalSeconds(shortPeriod))),
                          'AREA:datastore-capacity#0000FF',
                          '-v', 'Datastore Capacity',
                          '--right-axis', '1:0',
                          '--full-size-mode',
                          '--width', str(dimension[0]),
                          '--height', str(dimension[1])
                          )

            rrdtool.graph(args.outputDir + '/{0}_{1}x{2}_{3}'.format(period[0], dimension[0], dimension[1], args.errorRefusedGraph),
                          '--start', str(period[1]),
                          '--end', str(lastResult),
                          '-v', 'Errors and Refused',
                          '--right-axis', '1:0',
                          '--full-size-mode',
                          '--width', str(dimension[0]),
                          '--height', str(dimension[1]),
                          *refusedAndErrors
                          )

if args.runLocation:
    log("Querying database for locations.")
    locations = db.span_locations(recent, startTime)

    log("Plotting.")
    plot_location_dist(locations,
                       filename=args.outputDir + '/' + args.locationGraphFile)

if args.runPeerCount:
    log("Querying database for peer distribution histogram.")
    rawPeerCounts = db.span_peer_count(recent, startTime)

    log("Plotting.")
    plot_peer_count(rawPeerCounts, args.histogramMax,
                    filename=args.outputDir + '/' + args.peerCountGraphFile)

if args.runLinkLengths:
    log("Querying database for link lengths.")
    links = db.span_links(recent, startTime)

    log("Plotting.")
    plot_link_length(links,
                     filename=args.outputDir + '/' + args.linkGraphFile)

if args.runUptime:
    log("Querying database for uptime reported with identifiers.")
    # Note that the uptime percentage on the identifier probes is an integer.
    uptimes = db.span_uptimes(recent, startTime)

    log("Plotting.")
    plot_uptime(uptimes, args.uptimeHistogramMax,
                filename=args.outputDir + '/' + args.uptimeGraphFile)

if args.bulkReject:
    counts = {}

    for reject_type in reject_types:
        log("Querying database for {0} reports.".format(reject_type))
        counts[reject_type] = db.span_bulk_rejects(reject_type, recent, startTime)

    log("Plotting.")
    plot_bulk_reject(counts,
                     filename=args.outputDir + '/' + args.bulkRejectFile)

# TODO: Instead of always appending ".html", replace an extension if it exists, otherwise append.
# TODO: Different headers for different pages.
header = '<title>Freenet Statistics</title>'
if args.markdownFiles is not None:
    # The Markdown module uses Python logging.
    logging.basicConfig(filename="markdown.log")

    for markdownFile in split(args.markdownFiles, ','):
        with codecs.open(markdownFile, mode='r', encoding='utf-8') as markdownInput:
            with codecs.open(args.outputDir + '/' + markdownFile + '.html',
                             'w', encoding='utf-8') as markdownOutput:

                # NOTE: If the input file is large this will mean lots of memory usage
                # when it is all read into memory. Perhaps if it is a problem one could
                # pass in text which behaves like a string but actually pulls data from
                # the disk as needed.
                body = markdown.markdown(markdownInput.read().format(args),
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
host = defaults['host']
port = int(defaults['port'])
scriptPath = os.path.dirname(os.path.realpath(__file__))


class InsertFCPFactory(protocol.ClientFactory):
    """
    Inserts the site upon connection, then waits for success or failure
    before exiting.
    """
    protocol = FreenetClientProtocol

    def __init__(self):
        self.Identifier = 'Statistics Page Insert {0}'.format(startTime)
        # TODO: Why doesn't twistedfcp use a dictionary for fields?
        self.fields = [
                       ('URI', '{0}/{1}/0/'.format(privkey, path)),
                       ('Identifier', self.Identifier),
                       ('MaxRetries', '-1'),
                       ('Persistence', 'reboot'),
                       ('DefaultName', 'index.html'),
                       ('Filename', os.path.abspath(args.outputDir)),
                       # Send PutFetchable
                       ('Verbosity', 64),
        ]

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
        sys.stderr.write('Identifier collision in insert!')
        self.Done(message)

    def PutFetchable(self, message):
        log("Insert fetchable.")
        print(message.name)
        print(message.args)

    def PutSuccessful(self, message):
        log("Insert complete.")
        self.Done(message)

    def PutFailed(self, message):
        log("Insert failed.")
        self.Done(message)

    def Insert(self, message):
        log("Connected. Sending insert request.")
        self.proto.sendMessage(Message('ClientPutDiskDir', self.fields))

    def buildProtocol(self, addr):
        log("Connecting as {0}.".format(self.Identifier))
        proto = FreenetClientProtocol()
        proto.factory = self
        self.proto = proto

        proto.deferred['NodeHello'].addCallback(self.Insert)
        proto.deferred['PutFetchable'].addCallback(self.PutFetchable)
        proto.deferred['PutSuccessful'].addCallback(self.PutSuccessful)
        proto.deferred['PutFailed'].addCallback(self.PutFailed)

        proto.deferred['ProtocolError'].addCallback(self.ProtocolError)
        proto.deferred['IdentifierCollision'].addCallback(self.IdentifierCollision)

        return proto

reactor.connectTCP(host, port, InsertFCPFactory())
reactor.run()
