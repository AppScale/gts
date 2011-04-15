#!/bin/sh

val=`echo "status 'summary'" | ${APPSCALE_HOME}/AppDB/hbase/hbase-0.89.20100924/bin/hbase shell | mawk '/load$/{print $1}'`
if [ -z "$val" ]; then
    echo "0"
else
    echo $val
fi
