# pyProbe

pyProbe is a collection of data gathering and analysis tools for [Freenet](https://freenetproject.org/) network probes. Requires Freenet build 1408 or greater.

## Requirements

* Python 2.6.6-ish
* [pysqlite](http://code.google.com/p/pysqlite/)
* [Freenet](https://freenetproject.org/)
* [gnuplot](http://www.gnuplot.info/)
* [twisted](https://twistedmatrix.com/trac/)
* [twistedfcp](https://github.com/AnIrishDuck/twistedfcp)

## Usage

The three tools are:

* `probe.py`: connects to a Freenet node and makes probe requests, storing the results in a database. A config file allows changing parameters, such as how frequenty probes are sent, or what types of probes are sent.
* `analyze.py`: reads probe results from a database, analyses it, and generates plots of the data.
* `util.py`: provides statistics on the information held by the database and allows easily running the `sqlite` commands `analyze` and `vacuum`.

Help screens are available by running a tool with the `--help` or `-h` arguments.
