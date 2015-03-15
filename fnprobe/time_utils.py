import calendar
from datetime import datetime, date, time
from psycopg2.tz import LocalTimezone

# Recall POSIX time is Seconds since midnight UTC 1970-1-1.


def toPosix(dt):
    """
    Return the POSIX timestamp for a datetime.
    """
    ts = int(calendar.timegm(dt.utctimetuple()))

    # Tolerate daylight savings time.
    if dt.timetuple().tm_isdst > 0:
        ts += 3600

    return ts


def fromPosix(posix):
    """
    Return a timezone-aware datetime for a POSIX timestamp.
    """
    return datetime.fromtimestamp(posix, LocalTimezone())


def clamp_to_hour(timestamp):
    """
    Return the datetime set to the start of the hour.
    """
    return timestamp.replace(minute=0, second=0, microsecond=0)


def get_midnight(iso_date=''):
    """
    Return a timezone-aware datetime for midnight on the given date in ISO
    format, (YYYY-MM-DD) or today if iso_date is empty or not given.
    """
    if iso_date:
        try:
            starting_date = date(*[int(num) for num in iso_date.split('-')])
        except ValueError:
            print("Could not parse '%s' as a date. See --help." % iso_date)
            raise
    else:
        starting_date = date.today()

    return datetime.combine(starting_date, time(tzinfo=LocalTimezone()))


def totalSeconds(delta):
    # Duration in seconds. Python 2.7 introduced timedelta.total_seconds()
    # but this should run on Python 2.6. (Version in Debian Squeeze.)
    # Seconds per day: 24 hours per day * 60 minutes per hour * 60 seconds per
    # minute = 86400; seconds per microsecond: 1/1000000
    return delta.days * 86400 + delta.seconds + delta.microseconds / 1000000
