import logging
from enum import Enum
import psycopg2

# Current mapping between probe and error types. Used for storage (probe) and
# analysis. (analyze)
probeTypes = Enum('BANDWIDTH', 'BUILD', 'IDENTIFIER', 'LINK_LENGTHS',
                  'LOCATION', 'STORE_SIZE', 'UPTIME_48H',
                  'UPTIME_7D', 'REJECT_STATS')
errorTypes = Enum('DISCONNECTED', 'OVERLOAD', 'TIMEOUT', 'UNKNOWN',
                  'UNRECOGNIZED_TYPE', 'CANNOT_FORWARD')


# Changes made to sequences are not transactional, no need to commit after.
# See http://www.postgresql.org/docs/current/static/functions-sequence.html
# Apparently without PostgreSQL extensions is awful.
#
# Via RhodiumToad in Freenode #postgresql:
# "trust me, you don't want to see the standards-compliant way. in practice
# every db does sequences and automated generation of surrogate keys
# differently. if any db actually supports the standard way I haven't seen it
# yet. probably only DB2 does so, since that's where the spec gets most of its
# features from."
def update_id_sequence(cur, table_name):
    """
    Update the sequence behind the "id" column of the specified table.

    It will start above the maximum current value, which takes into account
    newly inserted values. This is relevant to manually inserting records,
    which avoids updating the sequence.
    """
    cur.execute("""
    SELECT
      setval(
        pg_get_serial_sequence(%(table)s,'id'),
        max("id"))
    FROM
      "{0}"
    """.format(table_name), {'table': table_name})


