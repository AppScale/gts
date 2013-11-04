#!/bin/sh
# /etc/init.d/appscale-progenitor
# Chris Bunch
### BEGIN INIT INFO
# Provides: appscale
# Required-Start: $network
# Required-Stop:
# Default-Start: 2 3 4 5
# Default-Stop:  0 1 6
# Short-Description: AppScale Progenitor service
# Description:       AppScale Progenitor service
### END INIT INFO

. /etc/profile
. /lib/lsb/init-functions

SECRET_FILE=/etc/appscale/secret.key

case "$1" in
  start)
    log_begin_msg "Starting AppScale Progenitor.."
    LIVE_APPCONTROLLERS=$(ps -ef | grep "djinnServer" | grep -v "grep" | wc -l)
    if [ $LIVE_APPCONTROLLERS -eq 0 -a -e $SECRET_FILE ];
    then
      log_begin_msg "AppController not running - starting it now."
      rm -rf /etc/monit/conf.d/*.cfg
      cp /root/appscale/AppController/appcontroller.cfg /etc/monit/conf.d/
      sleep 5
      /usr/local/bin/monit -Ic /etc/monitrc &
    else
      log_begin_msg "AppController already running - not starting it again."
    fi
    log_end_msg 0
    ;;
  *)
    echo "Usage: /etc/init.d/appscale-progenitor start"
    exit 1
    ;;
esac
