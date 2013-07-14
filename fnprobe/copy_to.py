from __future__ import print_function
import argparse
import datetime
from sys import exit, stderr
import os
import db
from psycopg2.tz import LocalTimezone
import update_db

# TODO: up_to_date between here and analyze.py
today = datetime.datetime.now(LocalTimezone()).strftime('%Y-%m-%d %Z')

parser = argparse.ArgumentParser(description='Dumps spans of time from each '
                                             'table.')
parser.add_argument('--up-to', dest='up_to', default=today,
                    help='Dump up to the given date. Defaults to today. '
                         '2013-02-27 EST is February 27th, 2013 midnight EST.')
parser.add_argument('--days', dest='days', type=int, default=7,
                    help='Number of days back to dump. Defaults to 7.')
parser.add_argument('--suffix', dest='suffix', default='week',
                    help='Suffix to add to the end of the filename. Defaults '
                         'to week. An example filename is '
                         '2013-02-27-bandwidth-week.sql')
parser.add_argument('--output-dir', dest='out_dir',
                    default='dumps/',
                    help='Directory to dump into. Defaults to the "dumps/"')
args = parser.parse_args()

try:
    os.mkdir(args.out_dir)
except OSError:
    # Directory already exists, which is fine.
    pass

up_to_date = datetime.datetime.strptime(args.up_to, '%Y-%m-%d %Z')
start_date = up_to_date - datetime.timedelta(days=args.days)

if not args.days > 0:
    print("Days must be positive. {0} is not.".format(args.days))
    exit(1)

database = update_db.main()
cur = database.read.cursor()

for table in database.table_names:
    filename = '{0}/{1}-{2}-{3}.sql'.format(args.out_dir, args.up_to, table,
                                            args.suffix)
    print("Copying '{0}' to '{1}'.".format(table, filename), file=stderr)

    target_file = open(filename, 'w')

    # copy_expert() does not support parameter substitution; do it separately.
    if table == 'link_lengths':
        sql = cur.mogrify("""
            COPY
              (SELECT
                id, length, count_id
              FROM
                (SELECT
                  lengths.id, length, count_id, time
                 FROM
                   "link_lengths" lengths
                 JOIN
                   "peer_count" counts
                 ON
                   counts.id = lengths.count_id) _
              WHERE
                "time" between %(start)s AND %(end)s)
            TO STDOUT""", {'start': start_date, 'end': up_to_date})
        cur.copy_expert(sql, target_file)
    else:
        sql = cur.mogrify("""
            COPY
              (SELECT
                *
              FROM
                "{0}"
              WHERE
                "time" BETWEEN %(start)s AND %(end)s)
            TO STDOUT""".format(table), {'start': start_date,
                                         'end': up_to_date})
        cur.copy_expert(sql, target_file)
