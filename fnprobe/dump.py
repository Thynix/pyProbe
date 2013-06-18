from __future__ import print_function
from ConfigParser import SafeConfigParser
import argparse
import datetime
from sys import exit, stderr
import psycopg2
import db

today = datetime.date.today().strftime('%Y-%m-%d')

parser = argparse.ArgumentParser(description='Dumps spans of time from each '
                                             'table.')
parser.add_argument('--up-to', dest='up_to', default=today,
                    help='Dump up to the given date. Defaults to today. Takes'
                         ' ISO 8601: 2013-02-27 is February 27th, 2013.')
parser.add_argument('--days', dest='days', type=int, default=7,
                    help='Number of days back to dump. Defaults to 7.')
parser.add_argument('--suffix', dest='suffix', default='week',
                    help='Suffix to add to the end of the filename. Defaults '
                         'to week. An example filename is '
                         '2013-02-27-bandwidth-week.sql')
parser.add_argument('--output-dir', dest='out_dir',
                    default='/var/lib/postgresql',
                    help='Directory to dump into. Defaults to '
                         '"/var/lib/postgresql"')
args = parser.parse_args()


up_to_date = datetime.datetime.strptime(args.up_to, '%Y-%m-%d')
start_date = up_to_date - datetime.timedelta(days=args.days)

if not args.days > 0:
    print("Days must be positive. {0} is not.".format(args.days))
    exit(1)

parser = SafeConfigParser()
parser.read("database.config")
config = parser.defaults()

# The database user is the one writing to the file, not this client,
# Cannot meaningfully check for output directory access here. In order to
# COPY TO a file, must connect as super user. (Attempting to COPY TO STDOUT
# causes a segmentation fault,)

cur = psycopg2.connect(database=config['database'], user='postgres').cursor()

for table in db.list_tables(cur):
    # link_lengths does not have a "time" column.
    if table == 'link_lengths':
        continue

    filename = '{0}/{1}-{2}-{3}.sql'.format(args.out_dir, args.up_to, table,
                                            args.suffix)
    print("Copying '{0}' to '{1}'.".format(table, filename), file=stderr)
    cur.execute("""
        COPY
          (SELECT
            *
          FROM
            "{0}"
          WHERE
            "time" BETWEEN %(start)s AND %(end)s)
        TO %(file)s""".format(table), {'start': start_date,
                                       'end': up_to_date, 'file': filename})
