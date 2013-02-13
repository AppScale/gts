#!/bin/bash
# Only start ejabberd if it is not already running.
# We do this because God cannot handle this logic directly.
ISEJABBERDRUNNING=`ps aux | grep ejabberd | grep mnesia | grep -v grep | wc | awk {'print $1'}`
[[ $ISEJABBERDRUNNING -eq "0" ]] && /etc/init.d/ejabberd start
