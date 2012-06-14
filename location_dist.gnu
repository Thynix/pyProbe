set terminal png size 1200,800
set key off

set title 'Location Distribution'

set xlabel 'Location'
set ylabel 'Percent nodes with this location or less'

set output 'location_dist.png'
plot [0:1.0] [0:1] 'locations_output' s cumul
