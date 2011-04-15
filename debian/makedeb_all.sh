#!/bin/sh

cd `dirname $0`/..

RELEASE=$1
if [ -z "$RELEASE" ]; then
    RELEASE="test"
fi

for comp in\
 core all\
 cassandra hbase hypertable\
 memcachedb mongodb mysql\
 scalaris timesten voldemort simpledb
do
    ./debian/makedeb.sh $comp $RELEASE
    if [ $? -ne 0 ]; then
	echo "Fail to create $comp package."
	exit 1
    fi
done
