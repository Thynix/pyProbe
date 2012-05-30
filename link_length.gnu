set terminal png size 1200,800
set key off

set title 'Link Length Distribution'

set xlabel 'Link Length (delta location)'
set ylabel 'Percent nodes with this length or less'

set output "link_length_log.png"
set logscale x
#As location is circular and [0,1), largest difference is 0.5.
plot [0.00001:0.5] [0:1] 'links_output' s cumul


set output 'link_length_linear.png'
unset logscale x
plot [0:0.5] [0:1] 'links_output' s cumul
