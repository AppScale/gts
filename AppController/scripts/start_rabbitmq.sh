#!/bin/bash
# First argument is the secret.
# Because God cannot do conditional login in the start command, 
# we have it call this script instead.
ISRABBITRUNNING=`ps aux | grep rabbitmq | grep erlang | grep -v grep | wc | awk {'print $1'}`
[[ $ISRABBITRUNNING -eq "0" ]] && rabbitmq-server -detached -setcookie $1
