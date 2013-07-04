Run "explain" on all queries.

Things should be in directories more. Making a /config/ and /logs/

Look into whether to implement database rotation.

Perhaps replace RRDTool with another PostgreSQL table and some R / knitr? Maybe only if it is clear it would not involve reinventing parts of RRDTool.

Specifying probe types by repeated occurances to get ratios is annoying. How to better specify distribution? Percentages / fractions?

Does PostgreSQL / psycopg handle time zone conversion? Can I insert a datetime() or select by it and have time zones converted to and from when appropriate?
    Probably. Datetime conversion would be insane otherwise.

https://en.wikipedia.org/wiki/Mann%E2%80%93Whitney_U

Move from command line arguments for settings such as filenames to config
files.

Convert tabs to spaces as per PEP8.
	Similarly line lengths below 80.

Output to a directory and insert the entire thing instead of requiring an explicit list of files.
	Would probably require something like using the Python Gnuplot library so that the output path could be changed.

Use Q-Q plots for link length distribution (logarithmic) and location. (uniform?)

Switch to built-in Python logging module.

Use Greasemonkey in Firefox and Chrome native support for the same to have interactive Javascript plots.
    Possibilities:
        http://dygraphs.com/
        https://github.com/danvk/dygraphs
        http://www.flotcharts.org/
    Data in HTML? In a CSV in the same USK container?

Keep list of notable dates, insert labeled vertical lines in the plots at those points.
    World events
    Version releases
    Changes to probe gathering techniques

`store_size`:

* Correct terminology errors - the datastore contains the store and the cache.

* Clean up analyze by breaking into functions instead of a serial script. Perhaps a frontend and backend module?

Stats sites for R - hopefully better population estimation:
http://www.ramas.com/CMdd.htm
http://cran.r-project.org/web/packages/CARE1/index.html
http://cran.r-project.org/web/packages/mra/index.html
http://cran.r-project.org/web/packages/mrds/index.html
http://cran.r-project.org/web/packages/Rcapture/index.html

Perhaps consider per-hour and build a matrix based on distinct IDs and whether they occur in that period.
