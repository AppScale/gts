#!/bin/sh
# /etc/init.d/appscale-monitoring
# Chris Bunch
### BEGIN INIT INFO
# Provides: appscale
# Required-Start: $network
# Required-Stop:
# Default-Start: 2 3 4 5
# Default-Stop:  0 1 6
# Short-Description: AppScale AppMonitoring service
# Description:       AppScale AppMonitoring service
### END INIT INFO

#PATH="/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin"
. /etc/profile
. /lib/lsb/init-functions

if [ -e /usr/bin/god ]; then
  GOD=/usr/bin/god
elif [ -e /var/lib/gems/1.8/bin/god ]; then
  GOD=/var/lib/gems/1.8/bin/god
else
  log_failure_msg "god command not found."
  exit 1
fi

GOD_PORT=17166
# this is needed for integrated tools.
export HOME=`cd ${APPSCALE_HOME}/..;pwd`

case "$1" in
  start)
    log_begin_msg "Starting AppScale AppMonitoring.."
    ${GOD} -c ${APPSCALE_HOME}/AppMonitoring/config/global.god -p ${GOD_PORT}
    echo "0" > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts 
    log_end_msg 0
    ;;
  stop)
    log_begin_msg "Stopping AppScale AppMonitoring.."
    ${GOD} stop monitoring -p ${GOD_PORT}
    ${GOD} quit -p ${GOD_PORT}
#    pkill -9 god
    log_end_msg 0
    ;;
  *)
    echo "Usage: /etc/init.d/appscale-monitoring {start|stop}"
    exit 1
    ;;
esac
