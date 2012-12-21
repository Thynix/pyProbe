import logging

def init_database(db):
	"""
	Initialize the database if it does not already exist. If it already exists and
	is not the latest version, upgrade it.
	"""
	# If there are no tables in this database, it is new, so set up the latest version.
	if db.execute("""SELECT count(*) FROM "sqlite_master" WHERE type == 'table'""").fetchone()[0] == 0:
		create_new(db)
	else:
		# The database has already been set up. Upgrade to the latest version if necessary.
		upgrade(db)

	db.commit()

def create_new(db):
	createVersion4(db)

def createVersion4(db):
	"""
	Create a version 4 database. This is separated to avoid duplication between
	the upgrade from version 3 to 4 and version 4 creation. This is because
	sqlite does not support ALTER COLUMN and so tables must be recreated in order
	to add types.
	"""
	logging.warning("Setting up new database.")
	db.execute("PRAGMA user_version = 4")

	db.execute(""""create table bandwidth(
	                                      time     DATETIME,
	                                      htl      INTEGER,
	                                      KiB      FLOAT,
	                                      duration FLOAT
	                                     )""")
	db.execute("""create index bandwidth_time_index on bandwidth(time)""")

	db.execute("create table build(
	                               time     DATETIME,
	                               htl      INTEGER,
	                               build    INTEGER,
	                               duration FLOAT
	                              )")
	db.execute("create index build_time_index on build(time)")

	db.execute("create table identifier(
	                                    time       DATETIME,
	                                    htl        INTEGER,
	                                    identifier INTEGER,
	                                    percent    INTEGER,
	                                    duration   FLOAT
	                                   )")
	db.execute("create index identifier_time_index on identifier(time)")
	db.execute("create index identifier_identifier_index on identifier(identifier)")

	# link_lengths need not have duration because peer count will have it for
	# all LINK_LENGTHS requests. Storing it on link_lengths would be needless
	# duplication.
	db.execute("create table link_lengths(
	                                      time   DATETIME,
	                                      htl    INTEGER,
	                                      length FLOAT,
	                                      id     INTEGER
	                                     )")
	db.execute("create index link_lengths_time_index on link_lengths(time)")

	db.execute("create table peer_count(
	                                    time     DATETIME,
	                                    htl      INTEGER,
	                                    peers    INTEGER,
	                                    duration FLOAT
	                                   )")
	db.execute("create index peer_count_time_index on peer_count(time)")

	db.execute("create table location(
	                                  time     DATETIME,
	                                  htl      INTEGER,
	                                  location FLOAT,
	                                  duration FLOAT
	                                 )")
	db.execute("create index location_time_index on location(time)")

	db.execute("create table store_size(
	                                    time     DATETIME,
	                                    htl      INTEGER,
	                                    GiB      FLOAT,
	                                    duration FLOAT
	                                   )")
	db.execute("create index store_size_time_index on peer_count(time)")

	db.execute("create table uptime_48h(
	                                    time     DATETIME,
	                                    htl      INTEGER,
	                                    percent  FLOAT,
	                                    duration FLOAT
	                                   )")
	db.execute("create index uptime_48h_time_index on uptime_48h(time)")

	db.execute("create table uptime_7d(
	                                   time     DATETIME,
	                                   htl      INTEGER,
	                                   percent  FLOAT,
	                                   duration FLOAT
	                                  )")
	db.execute("create index uptime_7d_time_index on uptime_7d(time)")

	#Type is included in error and refused to better inform possible
	#estimates of error in probe results.
	db.execute("create table error(time       DATETIME,
	                               htl        INTEGER,
	                               probe_type TEXT,
	                               error_type TEXT,
	                               code       INTEGER,
	                               duration   FLOAT,
	                               local      BOOLEAN
	                              )")
	db.execute("create index error_time_index on error(time)")

	db.execute("create table refused(
	                                 time       DATETIME,
	                                 htl        INTEGER,
	                                 probe_type TEXT,
	                                 duration   FLOAT
	                                )")
	db.execute("create index refused_time_index on refused(time)")

	db.execute("analyze")

def upgrade(db):
	version = db.execute("PRAGMA user_version").fetchone()[0]
	logging.debug("Read database version {0}".format(version))

	def update_version(new):
		db.execute("PRAGMA user_version = {0}".format(new))
		return db.execute("PRAGMA user_version").fetchone()[0]

	# In version 1: Add a response time column "duration" to most tables.
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
	# Add identifier index separate from time index for performance: the covering
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
	# support ALTER COLUMN. Convert timestamps to POSIX time.
	# See https://www.sqlite.org/wal.html
	if version == 3:
		logging.warning("Upgrading from database version 3 to version 4.")

		# TODO: Ensure the table is locked - is BEGIN TRANSACTION neccesary? is the journal change enough to lock it?
		# Begin transaction isn't enough on its own.
		# Enable WAL.
		journal_mode = db.execute("""PRAGMA journal_mode=WAL""").fetchone()[0]
		if journal_mode is not "wal":
			logging.warning("Unable to change journal_mode to Write-Ahead Logging. This will probably mean poor concurrency performance. It is currently '{0}'".format(journal_mode))

		# Rename existing tables so as to not interfere with the new.
		for table in [ "bandwidth", "build", "identifier", "link_lengths", "peer_count",
		               "location", "store_size", "uptime_48h", "uptime_7d", "error", "refused" ]:
			db.execute("""ALTER TABLE {0} RENAME TO {0}-old""".format(table))

		createVersion4(db)

		# TODO: Select everything from each table, insert into new, converting time into POSIX time.
		# TODO: analyze.py also has a function for going from a timestamp in the database to a datetime.

		db.execute("analyze")
		logging.warning("Update from 3 to 4 complete.")
