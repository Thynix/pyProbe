set terminal png size 1200,800
set output "link_length_log.png"
set key off

set logscale x

set xlabel 'Link Length (delta location)'
set ylabel 'Percent nodes with this length or less'

#TODO: Take number of elements as argument in order to normalize,
#so 1/363281 where 363281 is the number of records and should be variable.
#TODO: Where to start the x axis? Can't start log plot at zero.
plot [0.0001:1] 'links_output' u 1:(1/363281.) s cumul

set output 'link_length_linear.png'

unset logscale x

#As location is circular and [0,1), largest difference is 0.5.
plot [0:0.5] 'links_output' u 1:(1/363281.) s cumul
