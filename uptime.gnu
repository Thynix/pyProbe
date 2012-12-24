set terminal png size 900,600
set key off

set title 'Uptime Distribution'

set xlabel 'Reported 7-day uptime percentage'
set ylabel 'Percent reports with this uptime or less'

set output "plot_week_uptime.png"
plot [0:120] [0:100] 'uptimes' s cumul

