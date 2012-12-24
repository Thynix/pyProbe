Freenet Statistics
==================

<img src="activelink.png" alt="Activelink" width="108" height="36"/>

## Network Size

<!--- TODO: Vertical lines at configuration changes and build release/mandatory. -->

### Past Week

<a href="week_1200x400_plot_network_size.png"><img src="week_900x300_plot_network_size.png" alt="Plot of the last 7 days of network size estimates" title="Last 7 days" width="900" height="300"/></a>

### Past Month

<a href="month_1200x400_plot_network_size.png"><img src="month_900x300_plot_network_size.png" alt="Plot of the last 30 days of network size estimates" title="Last 30 days" width="900" height="300"/></a>

### All Data

<a href="all_1200x400_plot_network_size.png"><img src="all_900x300_plot_network_size.png" alt="Plot of all available network size estimates" title="All available data" width="900" height="300"/></a>

## Store Capacity

### Past Week

<a href="week_1200x400_plot_store_capacity.png"><img src="week_900x300_plot_store_capacity.png" alt="Plot of the last 7 days of store capacity data" title="Last 7 days" width="900" height="300"/></a>

### Past Month

<a href="month_1200x400_plot_store_capacity.png"><img src="month_900x300_plot_store_capacity.png" alt="Plot of the last 30 days of store capacity data" title="Last 30 days" width="900" height="300"/></a>

### All Data

<a href="all_1200x400_plot_store_capacity.png"><img src="all_900x300_plot_store_capacity.png" alt="Plot of all available store capacity data" title="All available data" width="900" height="300"/></a>

## Errors and Refused

### Past Week

<a href="week_1200x400_plot_error_refused.png"><img src="week_900x300_plot_error_refused.png" alt="Plot of the last 7 days of store capacity data" title="Last 7 days" width="900" height="300"/></a>

### Past Month

<a href="month_1200x400_plot_error_refused.png"><img src="month_900x300_plot_error_refused.png" alt="Plot of the last 30 days of store capacity data" title="Last 30 days" width="900" height="300"/></a>

### All Data

<a href="all_1200x400_plot_error_refused.png"><img src="all_900x300_plot_error_refused.png" alt="Plot of all available store capacity data" title="All available data" width="900" height="300"/></a>

## Peer Count

<img src="plot_peer_count.png" alt="Plot of the past week of peer counts" width="900" height="600"/>

## Link Length

<img src="plot_link_length.png" alt="Plot of the past week of link length" width="900" height="600"/>

## 7-Day Uptime

<img src="plot_week_uptime.png" alt="Plot of the past week of 7-day uptime" width="900" height="600"/>

## Explanation

These estimates are based on results gathered with the probes introduced in build 1409.

The network size is estimated by gathering identifier probe results, and comparing the number of distinct identifiers with the total number of samples. Based on the assumption that the results are from nodes selected from the entire network at random, as the probes are designed to do, this allows guessing the size the network would have to be to give that proportion. The instantaneous size estimate does this with an hour of samples, and as such estimates how many nodes are online at that moment.

Nodes still contribute to the network if they are online regularly - they need not be online all the time. The effective network size attempts to account for this by using the same estimation technique as the instantanious size, but with only those identifiers which were seen both in the past period of time and the one before that. This is problematic: one cannot depend on a response from a node during a time period even if it is online. A more accurate estimate could involve the included uptime percentage.

Datastore size probe results return the approximate amount of disk space a node has reserved to store data for the network. Taking the mean of these values and multiplying by the (weekly) effective network size gives an estimate of the total amount of disk space used for datastores throughout the entire network. Half of the datastore on each node is used for caching; half for longer-term storage. When blocks are inserted into Freenet an error correction (FEC) block is added for each one to allow reconstructing the data without being able to fetch every single block. In addition, every block, including error correction, is stored multiple - often three - times. This means that the usable storage capacity on Freenet is approximately 1/12th of the total dedicated disk space.

Refused responses mean that a node opted not to respond with the requested information.

Errors are:

* Disconnected: a node being waited on for a response - not neccesarily the endpoint - disconnected.
* Overload: a node could not accept the probe request because its probe DoS protection had tripped.
* Timeout: timed out while waiting for a response.
* Unknown Error: an error occured, but the error code was not recognized.
* Unrecognized Type: a remote node did not recognize the requested probe type.
* Cannot Forward: a remote node understood the request but failed to forward it to another node.

Link length, peer count, and uptime are from the past 7 days of results. All peer counts above 50 count towards 50. Reported uptime can exceed 100% due to the added random noise.

## Changelog

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

_Generated [GENERATED-DATE] by [operhiem1](/USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/blog/12/). [RRD](size.xml). Made with [pyProbe](/USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/pyProbe.R1/3)._
