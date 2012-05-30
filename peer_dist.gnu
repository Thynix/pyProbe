set terminal png size 1200,800
set output "peer_dist.png"

#How to handle xrange? Could mean missing huge changes.
set xrange [1:50]
set xtics 5

set title "Peer Count Distribution"

set xlabel "Reported Peers"
set ylabel "Nodes"

set style data histogram
set style fill solid border -1

set key off

plot 'peerDist.dat' with boxes
