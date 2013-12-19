Freenet Statistics
==================

<img src="activelink.png" alt="Activelink" width="108" height="36"/>

## Network Size

<!--- TODO: Vertical lines at configuration changes and build release/mandatory. -->

### Last Week

<a href="week_1200x400_plot_network_size.png"><img src="week_900x300_plot_network_size.png" alt="Plot of the last 7 days of network size estimates" title="Last 7 days" width="900" height="300"/></a>

### Last Month

<a href="month_1200x400_plot_network_size.png"><img src="month_900x300_plot_network_size.png" alt="Plot of the last 30 days of network size estimates" title="Last 30 days" width="900" height="300"/></a>

### Last Year

<a href="year_1200x400_plot_network_size.png"><img src="year_900x300_plot_network_size.png" alt="Plot of the last year of network size estimates" title="Last year" width="900" height="300"/></a>

## Datastore Size

### Last Week

<a href="week_1200x400_plot_datastore.png"><img src="week_900x300_plot_datastore.png" alt="Plot of the last 7 days of datastore size estimates" title="Last 7 days" width="900" height="300"/></a>

### Last Month

<a href="month_1200x400_plot_datastore.png"><img src="month_900x300_plot_datastore.png" alt="Plot of the last 30 days of datastore size estimates" title="Last 30 days" width="900" height="300"/></a>

### Last Year

<a href="year_1200x400_plot_datastore.png"><img src="year_900x300_plot_datastore.png" alt="Plot of the last year of datastore size estimates" title="Last year" width="900" height="300"/></a>

## Errors and Refused

### Last Week

<a href="week_1200x400_plot_error_refused.png"><img src="week_900x300_plot_error_refused.png" alt="Plot of the last 7 days of errors and refusals" title="Last 7 days" width="900" height="300"/></a>

### Last Month

<a href="month_1200x400_plot_error_refused.png"><img src="month_900x300_plot_error_refused.png" alt="Plot of the last 30 days of errors and refusals" title="Last 30 days" width="900" height="300"/></a>

### Last Year

<a href="year_1200x400_plot_error_refused.png"><img src="year_900x300_plot_error_refused.png" alt="Plot of the last year of errors and refusals" title="Last year" width="900" height="300"/></a>

## Peer Count

<img src="plot_peer_count.png" alt="Plot of the last week of peer counts" width="900" height="600"/>

## Link Length

<img src="plot_link_length.png" alt="Plot of the last week of link length" width="900" height="600"/>

## 7-Day Uptime

<img src="plot_week_uptime.png" alt="Plot of the last week of 7-day uptime" width="900" height="600"/>

## Bulk Reject

<img src="plot_week_reject.png" alt="Plot of the last week of bulk reject percentage by type" width="900" height="600"/>

## Explanation

These estimates are based on results gathered with the probes introduced in build 1409.

The network size is estimated by gathering identifier probe results, and comparing the number of distinct identifiers with the total number of samples. Based on the assumption that the results are from nodes selected from the entire network at random, as the probes are designed to do, this allows guessing the size the network would have to be to give that proportion. The instantaneous size estimate does this with an hour of samples, and as such estimates how many nodes are online at that moment.

Nodes still contribute to the network if they are online regularly - they need not be online all the time. The effective network size attempts to account for this by using the same estimation technique as the instantaneous size, but with only those identifiers which were seen both in the last period of time and the one before that. This is problematic: one cannot depend on a response from a node during a time period even if it is online. A more accurate estimate could involve the included uptime percentage.

Datastore size probe results return the approximate amount of disk space a node has reserved to store data for the network. After excluding outliers, taking the mean and multiplying by the (weekly) effective network size gives an estimate of the total amount of disk space used for datastores throughout the entire network. Without outliers excluded (seemingly impossibly) extreme values lead to sudden jumps in the estimate. Note that due to block storage redundancy the usable storage capacity is less, but how much less uses guesswork, so this is easier to estimate. It might be on the order of 1/12.

Refused responses mean that a node opted not to respond with the requested information.

Errors are:

* Disconnected: a node being waited on for a response - not necessarily the endpoint - disconnected.
* Overload: a node could not accept the probe request because its probe DoS protection had tripped.
* Timeout: timed out while waiting for a response.
* Unknown Error: an error occurred, but the error code was not recognized.
* Unrecognized Type: a remote node did not recognize the requested probe type.
* Cannot Forward: a remote node understood the request but failed to forward it to another node.

Link length, peer count, bulk reject percentages, and uptime are from the last day of results. All peer counts above 110 count towards 110. Reported uptime can exceed 100% due to the added random noise. Bulk reject percentages are restricted to between 0% and 100%.

The bulk queue (therefore not realtime queue) reject percentages are an indicator of network health. My understanding is that a node will reject a request if it does not have sufficient bandwidth available to take on the commitment. This would mean that high reject percentages might indicate low bandwidth limits and problems with routing. I am currently collecting information on bandwidth limits, but I am not yet plotting that information.

## Changelog

### August 8th, 2013

Port backend to PostgreSQL and bring the site back online after integrating backlog from the SQLite version. Thanks to RhodiumToad for extensive help! Add sample size label to plots. The bulk reject sample size is likely to be around 2% low. (Only the number of results with data for each type, not the number of results in all, is currently visible from the plotting layer.) Reduce non-RRD plot time span to a day - the probe rate is high enough that it's enough information. Estimate disk space dedicated to datastore instead of store capacity. This excludes outliers, so a plot showing the distribution of those outliers would be useful, but that's not yet implemented.

The SQLite backend had serious problems around May 10th or 20th and stopped storing results or answering queries. I think this was my fault in mangling the database file, but there were enough other annoyances with SQLite being untyped and increasingly slow that moving still seemed worthwhile.

### May 9th, 2013

Fix typos.

Backend changes and refactoring.

There was initially a regression where no results were committed.

### March 24th, 2013

Change bulk reject percentages plot to log scale.

### March 17th, 2013

Add bulk reject percentages plot.

### February 3rd, 2013

Fix plotting weekly size estimate as daily. Change longest time plots to cover the last year instead of all data. Plot uptime distribution in a histogram for readability. Fix histogram capping.

More database backend improvements. (Thanks Eleriseth!)

### January 1st, 2013

Plot each hourly daily size estimate instead of averaging them over 24 hours. (Thanks TheSeeker!)

### December 23rd, 2012

Add 7-day uptime plot.

Many backend improvements. (Thanks Eleriseth!) Fix Infocalypse repo. (Thanks djk!)

### December 9th, 2012

Implement first of many backend improvements. (Thanks Eleriseth!)

### December 1st, 2012

Add plots of errors and refused responses. Add daily effective network size. (Thanks ArneBab!) Fix non-relative links in the footer being relative. (Thanks SeekingFor!)

### October 7th, 2012

Add plots of the past week and month of network size and store capacity. Click for a larger version.

### September 10th, 2012

Correct September 3rd changelog entry. Improve HTML output to meet XHTML 1.1.

Link length and peer count plots:

* Fix order of magnitude error on percentage axis.
* Percentage is of reports, not nodes.

Fix typos and improve wording.

### September 3rd, 2012

Initial release.

* Plots of network and usable store size estimates for all available data.
* A download of the network and usable store size estimate RRD.
* Plots of the past 7 days of link length and peer count distribution.

_Generated [GENERATED-DATE] by [operhiem1](/USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/blog/18/) using pyProbe. Web mirror is [here](http://asksteved.com/stats/). The RRD is [here](size.xml). The source code is in [this Infocalypse repository](/USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/pyProbe.R1/11), or on [GitHub](https://github.com/thynix/pyProbe/)._
