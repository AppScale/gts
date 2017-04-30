#!/usr/bin/env bash
### BEGIN INIT INFO
# Provides:       appscale-unmonit
# Required-Start: $local_fs
# Required-Stop:  $local_fs
# Default-Start:  2 3 4 5
# Default-Stop:   0 1 6
# Description:    Prevents Monit from starting AppScale services.
### END INIT INFO

# This script is meant to be run at boot to prevent monit from starting
# services. The AppController should restart them as needed.

case "$1" in
    start)
        rm -rf /etc/monit/conf.d/appscale*cfg
        echo "AppScale Monit files removed"
        ;;
    stop) echo "Service stopped" ;;
    *) echo "Usage: $0 {start|stop}"
esac
