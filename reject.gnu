set terminal png size 900,600

set title 'Reject Distribution'

set xlabel 'Reported reject percentage'
set ylabel 'Percent reports'

set style data histogram
set style fill solid border -1

set logscale x

set output "plot_week_reject.png"
plot [1:100] [0:] 'bulk_request_chk' title 'Bulk Request CHK' with lines,\
                  'bulk_request_ssk' title 'Bulk Request SSK' with lines,\
                  'bulk_insert_chk' title 'Bulk Insert CHK' with lines,\
                  'bulk_insert_ssk' title 'Bulk Insert SSK' with lines

