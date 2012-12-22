import calendar
import datetime
import exceptions

def toPosix(dt):
	return int(calendar.timegm(dt.utctimetuple()))

def totalSeconds(delta):
	# Duration in seconds. Python 2.7 introduced timedelta.total_seconds()
	# but this should run on Python 2.6. (Version in Debian Squeeze.)
	# Seconds per day: 24 hours per day * 60 minutes per hour * 60 seconds per minute = 86400
	# Seconds per microsecond: 1/1000000
	return delta.days * 86400 + delta.seconds + delta.microseconds / 1000000

timestampFormat = u"%Y-%m-%d %H:%M:%S.%f"
sqliteTimestampFormat = u"%Y-%m-%d %H:%M:%S"
def timestamp(string):
	"""
	Parses a database-formatted timestamp into a datetime.
	"""
	# Timestamp may or may not specify milliseconds.
	try:
		return datetime.datetime.strptime(string, timestampFormat)
	except exceptions.ValueError:
		return datetime.datetime.strptime(string, sqliteTimestampFormat)

