import logging

def init_database(db):
	"""
	Initialize the database if it does not already exist. If it already exists and
	is not the latest version, upgrade it.
	"""
	# If there are no tables in this database, it is new, so set up the latest version.
	if db.execute("""SELECT count(*) FROM "sqlite_master" WHERE type == 'table'""").fetchone()[0] == 0:
		logging.warning("Setting up new database.")
		db.execute("PRAGMA user_version = 3")

		db.execute("create table bandwidth(time, htl, KiB, duration)")
		db.execute("create index bandwidth_time_index on bandwidth(time)")

		db.execute("create table build(time, htl, build, duration)")
		db.execute("create index build_time_index on build(time)")

		db.execute("create table identifier(time, htl, identifier, percent, duration)")
		db.execute("create index identifier_time_index on identifier(time)")
		db.execute("create index identifier_identifier_index on identifier(identifier)")

		# link_lengths need not have duration because peer count will have it for
		# all LINK_LENGTHS requests. Storing it on link_lengths would be needless
		# duplication.
		db.execute("create table link_lengths(time, htl, length, id)")
		db.execute("create index link_lengths_time_index on link_lengths(time)")

		db.execute("create table peer_count(time, htl, peers, duration)")
		db.execute("create index peer_count_time_index on peer_count(time)")

		db.execute("create table location(time, htl, location, duration)")
		db.execute("create index location_time_index on location(time)")

		db.execute("create table store_size(time, htl, GiB, duration)")
		db.execute("create index store_size_time_index on peer_count(time)")

		db.execute("create table uptime_48h(time, htl, percent, duration)")
		db.execute("create index uptime_48h_time_index on uptime_48h(time)")

		db.execute("create table uptime_7d(time, htl, percent, duration)")
		db.execute("create index uptime_7d_time_index on uptime_7d(time)")

		#Type is included in error and refused to better inform possible
		#estimates of error in probe results.
		db.execute("create table error(time, htl, probe_type, error_type, code, duration, local)")
		db.execute("create index error_time_index on error(time)")

		db.execute("create table refused(time, htl, probe_type, duration)")
		db.execute("create index refused_time_index on refused(time)")

		db.execute("analyze")
	else:
		# The database has already been set up; check that it is the latest version.

		version = db.execute("PRAGMA user_version").fetchone()[0]
		logging.debug("Read database version {0}".format(version))

		def update_version(new):
			db.execute("PRAGMA user_version = {0}".format(new))
			version = db.execute("PRAGMA user_version").fetchone()[0]

		# In version 1: added a response time column "duration" to most tables.
		if version == 0:
			logging.warning("Upgrading from database version 0 to version 1.")
			version_zero = [ "bandwidth", "build", "identifier", "peer_count",
				         "location", "store_size", "uptime_48h", "uptime_7d", "error", "refused" ]
			# Add the response time column to the relevant version 0 tables.
			for table in version_zero:
				db.execute("""alter table "{0}" add column duration""".format(table))
			update_version(1)
			logging.warning("Upgrade from 0 to 1 complete.")

		# In version 2: Added a "local" column to the error table.
		if version == 1:
			logging.warning("Upgrading from database version 1 to version 2.")
			db.execute("""alter table error add column local""")
			update_version(2)
			logging.warning("Upgrade from 1 to 2 complete.")

		# In version 3: Created time index on each table instead of only bandwidth.
		# Added identifier index separate from time index for performance: the covering
		# index led to very poor performance during normal usage.
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

			update_version(3)
			logging.warning("Update from 2 to 3 complete.")

	db.commit()

