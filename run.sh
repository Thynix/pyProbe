#!/bin/bash
#Exit on error
set -o errexit
if [ "X`id -u`" = "X0" -a -z "$RUN_AS_USER" ]
then
    echo "Do not run this script as root."
    exit 1
fi

pidFile="probe.pid"
logFile="probe.log"

start() {
    if [ -e "$pidFile" ]
    then
        if kill -0 `cat "$pidFile"`
        then
            echo "Probe is already running."
            return
        else
            echo "Removing stale PID file."
            rm "$pidFile"
        fi
    fi
    echo "Starting probe."
    twistd --python=probe.py --logfile="$logFile" --pidfile="$pidFile"
}

stop() {
    if [ -e "$pidFile" ]
    then
        if kill -0 `cat "$pidFile"`
        then
            echo "Stopping probe."
            kill -INT `cat "$pidFile"`
            i=0
            #twistd removes the pid file on shutdown.
            while [ -e "$pidFile" ]
            do
                let "i += 1"
                if [ $i -eq "100" ]
                then
                    echo "Waiting..."
                    i=0
                fi
            done
            return
        fi
    fi
    echo "Probe is not running."
}

status() {
    if [ -e "$pidFile" ]
    then
        if kill -0 `cat "$pidFile"`
        then
            echo "Probe is running."
            return
        fi
    fi
    #If the PID file does not exist or a process with that PID is not running.
    echo "Probe is not running."
}

log() {
    tail -F "$logFile"
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
        status
        ;;

    'console')
        start
        log
        ;;

    'log')
        log
        ;;

    *)
        echo "Usage: $0 { console | start | stop | restart | status | log }"
        exit 1
        ;;

esac

exit 0
