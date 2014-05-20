#!/bin/sh
# /etc/init.d/appscale-controller

### BEGIN INIT INFO
# Provides: appscale
# Required-Start: $network
# Required-Stop:
# Default-Start: 2 3 4 5
# Default-Stop:  0 1 6
# Short-Description: AppScale Controller service
# Description:       AppScale Controller service
### END INIT INFO

. /etc/profile
. /lib/lsb/init-functions

RUBY=/usr/bin/ruby
#RUBY=/usr/bin/jruby
PNAME=AppController
PID=/tmp/djinn.pid

case "$1" in
  start)
    log_begin_msg "Starting AppScale Controller.."
#    start-stop-daemon --start --background --pidfile ${PID} --name ${PNAME} --exec ${RUBY} -- ${APPSCALE_HOME}/AppController/djinnServer.rb
    ${RUBY} ${APPSCALE_HOME}/AppController/djinnServer.rb &
    log_end_msg 0
    ;;
  stop)
    log_begin_msg "Stopping AppScale Controller.."
    ${RUBY} ${APPSCALE_HOME}/AppController/terminate.rb
#    start-stop-daemon --stop --name ${PNAME} --pidfile ${PID}
    log_end_msg 0
    ;;
  *)
    echo "Usage: /etc/init.d/appscale-controller {start|stop}"
    exit 1
    ;;
esac
