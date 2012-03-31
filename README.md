# pyProbe

pyProbe is a collection of data gathering and analysis tools for [Freenet](https://freenetproject.org/) network probes.

## Requirements

* Python 2.6.6-ish
* [pysqlite](http://code.google.com/p/pysqlite/)
* [Freenet](https://freenetproject.org/)
* [gnuplot](http://www.gnuplot.info/)
* [libGEXF](http://gexf.net/lib/) (Optional - only for exporting network topology.)

## Setup

### Installing pysqlite

* Download and extract the source tarball.
* `sudo python setup.py install`

### Enabling TMCI

* Shut down Freenet. Freenet will write out its settings on shutdown so these changes cannot be made while the node is running.
* In `freenet.ini`, set these options, or add them if they do not exist:
    * `console.enabled=true`
    * `console.directEnabled=true`
* Start Freenet again.

### Installing libGEXF

* Download and extract the source tarball. (Word of warning: as of this writing the archive contains no top-level directory.)
* Install `swig`.
* `./autogen.sh`
* `./configure`
* `make`
* `cd binding/python`
* `sudo python setup.py install`

## Usage

The three tools are:

* `probe.py`: connects to a Freenet node and makes probe requests to random locations, storing the results in a database.
* `analyze.py`: reads probe results from a database, generating plots of the data and a network topology graph.
* `util.py`: provides statistics on the amount of information held by the database and allows easily running the `sqlite` commands `analyze` and `vacuum`.

Help screens are available by running a tool with the `--help` or `-h` arguments.
