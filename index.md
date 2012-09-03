Freenet Statistics
==================

<img src="activelink.png" alt="Activelink" width="108" height="36"/>

## Network Size

<!--- TODO: Past month; week as well --->

<img src="plot_network_size.png" alt="Plot of all available network size estimates" title="All available data" width="900" height="300"/>

## Store Capacity

<img src="plot_store_capacity.png" alt="Plot of all available store capacity data" title="All available data" width="900" height="300"/>

<!--- TODO: Graphs of error; refual occurances. --->

## Peer Count

<img src="plot_peer_count.png" alt="Plot of the past week of peer counts" width="900" height="600"/>

## Link Length

<img src="plot_link_length.png" alt="Plot of the past week of link length" width="900" height="600"/>

## Explanation

These estimates are based on results gathered with the probes introduced in build 1409.

The network size is estimated by gathering identifier probe results, and comparing the number of distinct identifiers with the total number of samples. Based on the assumption that the results are from nodes selected from the entire network at random, as the probes are desined to do, this allows guessing the size the network would have to be to give that proportion. The instantaneous size estimate does this with an hour of samples, and as such estimates how many nodes are online at that moment.

Nodes still contribute to the network if they are online regularly - they need not be online all the time. The effective network size attempts to account for this by using the same estimation technique as the instantanious size, but with only those identifiers which were seen both in the past week and the previous week. This is problematic: one cannot depend on a response from a node during a week even if it is online during that week. A more accurate estimate could involve the included uptime percentage.

Datastore size probe results return the approximate amount of disk space a node has reserved to store data for the network. Taking the mean of these values and multiplying by the effective network size gives an estimate of the total amount of disk space used for datastores throughout the entire network. Half of the datastore on each node is used for caching; half for longer-term storage. When blocks are inserted into Freenet an error correction (FEC) block is added for each one to allow reconstructing the data without being able to fetch every single block. In addition, every block, including error correction, is stored multiple - often three - times. This means that the usable storage capacity on Freenet is approximately 1/12th of the total dedicated disk space.

Link length and peer count are from the past 7 days results. All peer counts above 50 count towards 50.

## Changelog

### September 3rd, 2012

<!--- TODO: Vertical lines at configuration changes and build release/mandatory. --->

Initial release. This consists of plots of network and usable store size estimates for all available data, and downloads for the RRDs they were generated from.

_Generated [GENERATED-DATE] by [operhiem1](USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/blog/12/). [RRD](size.xml). Made with [pyProbe](USK@pxtehd-TmfJwyNUAW2Clk4pwv7Nshyg21NNfXcqzFv4,LTjcTWqvsq3ju6pMGe9Cqb3scvQgECG81hRdgj5WO4s,AQACAAE/pyProbe/1)._
