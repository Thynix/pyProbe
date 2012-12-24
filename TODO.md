Database upgrade:
then:
    Parameterize (values (?, ?)) util and analyze.
    Omit time and HTL from link_lengths entries: can select from peer_count and find same ID.
	More efficient queries. (Eleriseth #12)
    Treating probe and error type as integers is incomplete. Existing occurances were converted in the upgrade to version 4, but they are still stored and retreived as text.

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

`link_lengths`:

* Could save space by omitting `time` and `htl` and instead finding peer_count entries with the same `id`.

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
