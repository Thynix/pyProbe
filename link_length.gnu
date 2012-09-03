set terminal png size 900,600
set key off

set title 'Link Length Distribution'

set xlabel 'Link Length (delta location)'
set ylabel 'Percent nodes with this length or less'

set output "plot_link_length.png"
set logscale x
#As location is circular and [0,1), largest difference is 0.5.
plot [0.00001:0.5] [0:1] 'links_output' s cumul

