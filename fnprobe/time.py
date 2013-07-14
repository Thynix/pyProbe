import calendar


def toPosix(dt):
	"""
	Returns the UTC POSIX timestamp for a datetime.
	"""
	return int(calendar.timegm(dt.utctimetuple()))

def totalSeconds(delta):
	# Duration in seconds. Python 2.7 introduced timedelta.total_seconds()
	# but this should run on Python 2.6. (Version in Debian Squeeze.)
	# Seconds per day: 24 hours per day * 60 minutes per hour * 60 seconds per minute = 86400
	# Seconds per microsecond: 1/1000000
	return delta.days * 86400 + delta.seconds + delta.microseconds / 1000000
