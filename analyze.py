import argparse
import sqlite3
import datetime
import re
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
parser.add_argument('-T', dest="recentSeconds", default=604800, type=long,\
                    help="A node is considered new if it was first seen after this many seconds in the past. A node is considered former if it was last seen before this many seconds in the past. Default 604800: one week.")

args = parser.parse_args()

db = sqlite3.connect(args.databaseFile)

#TODO: Are comments needed? This seems pretty self-explanatory. Is it of concern that
#the 'now' used by sqlite will drift slightly between subsequent lines?

timeSpans = [[0, "-1 hours"], [0, "-1 days"], [0, "-5 days"], [0, "-7 days"], [0, "-15 days"]]
for span in timeSpans:
	#TODO: When to fetch only distinct?
	#string concatination because sqlite will not substitute paramters in strings.
	#TODO: SQL count()? Doesn't seem supported by sqlite?
	span[0] = len(db.execute("select distinct uid from uids where time > datetime('now',?)", [span[1]]).fetchall())
	#http://piratepad.net/ucUdssLhyE
	#http://www.sqlite.org/lang.html

new = db.execute("select count(firstSeen) from (select min(time) as firstSeen from uids group by uid) where firstSeen > datetime('now','-{0} seconds')".format(args.recentSeconds)).fetchone()[0]

former = db.execute("select count(lastSeen) from (select max(time) as lastSeen from uids group by uid) where lastSeen < datetime('now','-{0} seconds')".format(args.recentSeconds)).fetchone()[0]

oneTime = db.execute("select count(appearances) from (select count(uid) as appearances from uids group by uid) where appearances == 1").fetchone()[0]

db.close()

delta = datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(args.startTime)
hour = long(delta.days * 24 + delta.seconds/3.6e3 + delta.microseconds/3.6e9)

#Hour since stats epoch, nodes seen in: last hour, last day, last five days, last 7 days, last 15 days.
#TODO: Unique and non-unique are actually the same. This seems almost-true in summarize.sh, too, though.
data = "{statHour} {hour} {day} {uniqueDay} {fiveDays} {unique5Days} {week} {uniqueWeek} {fifteenDays} {unique15Days} {fiveDayAvg} {new} {former} {oneTime}".format(statHour=hour, hour=timeSpans[0][0], day=timeSpans[1][0], uniqueDay=timeSpans[1][0], fiveDays=timeSpans[2][0], unique5Days=timeSpans[2][0], week=timeSpans[3][0], uniqueWeek=timeSpans[3][0], fifteenDays=timeSpans[4][0], unique15Days=timeSpans[4][0], fiveDayAvg=timeSpans[2][0]/5, new=new, former=former, oneTime=oneTime)

#Create the file if it doesn't exist so that sed can find it on first run.run:
dataFile = open(args.fullData, 'a')
dataFile.close()

#Remove existing entry(/ies) for this hour and append updated one.
subprocess.call(['sed','-i', r'/^{0}.*$/d'.format(hour), args.fullData])

with open(args.fullData, 'a') as dataFile:
	dataFile.write("{0}\n".format(data))

subprocess.call(['gnuplot','plot.gnu'])