class Database:
    """Handles database connection, initialization, and analysis queries."""

    def __init__(self, config):
        """
        Initialize the database if it does not already exist. If it already
        exists and is not the latest version, upgrade it.

        Exposes maintenance, record addition, and reading connections as
        maintenance, add, and read respectively.

        :type config: dict contains at least database, maintenance_user,
        read_user, add_user.

        maintenance_pass, read_pass, and add_pass are also recognized. Other
        parameters are passed to the database as keyword arguments.
        """

        auth = {}
        # Move manually used parameters into expected config so they are not
        # specified again as additional keyword arguments. Passwords need not
        # be specified as there are methods of authentication that do not use
        # them.

        # Mandatory configuration.
        for parameter in ['maintenance_user', 'read_user', 'add_user']:
            auth[parameter] = config[parameter]
            del config[parameter]

        # Optional configuration.
        for parameter in ['maintenance_pass', 'read_pass', 'add_pass']:
            auth[parameter] = config.get(parameter)
            if parameter in config:
                del config[parameter]

        self.maintenance = psycopg2.connect(user=auth['maintenance_user'],
                                            password=auth['maintenance_pass'],
                                            **config)
        self.read = psycopg2.connect(user=auth['read_user'],
                                     password=auth['read_pass'], **config)
        self.add = psycopg2.connect(user=auth['add_user'],
                                    password=auth['add_pass'], **config)

        # Prevent the read connection from holding open a transaction for
        # long. Another option would be to manually commit after each group
        # of queries.
        self.read.autocommit = True

        cur = self.maintenance.cursor()
        try:
            cur.execute("""
            SELECT
              schema_version
            FROM
              meta""")
            version = cur.fetchone()[0]
            self.maintenance.commit()

            # The database has already been set up. Upgrade to the latest
            # version if necessary.
            logging.info("Found version {0}.".format(version))
            self.upgrade(version, config)

            self.table_names = self.list_tables()
        except psycopg2.ProgrammingError, e:
            logging.debug("Got '{0}' when querying version.".format(e.pgerror))
            # If there are no tables in this database, it is new, so set up the
            # latest version.
            self.maintenance.commit()
            self.create_new()

            self.table_names = self.list_tables(cur)

            # Grant permissions to the newly created tables.
            for table_name in self.table_names:
                self.set_privileges(auth, table_name)

            # PostgreSQL's INSERT RETURNING requires SELECT. This is used in
            # probe.py when inserting peer_count results.
            # http://www.postgresql.org/docs/current/static/sql-insert.html
            cur.execute("""
            GRANT
              SELECT(id)
            ON TABLE
              "peer_count"
            TO
              "{0}"
            """.format(auth['add_user']))

            self.maintenance.commit()

    def set_privileges(self, auth, table_name):
        """
        Sets default privileges for the table:
        * read_user gets SELECT
        * add_user gets INSERT; UPDATE for the "id" sequence.
        """
        cur = self.maintenance.cursor()

        cur.execute("""
        GRANT
          SELECT
        ON TABLE
          "{0}"
        TO
          "{1}"
        """.format(table_name, auth['read_user']))

        cur.execute("""
        GRANT
          INSERT
        ON TABLE
          "{0}"
        TO
          "{1}"
        """.format(table_name, auth['add_user']))

        cur.execute("""
                SELECT
                  pg_get_serial_sequence(%(table)s, 'id')
                """, {'table': table_name})
        sequence = cur.fetchone()[0]
        # sequence is qualified with a schema name and quoting the entire
        # thing makes it invalid.
        cur.execute("""
            GRANT
              UPDATE
            ON SEQUENCE
              {0}
            TO
              "{1}"
            """.format(sequence, auth['add_user']))

        self.maintenance.commit()

    def create_new(self):
        logging.warning("Setting up new tables.")

        cur = self.maintenance.cursor()

        cur.execute("""
        CREATE TABLE
          bandwidth(
                    id       SERIAL PRIMARY KEY,
                    time     TIMESTAMP WITH TIME ZONE NOT NULL,
                    duration INTERVAL NOT NULL,
                    htl      INTEGER NOT NULL,
                    kib      FLOAT NOT NULL
                   )""")

        cur.execute("""
        CREATE TABLE
          build(
                id       SERIAL PRIMARY KEY,
                time     TIMESTAMP WITH TIME ZONE NOT NULL,
                duration INTERVAL NOT NULL,
                htl      INTEGER NOT NULL,
                build    INTEGER NOT NULL
               )""")

        cur.execute("""
        CREATE TABLE
          identifier(
                     id         SERIAL PRIMARY KEY,
                     time       TIMESTAMP WITH TIME ZONE NOT NULL,
                     duration   INTERVAL NOT NULL,
                     htl        INTEGER NOT NULL,
                     identifier BIGINT NOT NULL,
                     percent    INTEGER NOT NULL
                    )""")

        # peer_count is out of alphabetical order here, but it must exist before
        # link_lengths because link_lengths REFERENCES this table.
        cur.execute("""
        CREATE TABLE
          peer_count(
                     id       SERIAL PRIMARY KEY,
                     time     TIMESTAMP WITH TIME ZONE NOT NULL,
                     duration INTERVAL NOT NULL,
                     htl      INTEGER NOT NULL,
                     peers    INTEGER NOT NULL
                    )""")

        # id is BIGSERIAL because there are likely to be a tremendous number
        # of records.
        cur.execute("""
        CREATE TABLE
          link_lengths(
                       id       BIGSERIAL PRIMARY KEY,
                       length   FLOAT NOT NULL,
                       count_id INTEGER REFERENCES peer_count
                                                   ON DELETE CASCADE
                                                   ON UPDATE CASCADE
                                        NOT NULL
                      )""")

        cur.execute("""
        CREATE TABLE
          location(
                   id       SERIAL PRIMARY KEY,
                   time     TIMESTAMP WITH TIME ZONE NOT NULL,
                   duration INTERVAL NOT NULL,
                   htl      INTEGER NOT NULL,
                   location FLOAT NOT NULL
                  )""")

        cur.execute("""
        CREATE TABLE
          store_size(
                     id       SERIAL PRIMARY KEY,
                     time     TIMESTAMP WITH TIME ZONE NOT NULL,
                     duration INTERVAL NOT NULL,
                     htl      INTEGER NOT NULL,
                     gib      FLOAT NOT NULL
                    )""")

        cur.execute("""
        CREATE TABLE
          reject_stats(
                       id               SERIAL PRIMARY KEY,
                       time             TIMESTAMP WITH TIME ZONE NOT NULL,
                       duration         INTERVAL NOT NULL,
                       htl              INTEGER NOT NULL,
                       bulk_request_chk INTEGER NOT NULL,
                       bulk_request_ssk INTEGER NOT NULL,
                       bulk_insert_chk  INTEGER NOT NULL,
                       bulk_insert_ssk  INTEGER NOT NULL
                      )""")

        cur.execute("""CREATE TABLE
          uptime_48h(
                     id       SERIAL PRIMARY KEY,
                     time     TIMESTAMP WITH TIME ZONE NOT NULL,
                     duration INTERVAL NOT NULL,
                     htl      INTEGER NOT NULL,
                     percent  FLOAT NOT NULL
                    )""")

        cur.execute("""
        CREATE TABLE
          uptime_7d(
                    id       SERIAL PRIMARY KEY,
                    time     TIMESTAMP WITH TIME ZONE NOT NULL,
                    duration INTERVAL NOT NULL,
                    htl      INTEGER NOT NULL,
                    percent  FLOAT NOT NULL
                   )""")

        # code can be null if - as is often the case - the error is not due to
        # a peer sending an unrecognized error code.
        cur.execute("""
        CREATE TABLE
          error(
                id         SERIAL PRIMARY KEY,
                time       TIMESTAMP WITH TIME ZONE NOT NULL,
                duration   INTERVAL NOT NULL,
                htl        INTEGER NOT NULL,
                local      BOOLEAN NOT NULL,
                probe_type INTEGER NOT NULL,
                error_type INTEGER NOT NULL,
                code       INTEGER
               )""")

        cur.execute("""CREATE TABLE
          refused(
                  id         SERIAL PRIMARY KEY,
                  time       TIMESTAMP WITH TIME ZONE NOT NULL,
                  duration   INTERVAL NOT NULL,
                  htl        INTEGER NOT NULL,
                  probe_type INTEGER NOT NULL
                 )""")

        cur.execute("""
        CREATE TABLE
          meta(
               schema_version INTEGER NOT NULL
              )""")
        cur.execute("""
        INSERT INTO
          meta(schema_version)
          values(0)""")

        self.maintenance.commit()
        self.create_indexes()
        logging.warning("Table setup complete.")

    def create_indexes(self):
        cur = self.maintenance.cursor()

        cur.execute("""
        CREATE INDEX
          bandwidth_time_index
        ON
          bandwidth(time)""")
        cur.execute("""
        CREATE INDEX
          build_time_index
        ON
          build(time)""")
        cur.execute("""
        CREATE INDEX
          identifier_identifier_time
        ON
          identifier(identifier, time)""")
        cur.execute("""
        CREATE INDEX
          identifier_time_identifier
        ON
          identifier(time, identifier)""")
        cur.execute("""
        CREATE INDEX
          peer_count_time_index
        ON
          peer_count(time)
        """)
        cur.execute("""
        CREATE INDEX
          location_time_index
        ON
          location(time)""")
        cur.execute("""
        CREATE INDEX
          store_size_time_index
        ON
          store_size(time)""")
        cur.execute("""
        CREATE INDEX
          reject_stats_time_index
        ON
          reject_stats(time)""")
        cur.execute("""
        CREATE INDEX
          uptime_48h_time_index
        ON
          uptime_48h(time)""")
        cur.execute("""
        CREATE INDEX
          uptime_7d_time_index
        ON
          uptime_7d(time)""")
        cur.execute("""
        CREATE INDEX
          error_time_index
        ON
          error(time)""")
        cur.execute("""
        CREATE INDEX
          refused_time_index
        ON
          refused(time)""")

        self.maintenance.commit()

    def drop_indexes(self):
        """
        Drops manually added indexes. Does not remove primary key indexes.
        See http://www.postgresql.org/docs/9.2/static/populate.html
        """
        cur = self.maintenance.cursor()

        for index in ['bandwidth_time_index', 'build_time_index',
                      'identifier_identifier_time',
                      'identifier_time_identifier', 'peer_count_time_index',
                      'location_time_index', 'store_size_time_index',
                      'reject_stats_time_index', 'uptime_48h_time_index',
                      'uptime_7d_time_index', 'error_time_index',
                      'refused_time_index']:
            cur.execute("""DROP INDEX IF EXISTS {0}""".format(index))

        self.maintenance.commit()

    def list_tables(self, cur=None):
        """
        Return a list of the names of public tables in the database (excluding
        "meta") in order usable for importing dumps.

        Can take a cursor to use, but defaults to read.
        """
        if not cur:
            cur = self.read.cursor()

        # Ignore meta - it is just a version number. It need not be dumped or
        # hold probe results or be analyzed.
        cur.execute("""
        SELECT
          table_name
        FROM
          information_schema.tables
        WHERE
          table_schema = 'public' AND table_name != 'meta'
        ORDER BY
          table_name
        """)

        # Each element will be a singleton tuple.
        tables = [x[0] for x in cur.fetchall()]

        # peer_count comes after link_lengths alphabetically, but link_lengths
        # REFERENCES peer_count, so peer_count must come first when importing.
        peer_count_index = tables.index('peer_count')
        link_lengths_index = tables.index('link_lengths')

        assert peer_count_index > link_lengths_index

        tables[peer_count_index], tables[link_lengths_index] = \
            tables[link_lengths_index], tables[peer_count_index]

        return tables

    def upgrade(self, version, config):
        # The user names (in config) will be needed to modify permissions as
        # part of upgrades.
        pass

    def earliest_result(self):
        """
        Return the datetime the earliest probe result was stored.
        """
        cur = self.read.cursor()

        overall_earliest = None

        for table in self.table_names:
            if table == 'link_lengths':
                # Link lengths only has time in association with peer_count.
                continue
            cur.execute("""
            SELECT
              min(time)
            FROM
              "{0}"
            """.format(table))
            earliest = cur.fetchone()[0]
            if overall_earliest is None:
                overall_earliest = earliest
            elif earliest is not None and earliest < overall_earliest:
                overall_earliest = earliest

        return overall_earliest

    def intersect_identifier(self, earliest, mid, latest):
        """
        Return a tuple of the number of distinct identifiers appearing in
        between both earliest to mid and mid to latest time spans, followed
        by the overall number of identifiers in the same conditions.
        """
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              COUNT(DISTINCT identifier), COUNT(identifier)
            FROM
              (SELECT
                i1.identifier
               FROM identifier i1
                 JOIN identifier i2
                 USING(identifier)
               WHERE i1.time BETWEEN %(earliest)s AND %(mid)s
                 AND i2.time BETWEEN %(mid)s AND %(latest)s
              ) _
            """, {'earliest': earliest, 'mid': mid,
                  'latest': latest})
        return cur.fetchone()

    def span_identifier(self, start, end):
        """
        Return a tuple of the number of distinct identifiers and the number
        of identifiers outright in the given time span.
        """
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              COUNT(DISTINCT "identifier"), COUNT("identifier")
            FROM
              "identifier"
            WHERE
              time BETWEEN %s AND %s
            """, (start, end))
        return cur.fetchone()

    def span_store_size(self, start, end):
        """
        Return a tuple of the sum of reported store sizes and the number of
        reports in the given time span.
        """
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              sum("gib"), count("gib")
            FROM
              "store_size"
            WHERE
              "time" BETWEEN %s AND %s
            """, (start, end))
        return cur.fetchone()

    def span_refused(self, start, end):
        """Return the number of refused probes in the given time span."""
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              count(*)
            FROM
              "refused"
            WHERE
              "time" BETWEEN %s AND %s
            """, (start, end))
        return cur.fetchone()[0]

    def span_error_count(self, start, end):
        """
        Return a list of tuples of the error type and the number of errors in
        the time span.
        """
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              error_type, count(*)
            FROM
              "error"
            WHERE
              "time" BETWEEN %(start)s AND %(end)s
            GROUP BY
              "error_type"
            """, {'start': start, 'end': end})
        return cur.fetchall()

    def span_locations(self, start, end):
        """Return the distinct locations seen over the given time span."""
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              DISTINCT "location"
            FROM
              "location"
            WHERE
              "time" BETWEEN %s AND %s
            """, (start, end))
        return cur.fetchall()

    def span_peer_count(self, start, end):
        """Return binned peer counts over the time span."""
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              peers, count("peers")
            FROM
              "peer_count"
            WHERE
              "time" BETWEEN %s AND %s
              GROUP BY "peers"
              ORDER BY "peers"
            """, (start, end))
        return cur.fetchall()

    def span_links(self, start, end):
        """Return the list lengths seen over the time span."""
        cur = self.read.cursor()
        cur.execute("""
        SELECT
          "length"
        FROM
          "link_lengths" lengths
        JOIN
          "peer_count" counts
            ON counts.id = lengths.count_id
        WHERE
          "time" BETWEEN %s AND %s
        """, (start, end))
        return cur.fetchall()

    def span_uptimes(self, start, end):
        """Return binned uptimes reported with identifier over the time span."""
        cur = self.read.cursor()
        cur.execute("""
            SELECT
              "percent", count("percent")
            FROM
              "identifier"
            WHERE
              "time" BETWEEN %s AND %s
            GROUP BY "percent"
            ORDER BY "percent"
            """, (start, end))
        return cur.fetchall()

    def span_bulk_rejects(self, queue_type, start, end):
        """Return binned bulk rejection percentages for the given queue type."""
        cur = self.read.cursor()
        # Report of -1 means no data.
        # Note that queue_type could cause injection because of the string
        # formatting operations, but it should be used with elements from a
        # fixed list, and the read connection should have only SELECT
        # privileges.
        cur.execute("""
            SELECT
              {0}, count({0})
            FROM
              "reject_stats"
            WHERE
              "time" BETWEEN %s AND %s
              AND {0} != -1
            GROUP BY {0}
            ORDER BY {0}
            """.format(queue_type), (start, end))
        return cur.fetchall()
