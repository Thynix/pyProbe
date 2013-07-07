from fnprobe.db import list_tables, update_id_sequence
import update_db

# No need to commit changes - sequence changes are not transactional.
database = update_db.main()
cur = database.maintenance.cursor()

for table in list_tables():
    print("Updating %s" % table)
    update_id_sequence(cur, table)