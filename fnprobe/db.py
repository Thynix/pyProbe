import logging
from fnprobe.time import toPosix, timestamp
from enum import Enum
import sqlite3
import string

# Current mapping between probe and error types. Used for storage (probe) and
# analysis. (analyze)
probeTypes = Enum('BANDWIDTH', 'BUILD', 'IDENTIFIER', 'LINK_LENGTHS',
                  'LOCATION', 'STORE_SIZE', 'UPTIME_48H',
                  'UPTIME_7D', 'REJECT_STATS')
errorTypes = Enum('DISCONNECTED', 'OVERLOAD', 'TIMEOUT', 'UNKNOWN',
                  'UNRECOGNIZED_TYPE', 'CANNOT_FORWARD')

def stringToPosix(string):
    """
    Converts a database timestamp string to a POSIX timestamp.
    """
    return toPosix(timestamp(string))


class Database:
    """Handles database initialization and various queries."""

    def __init__(self, filename):
        """
        Initialize the database if it does not already exist. If it already exists and
        is not the latest version, upgrade it.
        """

        self.db = sqlite3.connect(filename)

        # If there are no tables in this database, it is new, so set up the latest version.
        if self.db.execute("""SELECT count(*) FROM "sqlite_master" WHERE type == 'table'""").fetchone()[0] == 0:
            self.create_new()
        else:
            # The database has already been set up. Upgrade to the latest version if necessary.
            self.upgrade()

    # TODO: Is there something preferable to expose .rollback(), .cursor(), .execute(), ect?
    def get_connection(self):
        return self.db

    def create_new(self):
        logging.warning("Setting up new database.")
        db = self.db
        db.execute("PRAGMA user_version = 6")

        db.execute("""create table bandwidth(
                                             time     DATETIME,
                                             htl      INTEGER,
                                             KiB      FLOAT,
                                             duration FLOAT
                                            )""")
        db.execute("""create index bandwidth_time_index on bandwidth(time)""")

        db.execute("""create table build(
                                         time     DATETIME,
                                         htl      INTEGER,
                                         build    INTEGER,
                                         duration FLOAT
                                        )""")
        db.execute("""create index build_time_index on build(time)""")

        db.execute("""create table identifier(
                                              time       DATETIME,
                                              htl        INTEGER,
                                              identifier INTEGER,
                                              percent    INTEGER,
                                              duration   FLOAT
                                             )""")
        db.execute("""create index identifier_identifier_time on identifier(identifier, time)""")
        db.execute("""create index identifier_time_identifier on identifier(time, identifier)""")

        # link_lengths need not have duration because peer count will have it for
        # all LINK_LENGTHS requests. Storing it on link_lengths would be needless
        # duplication.
        db.execute("""create table link_lengths(
                                                time   DATETIME,
                                                htl    INTEGER,
                                                length FLOAT,
                                                id     INTEGER
                                               )""")
        db.execute("""create index link_lengths_time_index on link_lengths(time)""")

        db.execute("""create table peer_count(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              peers    INTEGER,
                                              duration FLOAT
                                             )""")
        db.execute("""create index peer_count_time_index on peer_count(time)""")

        db.execute("""create table location(
                                            time     DATETIME,
                                            htl      INTEGER,
                                            location FLOAT,
                                            duration FLOAT
                                           )""")
        db.execute("""create index location_time_index on location(time)""")

        db.execute("""create table store_size(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              GiB      FLOAT,
                                              duration FLOAT
                                             )""")
        db.execute("""create index store_size_time_index on store_size(time)""")

        db.execute("""create table reject_stats(
                                                time DATETIME,
                                                htl  INTEGER,
                                                bulk_request_chk INTEGER,
                                                bulk_request_ssk INTEGER,
                                                bulk_insert_chk  INTEGER,
                                                bulk_insert_ssk  INTEGER
                                               )""")
        db.execute("""create index reject_stats_time_index on reject_stats(time)""")

        db.execute("""create table uptime_48h(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              percent  FLOAT,
                                              duration FLOAT
                                             )""")
        db.execute("""create index uptime_48h_time_index on uptime_48h(time)""")

        db.execute("""create table uptime_7d(
                                             time     DATETIME,
                                             htl      INTEGER,
                                             percent  FLOAT,
                                             duration FLOAT
                                            )""")
        db.execute("""create index uptime_7d_time_index on uptime_7d(time)""")

        #Type is included in error and refused to better inform possible
        #estimates of error in probe results.
        db.execute("""create table error(
                                         time       DATETIME,
                                         htl        INTEGER,
                                         probe_type INTEGER,
                                         error_type INTEGER,
                                         code       INTEGER,
                                         duration   FLOAT,
                                         local      BOOLEAN
                                        )""")
        db.execute("""create index error_time_index on error(time)""")

        db.execute("""create table refused(
                                           time       DATETIME,
                                           htl        INTEGER,
                                           probe_type INTEGER,
                                           duration   FLOAT
                                          )""")
        db.execute("""create index refused_time_index on refused(time)""")

        db.execute("analyze")

    def createVersion4(self):
        """
        Create a version 4 database. This is separated to avoid duplication between
        the upgrade from version 3 to 4 and version 4 creation. This is because
        sqlite does not support ALTER COLUMN and so tables must be recreated in order
        to add types.
        """
        logging.warning("Setting up new database.")
        db = self.db
        db.execute("PRAGMA user_version = 4")

        db.execute("""create table bandwidth(
                                             time     DATETIME,
                                             htl      INTEGER,
                                             KiB      FLOAT,
                                             duration FLOAT
                                            )""")
        db.execute("""create index bandwidth_time_index on bandwidth(time)""")

        db.execute("""create table build(
                                         time     DATETIME,
                                         htl      INTEGER,
                                         build    INTEGER,
                                         duration FLOAT
                                        )""")
        db.execute("""create index build_time_index on build(time)""")

        db.execute("""create table identifier(
                                              time       DATETIME,
                                              htl        INTEGER,
                                              identifier INTEGER,
                                              percent    INTEGER,
                                              duration   FLOAT
                                             )""")
        db.execute("""create index identifier_time_index on identifier(time)""")
        db.execute("""create index identifier_identifier_index on identifier(identifier)""")

        # link_lengths need not have duration because peer count will have it for
        # all LINK_LENGTHS requests. Storing it on link_lengths would be needless
        # duplication.
        db.execute("""create table link_lengths(
                                                time   DATETIME,
                                                htl    INTEGER,
                                                length FLOAT,
                                                id     INTEGER
                                               )""")
        db.execute("""create index link_lengths_time_index on link_lengths(time)""")

        db.execute("""create table peer_count(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              peers    INTEGER,
                                              duration FLOAT
                                             )""")
        db.execute("""create index peer_count_time_index on peer_count(time)""")

        db.execute("""create table location(
                                            time     DATETIME,
                                            htl      INTEGER,
                                            location FLOAT,
                                            duration FLOAT
                                           )""")
        db.execute("""create index location_time_index on location(time)""")

        db.execute("""create table store_size(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              GiB      FLOAT,
                                              duration FLOAT
                                             )""")
        db.execute("""create index store_size_time_index on peer_count(time)""")

        db.execute("""create table uptime_48h(
                                              time     DATETIME,
                                              htl      INTEGER,
                                              percent  FLOAT,
                                              duration FLOAT
                                             )""")
        db.execute("""create index uptime_48h_time_index on uptime_48h(time)""")

        db.execute("""create table uptime_7d(
                                             time     DATETIME,
                                             htl      INTEGER,
                                             percent  FLOAT,
                                             duration FLOAT
                                            )""")
        db.execute("""create index uptime_7d_time_index on uptime_7d(time)""")

        #Type is included in error and refused to better inform possible
        #estimates of error in probe results.
        db.execute("""create table error(
                                         time       DATETIME,
                                         htl        INTEGER,
                                         probe_type INTEGER,
                                         error_type INTEGER,
                                         code       INTEGER,
                                         duration   FLOAT,
                                         local      BOOLEAN
                                        )""")
        db.execute("""create index error_time_index on error(time)""")

        db.execute("""create table refused(
                                           time       DATETIME,
                                           htl        INTEGER,
                                           probe_type INTEGER,
                                           duration   FLOAT
                                          )""")
        db.execute("""create index refused_time_index on refused(time)""")

        db.execute("analyze")

    def upgrade(self):
        db = self.db
        version = db.execute("PRAGMA user_version").fetchone()[0]
        logging.debug("Read database version {0}".format(version))

        def update_version(new):
            db.execute("PRAGMA user_version = {0}".format(new))
            return db.execute("PRAGMA user_version").fetchone()[0]

        # In version 1: add a response time column "duration" to most tables.
        if version == 0:
            logging.warning("Upgrading from database version 0 to version 1.")
            version_zero = [ "bandwidth", "build", "identifier", "peer_count",
                         "location", "store_size", "uptime_48h", "uptime_7d", "error", "refused" ]
            # Add the response time column to the relevant version 0 tables.
            for table in version_zero:
                db.execute("""alter table "{0}" add column duration""".format(table))
            version = update_version(1)
            logging.warning("Upgrade from 0 to 1 complete.")

        # In version 2: Add a "local" column to the error table.
        if version == 1:
            logging.warning("Upgrading from database version 1 to version 2.")
            db.execute("""alter table error add column local""")
            version = update_version(2)
            logging.warning("Upgrade from 1 to 2 complete.")

        # In version 3: Create time index on each table instead of only bandwidth.
        # Adde identifier index separate from time index for performance: the covering
        # index leads to very poor performance during normal usage.
        if version == 2:
            logging.warning("Upgrading from database version 2 to version 3.")
            # Remove old index.
            db.execute("""drop index time_index""")

            # Create new indexes.
            db.execute("create index bandwidth_time_index on bandwidth(time)")
            db.execute("create index build_time_index on build(time)")
            db.execute("create index identifier_time_index on identifier(time)")
            db.execute("create index identifier_identifier_index on identifier(identifier)")
            db.execute("create index link_lengths_time_index on link_lengths(time)")
            db.execute("create index peer_count_time_index on peer_count(time)")
            db.execute("create index location_time_index on location(time)")
            db.execute("create index store_size_time_index on peer_count(time)")
            db.execute("create index uptime_48h_time_index on uptime_48h(time)")
            db.execute("create index uptime_7d_time_index on uptime_7d(time)")
            db.execute("create index error_time_index on error(time)")
            db.execute("create index refused_time_index on refused(time)")

            # Analyze so that the optimizer is aware of the indexes.
            db.execute("analyze")

            version = update_version(3)
            logging.warning("Update from 2 to 3 complete.")

        # In version 4: Use WAL so that "readers do not block writers and a writer does
        # not block readers." Recreate database with column datatypes - sqlite does not
        # support ALTER COLUMN. Convert timestamps to POSIX time. Store probe and error
        # types as integer codes.
        # See https://www.sqlite.org/wal.html https://www.sqlite.org/datatype3.html
        if version == 3:
            logging.warning("Upgrading from database version 3 to version 4.")

            # Lock the database. If other writes occur data could be left behind and lost.
            db.execute("""begin immediate transaction""")

            probeTypes = Enum('BANDWIDTH', 'BUILD', 'IDENTIFIER', 'LINK_LENGTHS',
                      'LOCATION', 'STORE_SIZE', 'UPTIME_48H', 'UPTIME_7D',
                      'REJECT_STATS')
            errorTypes = Enum('DISCONNECTED', 'OVERLOAD', 'TIMEOUT', 'UNKNOWN',
                              'UNRECOGNIZED_TYPE', 'CANNOT_FORWARD')

            # Enable WAL.
            journal_mode = db.execute("""pragma journal_mode=wal""").fetchone()[0]
            if journal_mode != "wal":
                logging.warning("Unable to change journal_mode to Write-Ahead Logging. This will probably mean poor concurrency performance. It is currently '{0}'".format(journal_mode))

            tables = [ "bandwidth", "build", "identifier", "link_lengths", "peer_count",
                       "location", "store_size", "uptime_48h", "uptime_7d", "error", "refused" ]
            # Rename existing tables so as to not interfere with the new.
            # Drop existing indexes as they conflict in name with those on the new.
            for table in tables:
                db.execute("""alter table "{0}" rename to "{0}-old" """.format(table))
                db.execute("""drop index "{0}_time_index" """.format(table))
            db.execute("""drop index identifier_identifier_index""")

            # Create version 4 database; set user_version to 4.
            self.createVersion4()

            # Insert everything from the old tables into the new, performing these conversions:
            # * time into POSIX timestamps
            # * probe_type and error_type into numeric codes
            # The sqlite3 module only allows executing single statements, so build a list.
            # {0} stays as such to allow substitutions for each table.
            probeTypeUpdates = []
            errorTypeUpdates = []
            for probeType in probeTypes:
                probeTypeUpdates.append("""update "{0}" set "probe_type" = "{1}" where "probe_type" == "{2}" """.format("{0}", probeType.index, probeType))
            for errorType in errorTypes:
                errorTypeUpdates.append("""update "{0}" set "error_type" = "{1}" where "error_type" == "{2}" """.format("{0}", errorType.index, errorType))

            for table in tables:
                db.execute("""insert into "{0}" select * from "{0}-old" """.format(table))
                db.execute("""update "{0}" set time = strftime('%s', time) """.format(table))
                if table == "error":
                    for update in errorTypeUpdates:
                        db.execute(update.format(table))
                if table == "error" or table == "refused":
                    for update in probeTypeUpdates:
                        db.execute(update.format(table))

            # Drop old tables.
            for table in tables:
                db.execute("""drop table "{0}-old" """.format(table))

            db.execute("vacuum")
            db.execute("analyze")
            version = update_version(4)
            logging.warning("Update from 3 to 4 complete.")

        # In version 5: Add covering indexes for performance on size estimate.
        # Remove some unused indexes.
        # Remove duplicate index and add the one it was intended to be.
        if version == 4:
            logging.warning("Upgrading from database version 4 to version 5.")

            # Covering indexes.
            db.execute("""CREATE INDEX identifier_identifier_time ON identifier(identifier, time)""")
            db.execute("""CREATE INDEX identifier_time_identifier ON identifier(time, identifier)""")

            # Not needed in query on covering indexes.
            db.execute("""DROP INDEX identifier_identifier_index""")
            db.execute("""DROP INDEX identifier_time_index""")

            # Store size time index was accidentally over peer_count
            db.execute("""DROP INDEX store_size_time_index""")
            db.execute("""CREATE INDEX store_size_time_index on store_size(time)""")

            db.execute("analyze")
            version = update_version(5)
            logging.warning("Update from 4 to 5 complete.")

        # In version 6: Add table reject_stats for new probe type REJECT_STATS.
        if version == 5:
            logging.warning("Upgrading from database version 5 to version 6.")

            db.execute("""create table reject_stats(
                                                    time DATETIME,
                                                    htl  INTEGER,
                                                    bulk_request_chk INTEGER,
                                                    bulk_request_ssk INTEGER,
                                                    bulk_insert_chk  INTEGER,
                                                    bulk_insert_ssk  INTEGER
                                                   )""")
            db.execute("""create index reject_stats_time_index on reject_stats(time)""")

            version = update_version(6)
            logging.warning("Update from 5 to 6 complete.")

        # In version 7: Convert probe and error types to integer codes again,
        # this time with a corresponding change to how results are saved.
        # Similarly for the locality boolean.
        if version == 6:
            logging.warning("Upgrading from database version 6 to version 7.")
            probeTypes = Enum('BANDWIDTH', 'BUILD', 'IDENTIFIER', 'LINK_LENGTHS',
                              'LOCATION', 'STORE_SIZE', 'UPTIME_48H',
                              'UPTIME_7D', 'REJECT_STATS')
            errorTypes = Enum('DISCONNECTED', 'OVERLOAD', 'TIMEOUT', 'UNKNOWN',
                              'UNRECOGNIZED_TYPE', 'CANNOT_FORWARD')

            for table in [ "error", "refused" ]:
                for probeType in probeTypes:
                    db.execute("""
                    UPDATE
                      "{0}"
                    SET
                      "probe_type" = ?1
                    WHERE
                      "probe_type" = ?2 """.format(table),
                               (probeType.index, str(probeType)))

            for errorType in errorTypes:
                db.execute("""
                UPDATE
                  "error"
                SET
                  "error_type" = ?1
                WHERE
                  "error_type" = ?2 """, (errorType.index, str(errorType)))

            # Update locality. SQLite does not support booleans apart from
            # integers.
            db.execute("""
            UPDATE
              "error"
            SET
              "local" = 1
            WHERE
              "local" = "true"
            """)
            db.execute("""
            UPDATE
              "error"
            SET
              "local" = 0
            WHERE
              "local" = "false"
            """)

            version = update_version(7)
            logging.warning("Update from 6 to 7 complete.")


    def intersect_identifier(self, earliest, mid, latest):
        """
        Return a tuple of the number of distinct identifiers appearing in
        between both earliest to mid and mid to latest time spans, followed
        by the overall number of identifiers in the same conditions.
        """
        return self.db.execute("""
            SELECT
              COUNT(DISTINCT identifier), COUNT(identifier)
            FROM
              (SELECT
                i1.identifier
               FROM identifier i1
                 JOIN identifier i2
                 USING(identifier)
               WHERE i1.time BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
                 AND i2.time BETWEEN strftime('%s', ?2) AND strftime('%s', ?3)
              )
            """, (earliest, mid, latest)).fetchone()

    def span_identifier(self, start, end):
        """
        Return a tuple of the number of distinct identifiers and the number
        of identifiers outright in the given time span.
        """
        return self.db.execute("""
            SELECT
              COUNT(DISTINCT "identifier"), COUNT("identifier")
            FROM
              "identifier"
            WHERE
              time BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
            """, (start, end)).fetchone()

    def span_store_size(self, start, end):
        """
        Return a tuple of the sum of reported store sizes and the number of
        reports in the given time span.
        """
        return self.db.execute("""
            SELECT
              sum("GiB"), count("GiB")
            FROM
              "store_size"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
            """, (start, end)).fetchone()

    def span_refused(self, start, end):
        """Return the number of refused probes in the given time span."""
        return self.db.execute("""
            SELECT
              count(*)
            FROM
              "refused"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND "time" <  strftime('%s', ?2)
            """, (start, end)).fetchone()[0]

    def span_error_count(self, errorType, start, end):
        """Return the number of errors of the given type in the time span."""
        return self.db.execute("""
            SELECT
              count(*)
            FROM
              "error"
            WHERE
              "error_type" == ?1 AND
              "time" BETWEEN strftime('%s', ?2) AND strftime('%s', ?3)
            """, (errorType, start, end)).fetchone()[0]

    def span_locations(self, start, end):
        """Return the distinct locations seen over the given time span."""
        return self.db.execute("""
            SELECT
              DISTINCT "location"
            FROM
              "location"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
            """, (start, end)).fetchall()

    def span_peer_count(self, start, end):
        """Return binned peer counts over the time span."""
        return self.db.execute("""
            SELECT
              peers, count("peers")
            FROM
              "peer_count"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
              GROUP BY "peers"
              ORDER BY "peers"
            """, (start, end)).fetchall()

    def span_links(self, start, end):
        """Return the list lengths seen over the time span."""
        return self.db.execute("""
        SELECT
          "length"
        FROM
          "link_lengths"
        WHERE
          "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
        """, (start, end)).fetchall()

    def span_uptimes(self, start, end):
        """Return binned uptimes reported with identifier over the time span."""
        return self.db.execute("""
            SELECT
              "percent", count("percent")
            FROM
              "identifier"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
            GROUP BY "percent"
            ORDER BY "percent"
            """, (start, end)).fetchall()

    def span_bulk_rejects(self, queue_type, start, end):
        """Return binned bulk rejection percentages for the given queue type."""
        # Report of -1 means no data.
        return self.db.execute("""
            SELECT
              {0}, count({0})
            FROM
              "reject_stats"
            WHERE
              "time" BETWEEN strftime('%s', ?1) AND strftime('%s', ?2)
              AND {0} IS NOT -1
            GROUP BY {0}
            ORDER BY {0}
            """.format(queue_type), (start, end)).fetchall()