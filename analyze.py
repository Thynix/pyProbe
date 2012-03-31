import argparse
import sqlite3
import datetime
import re
from subprocess import call
from array import array

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of network size and interconnectedness, generate plots with gnuplot, and optionally upload the results.")
parser.add_argument('-u', dest="upload", default=False,\
                    action="store_true", help="Upload updated analysis. This is not done by default.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
#TODO: graph hour zero should be first probe time; probably should get rid of this.
parser.add_argument('-s', dest="startTime", default=1258866000, type=float,\
                    help="Unix time for plot hour 0. Default 1258866000: 5 AM November 22, 2009")
parser.add_argument('-f', dest="fullData", default="full_data",\
                    help="Path to file to save analysis to. Default \"full_data\"")
parser.add_argument('-T', dest="recentSeconds", default=604800, type=long,\
                    help="A node is considered new if it was first seen after this many seconds in the past. A node is considered former if it was last seen before this many seconds in the past. Default 604800: one week.")
parser.add_argument('--histogram-max', dest="histogramMax", default=50, type=int,\
                    help="Maximum number of peers to consider for histogram generation; anything more than that is lumped into the highest category. Default 100.")
parser.add_argument('-g', dest="graphFile", default="graph.gexf",\
                    help="Path to file to save network graph to. Default \"graph.gexf\".")
parser.add_argument('-q', dest='quiet', default=False, action='store_true',\
                    help='Do not print status updates.')
parser.add_argument('--topology', dest='topology', default=False, action='store_true',\
                    help='Output network topology. Requires libgexf.')

args = parser.parse_args()

def log(msg):
    if not args.quiet:
        print("{0}: {1}".format(datetime.datetime.now(), msg))

log("Connecting to database.")
db = sqlite3.connect(args.databaseFile)

#TODO: Are comments needed? This seems pretty self-explanatory. Is it of concern that
#the 'now' used by sqlite will drift slightly between subsequent lines?

log("Querying database for node appearance data.")
timeSpans = [[0, "-1 hours"], [0, "-1 days"], [0, "-5 days"], [0, "-7 days"], [0, "-15 days"]]
for span in timeSpans:
	#string concatination because sqlite will not substitute paramters in strings.
	span[0] = db.execute("select count(distinct uid) from uids where time > datetime('now',?)", [span[1]]).fetchone()[0]

new = db.execute("select count(firstSeen) from (select min(time) as firstSeen from uids group by uid) where firstSeen > datetime('now','-{0} seconds')".format(args.recentSeconds)).fetchone()[0]

former = db.execute("select count(lastSeen) from (select max(time) as lastSeen from uids group by uid) where lastSeen < datetime('now','-{0} seconds')".format(args.recentSeconds)).fetchone()[0]

oneTime = db.execute("select count(appearances) from (select count(uid) as appearances from uids group by uid) where appearances == 1").fetchone()[0]

delta = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(args.startTime)
hour = long(delta.days * 24 + delta.seconds/3.6e3 + delta.microseconds/3.6e9)

#Hour since stats epoch, nodes seen in: last hour, last day, last five days, last 7 days, last 15 days.
#TODO: Unique and non-unique are actually the same. This seems almost-true in summarize.sh, too, though.
data = "{statHour} {hour} {day} {uniqueDay} {fiveDays} {unique5Days} {week} {uniqueWeek} {fifteenDays} {unique15Days} {fiveDayAvg} {new} {former} {oneTime}".format(statHour=hour, hour=timeSpans[0][0], day=timeSpans[1][0], uniqueDay=timeSpans[1][0], fiveDays=timeSpans[2][0], unique5Days=timeSpans[2][0], week=timeSpans[3][0], uniqueWeek=timeSpans[3][0], fifteenDays=timeSpans[4][0], unique15Days=timeSpans[4][0], fiveDayAvg=timeSpans[2][0]/5, new=new, former=former, oneTime=oneTime)

#Create the file if it doesn't exist so that sed can find it on first run.run:
dataFile = open(args.fullData, 'a')
dataFile.close()

log("Writing appearance data.")

#Remove existing entry(/ies) for this hour and append updated one.
call(['sed','-i', r'/^{0}.*$/d'.format(hour), args.fullData])

with open(args.fullData, 'a') as dataFile:
	dataFile.write("{0}\n".format(data))

log("Plotting network size estimates.")

call(['gnuplot','plot.gnu'])

#Maximum: size one greater to account for zero.
histogram = array('I', (0,)*(args.histogramMax + 1))

log("Querying database for peer distribution histogram.")
probeStats = db.execute("select count(traceNum), count(distinct probeID) from traces group by uid").fetchall()
log("Analyzing results.")

for traceAggregate in probeStats:
        peerUIDs = traceAggregate[0]
        probes = traceAggregate[1]
        if probes > 0:
                avgPeers = peerUIDs/probes
                if avgPeers >= args.histogramMax:
                        histogram[args.histogramMax] += 1
                else:
                        histogram[avgPeers] += 1

log("Writing results.")
with open("peerDist.dat", 'w') as output:
        numberOfPeers = 0
        for nodeCount in histogram:
                output.write("{0} {1}\n".format(numberOfPeers, nodeCount))
                numberOfPeers += 1

log("Plotting histogram.")
call(["gnuplot","peer_dist.gnu"])

if args.topology:
    from libgexf import GEXF, FileWriter
    g = GEXF()
    graph = g.getUndirectedGraph()
    
    log("Querying database for network topology graph.")
    #Vertices: Retrieve all nodes.
    uids = db.execute("select distinct uid from uids").fetchall()
    
    #Edges: Retrieve all nodes there are traces for and which nodes they're connected to.
    nodes = db.execute("select peerUID, uid from traces group by peerUID, uid").fetchall()
    
    log("Adding verticies.")
    #Build vertices.
    #TODO: Might be good to include as attributes things such as how many traces the node
    #is in, its location, when it was last and first seen.
    for vertex in uids:
        graph.addNode(str(vertex[0]))
    
    log("Adding edges.")
    #Build edges.
    i = 0
    for node in nodes:
        #Because results are grouped by peerUID, uid; duplicate edges should not be an issue.
        #TODO: Is there something more useful to use as an edge ID?
        graph.addEdge(str(i), str(node[0]), str(node[1]))
        i += 1
    
    log("Writing graph.")
    writer = FileWriter(args.graphFile, g)
    writer.write()

#Extracts a valid location from an overloaded location value.
#Locations are [0,1), but additional information can be encoded,
#as seen in freenet.node.LocationManager's extractLocs. (Line 1381 as of build 1405.)
#
#If the location is unknown, it will be set to -1 before the backed off encoding.
#If not backed off, it will be subtracted from -1.
#If backed off, it will be added to 1.
#Due to overlap in these values:
#  -1: either not backed off location 0 or an unknown location.
#   0: either location 0 or backed off unknown location.
#the meaning cannot be determined with certainty.
def toLoc(loc):
    loc = float(loc)
    #Not backed off:
    #result = -1 - loc
    #loc = -result - 1
    if loc < 0.0:
        return -loc - 1.0
    if loc >= 1.0:
        return loc - 1.0
    
    return loc

#Link length is difference in location between connected nodes.
log("Querying database for location pairs.")
#Get location, peerLoc pairs for a time-limited period, with one entry for each pair.
links = db.execute("select location, peerLoc from traces join probes on traces.probeID = probes.probeID where time > datetime('now','-{0} seconds') group by location, peerLoc".format(args.recentSeconds)).fetchall()

log("Calculating lengths.")
linkFile = open('links_output', "w")

uniqueLinks = set()
duplicateLinks = 0
for link in links:
    nodeLoc = toLoc(link[0])
    peerLoc = toLoc(link[1])
    diff = abs(nodeLoc - peerLoc)
    distance = min(diff, 1 - diff)
    if distance in uniqueLinks:
        duplicateLinks += 1
    else:
        uniqueLinks.add(distance)

percentage = 0
if len(links) > 0:
    percentage = 1.0*duplicateLinks/len(links)*100

log("From {0} location pairs, {1} ({2}%) had duplicate link lengths."\
    .format(len(links), duplicateLinks, percentage))

log("Writing results.")
#GNUPlot cumulative adds y values, should add to 1.0 in total.
for link in uniqueLinks:
    linkFile.write("{0} {1}\n".format(link, 1.0/len(uniqueLinks)))

linkFile.close()

log("Plotting.")
call(["gnuplot","link_length.gnu"])

log("Closing database.")
db.close()
