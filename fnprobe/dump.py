from __future__ import print_function
import argparse
import datetime
from sys import exit, stderr

import update_db

today = datetime.date.today().strftime('%Y-%m-%d')

parser = argparse.ArgumentParser(description='Dumps spans of time from each '
                                             'table.')
parser.add_argument('--up-to', dest='up_to', default=today,
                    help='Dump up to the given date. Defaults to today. Takes'
                         ' ISO 8601: 2013-02-27 is February 27th, 2013.')
parser.add_argument('--days', dest='days', type=int, default=7,
                    help='Number of days back to dump. Defaults to 7.')
args = parser.parse_args()


up_to_date = datetime.datetime.strptime(args.up_to, '%Y-%m-%d')
start_date = up_to_date - datetime.timedelta(days=args.days)

if not args.days > 0:
    print("Days must be positive. {0} is not.".format(args.days))
    exit(1)

database = update_db.main()

cur = database.read.cursor()

for table in database.table_names:
    print("Copying '{0}'.".format(table), file=stderr)
    cur.execute("""
        COPY
          (SELECT
            *
          FROM
            "{0}"
          WHERE
            "time" BETWEEN %(start)s AND %(end)s)
        TO STDOUT""".format(table), {'start': start_date, 'end': up_to_date})