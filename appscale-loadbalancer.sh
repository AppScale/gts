#!/bin/sh
# /etc/init.d/appscale-loadbalancer
# Chris Bunch
### BEGIN INIT INFO
# Provides: appscale
# Required-Start: $network
# Required-Stop:
# Default-Start: 2 3 4 5
# Default-Stop:  0 1 6
# Short-Description: AppScale AppLoadBalancer service
# Description:       AppScale AppLoadBalancer service
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

GOD_PORT=17165
# this is needed for integrated tools.
export HOME=`cd ${APPSCALE_HOME}/..;pwd`

case "$1" in
  start)
    log_begin_msg "Starting AppScale AppLoadBalancer.."
    ${GOD} -c ${APPSCALE_HOME}/AppLoadBalancer/config/global.god -p ${GOD_PORT}
    echo "0" > /proc/sys/net/ipv4/icmp_echo_ignore_broadcasts 
#    ruby ${APPSCALE_HOME}/AppController/changeRootPwd.rb
    log_end_msg 0
    ;;
  stop)
    log_begin_msg "Stopping AppScale AppLoadBalancer.."
    ${GOD} stop loadbalancer
    ${GOD} quit
#    pkill -9 god
    log_end_msg 0
    ;;
  *)
    echo "Usage: /etc/init.d/appscale-loadbalancer {start|stop}"
    exit 1
    ;;
esac
