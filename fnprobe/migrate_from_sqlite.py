import logging
import sqlite3
from psycopg2 import TimestampFromTicks
from datetime import timedelta
import update_db
import signal
import sys

new_database = update_db.main()
Postgres_add = new_database.add.cursor()
Postgres_read = new_database.read.cursor()

# Remove indexes during import for performance.
# See http://www.postgresql.org/docs/current/interactive/populate.html
logging.warning("Dropping indexes to speed import.")
# TODO: Catch exception in case this is a resumed import?
new_database.drop_indexes()

# TODO: Output records / second and see what changes things?

SQLite = sqlite3.connect("database.sql").cursor()


def resume_id(table_name):
    # Find highest ID at which to resume import.
    Postgres_read.execute("""
    SELECT
      max(id)
    FROM
      "{0}"
    """.format(table_name))
    max_id = Postgres_read.fetchone()[0]
    new_database.read.commit()

    if max_id is None:
        # Nothing has been imported yet. Start before the first SQLite record.
        # Assuming no negative ROWIDs have been manually inserted.
        # See https://www.sqlite.org/autoinc.html
        max_id = 0
        # max_id = SQLite.execute("""
        # SELECT
        #   min(ROWID)
        # FROM
        #   "{0}"
        # """.format(table_name)).fetchone()[0] - 1
        logging.info("Starting import for table '{0}' at ROWID {1}".format(
            table_name, max_id))
    else:
        logging.info("Resuming import for table '{0}' at id {1}".format(
            table_name, max_id))

    return max_id


def convert_time(row):
    # Converts row to a list.
    # Assumes: * at least 3 elements
    #          * POSIX timestamp second element
    #          * seconds duration third element
    row = list(row)
    row[1] = TimestampFromTicks(row[1])  # TODO: What time zone? Does it matter?

    # Duration was added later; might be unspecified.
    if row[2] is not None:
        row[2] = timedelta(seconds=row[2])

    return row


def handler(signum, frame):
    logging.warning("Got signal {0}. Committing.".format(signum))
    new_database.add.commit()
    logging.warning("Shutting down.")
    sys.exit(0)

# Commit on interrupt.
signal.signal(signal.SIGINT, handler)
signal.signal(signal.SIGTERM, handler)

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, KiB
    FROM
      bandwidth
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('bandwidth'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      bandwidth(id, time, duration, htl, KiB)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, build
    FROM
      build
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('build'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      build(id, time, duration, htl, build)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, identifier, percent
    FROM
      identifier
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('identifier'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      identifier(id, time, duration, htl, identifier, percent)
    VALUES
      (%s, %s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, peers
    FROM
      peer_count
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('peer_count'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      peer_count(id, time, duration, htl, peers)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

# Link lengths is out of alphabetical order to be after peer_count. It
# references peer_count IDs. Early ids might be broken as 0.
for row in SQLite.execute("""
    SELECT
      ROWID, length, id
    FROM
      link_lengths
    WHERE
      ROWID > ?1 AND id IS NOT 0
    ORDER BY ROWID ASC
    """, (resume_id('link_lengths'),)):

    Postgres_add.execute("""
    INSERT INTO
      link_lengths(id, length, count_id)
    VALUES
      (%s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, location
    FROM
      location
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('location'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      location(id, time, duration, htl, location)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, GiB
    FROM
      store_size
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('store_size'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      store_size(id, time, duration, htl, GiB)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

# reject_stats was missing duration in the SQLite version.
for row in SQLite.execute("""
    SELECT
      ROWID, time, htl, bulk_request_chk, bulk_request_ssk,
      bulk_insert_chk, bulk_insert_ssk
    FROM
      reject_stats
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('reject_stats'),)):

    # No duration column; can't use convert_time.
    row = list(row)
    row[1] = TimestampFromTicks(row[1])

    # duration omitted; will be NULL.
    Postgres_add.execute("""
    INSERT INTO
      reject_stats(id, time, htl, bulk_request_chk, bulk_request_ssk,
      bulk_insert_chk, bulk_insert_ssk)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, percent
    FROM
      uptime_48h
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('uptime_48h'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      uptime_48h(id, time, duration, htl, percent)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, percent
    FROM
      uptime_7d
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('uptime_7d'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      uptime_7d(id, time, duration, htl, percent)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, local, probe_type, error_type, code
    FROM
      error
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('error'),)):

    row = convert_time(row)

    # local was initially not specified.
    if row[4] is not None:
        # Local is 0 or 1; bool() converts 0 to False and 1 to True as desired.
        row[4] = bool(row[4])

    Postgres_add.execute("""
    INSERT INTO
      error(id, time, duration, htl, local, probe_type, error_type, code)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

for row in SQLite.execute("""
    SELECT
      ROWID, time, duration, htl, probe_type
    FROM
      refused
    WHERE
      ROWID > ?1
    ORDER BY ROWID ASC
    """, (resume_id('refused'),)):

    row = convert_time(row)

    Postgres_add.execute("""
    INSERT INTO
      refused(id, time, duration, htl, probe_type)
    VALUES
      (%s, %s, %s, %s, %s)
    """, row)
new_database.add.commit()

logging.warning("Migration complete. Recreating indexes.")
new_database.create_indexes()

logging.warning("Analyzing.")
Postgres_read.execute("""ANALYZE VERBOSE""")
new_database.read.commit()
logging.warning("Done.")
