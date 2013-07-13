import logging
from db import update_id_sequence
import update_db
import os

# No need to commit changes - sequence changes are not transactional.
database = update_db.main()
cur = database.maintenance.cursor()

print("""Filenames to copy from are built from a prefix, the table name,
and a suffix. The prefix should consist of an absolute path and the start
of the filename, and the suffix should consist of the end of the filename,
including any file extension. The table name goes between the prefix and the
suffix. If a file does not exist it will be skipped.
""")
prefix = raw_input('Enter prefix: ')
suffix = raw_input('Enter suffix: ')

logging.warning("Dropping indexes to speed import.")
database.drop_indexes()

for table in database.table_names:
    filename = prefix + table + suffix
    if os.path.exists(filename):
        source_file = open(filename)
        logging.info("Copying from %s to %s" % (filename, table))
        cur.copy_from(source_file, table)
        logging.info("Updating id sequence for %s" % table)
        update_id_sequence(cur, table)

logging.warning("Copy complete. Recreating indexes.")
database.create_indexes()
logging.warning("Analyzing.")
cur.execute("ANALYZE")
database.maintenance.commit()
