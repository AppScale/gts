#!/bin/bash
# Only start haproxy if it is not already running.
# We do this because God cannot handle this logic directly.
ISHAPROXYRUNNING=`ps aux | grep haproxy | grep -v grep | grep -v start_haproxy | wc | awk {'print $1'}`
[[ $ISHAPROXYRUNNING -eq "0" ]] && /etc/init.d/haproxy start
