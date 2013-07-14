# pyProbe

pyProbe is a collection of data gathering and analysis tools for [Freenet](https://freenetproject.org/) network probes. These probes report limited sets of information at once and apply random noise in order to reduce how identifiable information is while keeping it useful for network-wide statistics. Requires Freenet build 1409 or greater.

## Requirements

* [Python 2.6 or higher](http://www.python.org/download/releases/2.7.3/)
    * [argparse]() (if using Python earlier than 2.7)
* [Freenet](https://freenetproject.org/)
* [gnuplot](http://www.gnuplot.info/) (for extra analyze.py plots)
* [gnuplot-py](https://pypi.python.org/pypi/gnuplot-py/1.8)
* [rrdtool] (http://oss.oetiker.ch/rrdtool/download.en.html) (rrdpython)
* [Twisted](https://twistedmatrix.com/trac/)
* [twistedfcp](https://github.com/AnIrishDuck/twistedfcp)
* [Markdown](http://packages.python.org/Markdown/index.html)
* [enum](http://pypi.python.org/pypi/enum/0.4.4)
* [postgresql](http://www.postgresql.org/)
* [psycopg](http://initd.org/psycopg/)

## Installation

Freenet, Python, gnuplot, rrdtool, Twisted, and Markdown all have installation instructions on their respective sites.

`pip install markdown enum gnuplot-py psycopg2`

### argparse

* argparse was added to Python in version 2.7. It is available for older versions on the package index: `# pip install argparse`

### twistedfcp

* Clone [twistedfcp](https://github.com/AnIrishDuck/twistedfcp): `$ git clone https://github.com/AnIrishDuck/twistedfcp.git`
* `$ cd twistedfcp`
* `# python setup.py install`

### PostgreSQL

After [installing](http://www.postgresql.org/download/), [create](http://www.postgresql.org/docs/current/interactive/database-roles.html) [roles](http://www.postgresql.org/docs/current/interactive/role-attributes.html). This guide was written using PostgreSQL 9.2 and assumes Debian-ish tendencies. An example package name is `postgresql-9.2`.

pyProbe uses the database in three capacities:

* Table creation, updating, and alteration for database initialization and upgrades.
* Inserting for data gathering.
* Reading for data analysis.

**Please note: I don't know if I'm setting this up in a sane way. If not, please yell at me about it.**

If appropriate roles for these don't already exist, create them. Then create the database and grant sufficient privileges. There are many ways to authenticate; this guide will use [peer authentication](http://www.postgresql.org/docs/current/static/auth-methods.html#AUTH-PEER), which maps operating system user names to PostgreSQL users.

    # su postgres
    $ createuser pyprobe-maint
    $ createuser pyprobe-add
    $ createuser pyprobe-read
    $ createdb probe-results
    $ psql -c 'GRANT CREATE ON DATABASE "probe-results" TO "pyprobe-maint"'

The tables do not exist yet, so privileges cannot be assigned for them. They will be assigned by the maintenance user after creating the tables. Note that pyProbe will modify permissions for all tables in the public schema of the database. This means it does not coexist nicely with other applications in the same database. (This was to avoid maintaining a separate hardcoded list of what tables exist, see db.Database initialization.)

Copy `database.config_sample` to `database.config` and set the usernames and database name. (Passwords need not be specified if they are not used.) Set the mapping between system users and PostgreSQL users - this may involve `/etc/postgresql/9.2/main/pg_ident.conf` and `/etc/postgresql/9.2/main/pg_hba.conf`. For example, in `pg_ident.conf`:

    # MAPNAME       SYSTEM-USERNAME         PG-USERNAME
    pyprobe         pyprobe                 pyprobe-maint
    pyprobe         pyprobe                 pyprobe-read
    pyprobe         pyprobe                 pyprobe-add

And in `pg_hba.conf`:

    # TYPE  DATABASE        USER            ADDRESS                 METHOD
    local   probe-results   pyprobe-maint                           peer map=pyprobe
    local   probe-results   pyprobe-add                             peer map=pyprobe
    local   probe-results   pyprobe-read                            peer map=pyprobe

Then reload the PostgreSQL configuration. If migrating from from the sqlite version of pyProbe, run `python fnprobe/migrate_from_sqlite.py`. If importing the database dumps, run `python fnprobe/copy_from.py`. Now probe collection and analysis can begin!

## Usage

The tools are:

* `probe.py`: connects to a Freenet node, makes probe requests, and stores the results.
* `analyze.py`: analyzes stored probe results, and generates plots of the data.

### `probe.py`

Can be run directly with `python`, with `twistd`, or with the bash script `run`, which supports these operations:

* `start`: Starts the probe if it is not already running.
* `stop`: Stops the probe if it is running.
* `restart`: Stops the probe if it is running, then starts it again.
* `console`: Restarts the probe and follows the log, and stops the probe on interrupt.
* `log`: Follows the log.

Configured with the self-documenting [`probe.config`](https://github.com/Thynix/pyProbe/blob/master/probe.config).

### `analyze.py`

Can perform analysis of gathered probe data:

* Network size estimate
* Store size estimate
* Location distribution
* Peer count distribution
* Link length distribution
* Uptime distribution (using that included with `identifier`)
* Bulk reject percentage distribution

For documentation on using it run `analyze` with `--help`.

## Database Schema

There are separate tables for each result type, errors, and refuals. The database is versioned, and previous versions will be upgraded. All table names but `error`, `refused`, and `peer_count` match the name of the result type with which they are updated. With the exception of `link_lengths`, all tables have the following columns:

* `time`: when the result was committed.
* `htl`: hops to live of the request.
* `duration`: elapsed between sending the probe and receiving the response.

All tables have an `id` primary key. Additional columns vary by table:

### `bandwidth`

* `KiB`- Outgoing bandwidth limit in floating point KiB/s.

### `build`

* `build`: Freenet build number.

### `identifier`

* `identifier`: Randomly assigned (by default; can be set or randomized again at will) integer identifier.
* `percent`: Very low-precision integer uptime percentage over the last 7 days.

### `link_lengths`

Each individual reported length has its own entry.

* `length`: Floating point difference between the responding node's location and one of its peers' locations.
* `count_id`: Matches the `id` of the associated `peer_count` row.

### `peer count`

Set from `LINK_LENGTHS` probes like `link_lengths`.

* `peers`: Number of peers.

### `location`

* `location`: Floating point network location.

### `store_size`:

* `GiB`: Datastore (cache and store) size in floating point GiB.

### `reject_stats`:

* `bulk_request_chk`: Percent bulk CHK requests rejected.
* `bulk_request_ssk`: Percent bulk SSK requests rejected.
* `bulk_insert_chk`: Percent bulk CHK inserts rejected.
* `bulk_insert_ssk`: Percent bulk SSK inserts rejected.

### `uptime_48h`

* `percent`: Floating point uptime percentage over the last 48 hours.

### `uptime_7d`

* `percent`: Floating point uptime percentage over the last 7 days.

### `error`

* `probe_type`: The probe result which was requested.
* `error_type`: The type of error which occurred.
* `code`: If specified, the local node did not recognize this error code. In this case, the `error_type` will be `UNKNOWN`.
* `local`: If `true` the error occurred locally and was not prompted by an error relayed from a remote node. If `false` the error was relayed from a remote node.

### `refused`

* `probe_type`: The probe result which was requested.

### `meta`

* `schema_version`: Internal version number to handle upgrades.
