#!/bin/bash

# SEVERE LIMITATION:
# VTR will create its own processes to run yosys synthesis etc., which CANNOT be terminated by this script. To find the PIDs, use:
# ps -ef | grep "yosys -c synthesis.tcl"
# and manually kill the process(es) yourself with `sudo kill <pid>`.
# (or alternatively, use `sudo htop`, sort by CPU usage, and terminate accordingly.) 

# Change this to the run script to use with nohup.
BASH_RUN_SCRIPT="./run_with_venv.sh"

PID_FILE="${BASH_RUN_SCRIPT}.pid"

start() {
    if [ -f $PID_FILE ]; then
        echo "The service is already running."
    else
        chmod +x $BASH_RUN_SCRIPT
        nohup $BASH_RUN_SCRIPT &> $BASH_RUN_SCRIPT.out &
        echo $! > $PID_FILE
        echo "Process ID: $(cat $PID_FILE)"
        echo "Service started."
    fi
}

stop() {
    if [ -f $PID_FILE ]; then
        pkill -P $(cat $PID_FILE)
        rm $PID_FILE
        echo "Service stopped."
    else
        echo "The service is not running."
    fi
}

restart() {
    stop
    start
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
esac