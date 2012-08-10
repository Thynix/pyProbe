import sqlite3

# This script recalculates the peer counts by counting the link lengths which
# were saved at the same time. This is not guarenteed to work, because a
# timestamp is not an ID, and exists to recover from a peer count bug.

db = sqlite3.connect("database.sql")

# Check that timestamp works as an identifier.
num_lengths = db.execute(""" select count(distinct "time") from "link_lengths" """).fetchone()[0]
num_counts = db.execute(""" select count(*) from "peer_count" """).fetchone()[0]

if num_lengths != num_counts:
    print("Timestamp does not function as an identifier; cannot recalculate.")
else:
    times = db.execute(""" select time from "peer_count" """).fetchall()

    for time in times:
        time = time[0]
        peers = db.execute(""" select count(*) from "link_lengths" where "time" == '{0}'""".format(time)).fetchone()[0]
        db.execute(""" update "peer_count" set "peers" = {0} where "time" == '{1}'""".format(peers, time))

    db.commit()

db.close()

