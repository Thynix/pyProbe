import argparse
import sqlite3
import datetime
import re
#import math
import subprocess

parser = argparse.ArgumentParser(description="Analyze probe results for estimates of network size, generate graphs with gnuplot, and optionally upload the results.")
parser.add_argument('-u', dest="upload", default=False,\
                    action="store_true", help="Upload updated analysis. This is not done by default.")
parser.add_argument('-d', dest="databaseFile", default="database.sql",\
                    help="Path to database file. Default \"database.sql\"")
parser.add_argument('-s', dest="startTime", default=1258866000, type=float,\
                    help="Unix time for graph hour 0. Default 1258866000: 5 AM November 22, 2009")
parser.add_argument('-f', dest="fullData", default="full_data",\
                    help="Path to file to save analysis to. Default \"full_data\"")

args = parser.parse_args()

db = sqlite3.connect(args.databaseFile)

#TODO: Are comments needed? This seems pretty self-explanatory. Is it of concern that
#the 'now' used by sqlite will drift slightly between subsequent lines?

timeSpans = [[0, "-1 hours"], [0, "-1 days"], [0, "-5 days"], [0, "-7 days"], [0, "-15 days"]]
for span in timeSpans:
	#TODO: When to fetch only distinct?
	#string concatination because sqlite will not substitute paramters in strings.
	#span[0] = db.execute("select distinct uid from uids where time > datetime('now','-'+?+' days')", [span[1]])
	#TODO: SQL count()?
	span[0] = len(db.execute("select distinct uid from uids where time > datetime('now',?)", [span[1]]).fetchall())
	#TODO: Output hours line to all_data. Should also do summary?
	#$HOURS $PEERS $PEERS5 $PEERS24 $PEERS24_1 $PEERS34 $PEERS34_1 $PEERS72 $PEERS72_1 $SIZE_AVG_24
	#http://piratepad.net/ucUdssLhyE
	#http://www.sqlite.org/lang.html
	#print("Day -", span[1], ":", len(span[0].fetchall()))

db.close()

delta = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(args.startTime)
hour = long(delta.days * 24 + delta.seconds/3.6e3 + delta.microseconds/3.6e9)

#Hour since stats epoch, peers in: last hour, last day, last five days, last 7 days, last 15 days.
data = "{0} {1} {2} {3} {4} {5} {6} {7} {8} {9}".format(hour, timeSpans[0][0], timeSpans[1][0], timeSpans[1][0], timeSpans[2][0], timeSpans[2][0], timeSpans[3][0], timeSpans[3][0], timeSpans[4][0], timeSpans[4][0], timeSpans[2][0]/5)

#Create the file if it doesn't exist so that sed can find it on first run.run:
dataFile = open(args.fullData, 'a')
dataFile.close()

#Remove existing entry(/ies) for this hour and append updated one.
subprocess.call(['sed','-i', r'/^{0}.*$/d'.format(hour), args.fullData])

with open(args.fullData, 'a') as dataFile:
	dataFile.write("{0}\n".format(data))
