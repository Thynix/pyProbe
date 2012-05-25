#!/bin/bash
if [ "X`id -u`" = "X0" -a -z "$RUN_AS_USER" ]
then
    echo "Do not run this script as root."
    exit 1
fi

pid=probe.pid
log=probe.log

start() {
    twistd --python=probe.py --logfile="$log" --pidfile="$pid"
}

stop() {
    kill `cat "$pid"`
}

case "$1" in
    'start')
        start
        ;;

    'stop')
        stop
        ;;

    'restart')
        stop
        start
        ;;

    'status')
        tail -F "$log"
    ;;

    *)
        echo "Usage: $0 { start | stop | restart | status }"
        exit 1
        ;;

esac

exit 0
