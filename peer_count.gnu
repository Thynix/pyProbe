set terminal png size 900,600
set output "plot_peer_count.png"

#How to handle xrange? Could mean missing huge changes.
set xrange [1:50]
set xtics 5

set title "Peer Count Distribution"

set xlabel "Reported Peers"
set ylabel "Percent of Reports"

set style data histogram
set style fill solid border -1

set key off

plot 'peerDist.dat' with boxes
