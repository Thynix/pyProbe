# pyProbe

pyProbe is a collection of data gathering and analysis tools for [Freenet](https://freenetproject.org/) network probes. These probes report limited sets of information at once and apply random noise in order to reduce how identifiable information is while keeping it useful for network-wide statistics. Requires Freenet build 1409 or greater.

## Requirements

* [Python 2.6 or higher](http://www.python.org/download/releases/2.7.3/)
    * [argparse]() (if using Python earlier than 2.7)
* [pysqlite](http://code.google.com/p/pysqlite/)
* [Freenet](https://freenetproject.org/)
* [gnuplot](http://www.gnuplot.info/) (for extra analyze.py plots)
* [rrdtool] (http://oss.oetiker.ch/rrdtool/download.en.html) (rrdpython)
* [Twisted](https://twistedmatrix.com/trac/)
* [twistedfcp](https://github.com/AnIrishDuck/twistedfcp)

## Installation

Freenet, Python, gnuplot, rrdtool, and Twisted all have installation instructions on their respective sites.

However, as of this writing, the FCP field names in the current official build of Freenet [differ](https://github.com/freenet/fred-official/blob/build01410/src/freenet/node/fcp/FCPMessage.java#L22) from what was intended. This means all probes will run at `MAX_HTL` instead of the configured value, resulting in the vast majority of responses being errors due to the unworkably high HTL. To work around this, change `probe.py` line 39 to read `HTL="HTL"`.

### pysqlite

* Available on the [Python Package Index](http://pypi.python.org/pypi/pip): `# pip install pysqlite`

### argparse

* argparse was added to Python in version 2.7. It is available for older versions on the package index: `# pip install argparse`

### twistedfcp

* Clone [twistedfcp](https://github.com/AnIrishDuck/twistedfcp): `$ git clone https://github.com/AnIrishDuck/twistedfcp.git`
* `$ cd twistedfcp`
* `# python setup.py install`

## Usage

The three tools are:

* `probe.py`: connects to a Freenet node to make probe requests, and stores the results.
* `analyze.py`: analyzes stored probe results, and generates plots of the data.
* `util.py`: provides statistics on the stored probe results.

### `probe.py`

Can be run directly with `python`, with `twistd`, or with the bash script `run`, which supports these operations:

* `start`: Starts the probe if it is not already running.
* `stop`: Stops the probe if it is running.
* `restart`: Stops the probe if it is running, then starts it again.
* `console`: Restarts the probe and follows the log, and stops the probe on interrupt.
* `log`: Follows the log.

Configured with the self-documenting [`probe.config`](https://github.com/Thynix/pyProbe/blob/master/probe.config).

### `analyze.py`

When run without arguments, analyzes the past week of probe data to generate statistics:

* Network size estimate
* Plot of location distribution
* Plot of peer count distribution
* Plot of link length distribution

For command line argument documentation run with `--help`.

### `util.py`

Presents a menu with sqlite utility functions and probe collection statistics:

* Result collection rate
* Distribution of error types over probe types
* Success, refusal, and error percentages

For command line argument documentation run with `--help`.

## Database Schema

There are separate tables for each result type, errors, and refuals. The database is versioned, and previous versions will be upgraded. (`init_database()`) All table names but `error`, `refused`, and `peer_count` match the name of the result type with which they are updated. With the exception of `link_lengths` lacking a `duration` column, all tables have the following columns:

* `time`: Timestamp of when the result was committed.
* `htl`: Hops to live value the probe used.
* `duration`: How long elapsed between sending the probe and receiving the response.

Additional columns vary by table:

### `bandwidth`

* `KiB`: Outgoing bandwidth limit in KiB/s.

### `build`

* `build`: Freenet build number.

### `identifier`

* `identifier`: Randomly assigned (by default; can be set or randomized again at will) identifier.
* `percent`: Very low-precision uptime percentage over the last 7 days.

### `link_lengths`

Each individual reported length has its own entry. This table does not have a `duration` column because the next table, `peer_count`, is based off the same probe result and has only one entry for each, which avoids storing that information multiple times for a single returned result.

* `length`: Difference between the responding node's location and one of its peers' locations.
* `id`: Each value is shared with the other entries resulting from the same probe result.

### `peer count`

Set from `LINK_LENGTHS` probes like `link_lengths`.

* `peers`: Number of peers.

### `location`

* `location`: Network location.

### `store_size`:

* `GiB`: Datastore (cache and store) size in GiB.

### `uptime_48h`

* `percent`: Uptime percentage over the last 48 hours.

### `uptime_7d`

* `percent`: Uptime percentage over the last 7 days.

### `error`

* `probe_type`: The probe result which was requested.
* `error_type`: The type of error which occurred.
* `code`: If specified, the local node did not recognize this error code. In this case, the `error_type` will be `UNKNOWN`.
* `local`: If `true` the error occurred locally and was not prompted by an error relayed from a remote node. If `false` the error was relayed from a remote node.

### `refused`

* `probe_type`: The probe result which was requested.
