#!/bin/sh
#
# Cleanup old Zookeeper transactions.
#

MONIT_CMD="$(which monit)"
LOG4J_CONF="/root/log4j.xml"
ZK_DIR="/opt/appscale/zookeeper"

# Sanity checks.
if [ -z "${MONIT_CMD}" ]; then
        echo "Cannot find monit!"
        exit 1
fi
if [ ! -d "${ZK_DIR}" ]; then
        echo "Cannot find Zookeeper directory!"
        exit 2
fi

# Run only on Zookeeper node.
if [ ! ${MONIT_CMD} summary | grep zookeeper > /dev/null ]; then
        echo "Zookeeper is not running."
        exit 1
fi

# Create configuration for log4j.
if [ ! -e ${LOG4J_CONF} ]; then
        cat <<EOF > ${LOG4J_CONF}
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE log4j:configuration SYSTEM "log4j.dtd">
 
<log4j:configuration xmlns:log4j="http://jakarta.apache.org/log4j/">
  <appender name="console" class="org.apache.log4j.ConsoleAppender">
    <param name="Target" value="System.out"/>
    <layout class="org.apache.log4j.PatternLayout">
      <param name="ConversionPattern" value="%-5p %c{1} - %m%n"/>
    </layout>
  </appender>
 
  <root>
    <priority value ="debug" />
    <appender-ref ref="console" />
  </root>
 
</log4j:configuration>
EOF
fi

# Clean Zookeper transactions.
java -cp /root/:/usr/lib/zookeeper/zookeeper.jar:/usr/lib/zookeeper/lib/slf4j-api-1.6.1.jar:/usr/lib/zookeeper/lib/slf4j-log4j12-1.6.1.jar:/usr/lib/zookeeper/liblog4j-1.2.15.jar:conf:/usr/lib/zookeeper/lib/* -Dlog4j.debug org.apache.zookeeper.server.PurgeTxnLog ${ZK_DIR} ${ZK_DIR} -n 3

