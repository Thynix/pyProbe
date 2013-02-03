set terminal png size 900,600
set key off

set title 'Uptime Distribution'

set xlabel 'Reported 7-day uptime percentage'
set ylabel 'Percent reports'

set style data histogram
set style fill solid border -1

set output "plot_week_uptime.png"
plot [0:120] [0:] 'uptimes' with boxes

