Change rrdtool database name from store capacity to datastore size. Re-analyze
datastore backlog using existing size estimates from RRD (under the assumption
it is faster than querying the database again - less than 10 seconds likely.)

Consistently use quoted or unquoted identifiers.
    http://www.postgresql.org/docs/9.2/static/sql-syntax-lexical.html
    Is my understanding correct that parameter substitution will always
    produce literals, not identifiers? (So that string formatting operations
    must be used to insert identifiers like table names?)

Run "explain" on all queries.

Things should be in directories more. Making a /config/ and /logs/

Look into whether to implement database rotation.

Perhaps replace RRDTool with another PostgreSQL table and some R / knitr? Maybe only if it is clear it would not involve reinventing parts of RRDTool.

Specifying probe types by repeated occurances to get ratios is annoying. How to better specify distribution? Percentages / fractions?

https://en.wikipedia.org/wiki/Mann%E2%80%93Whitney_U

Move from command line arguments for settings such as filenames to config
files.

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
