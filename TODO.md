`link_lengths`:

* Could save space by omitting `time` and `htl` on all but the first entry of a given `id`.

`store_size`:

* Correct terminology errors - the datastore contains the store and the cache.

* Consistently use and specify UTC.
* Clean up analyze by breaking into functions instead of a serial script. Perhaps a frontend and backend module?

Stats sites for R - hopefully better population estimation:
http://www.ramas.com/CMdd.htm
http://cran.r-project.org/web/packages/CARE1/index.html
http://cran.r-project.org/web/packages/mra/index.html
http://cran.r-project.org/web/packages/mrds/index.html
http://cran.r-project.org/web/packages/Rcapture/index.html

Perhaps consider per-hour and build a matrix based on distinct IDs and whether they occur in that period.

