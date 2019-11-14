#!/usr/bin/env bash
#
# Ensures that Zookeeper is running on this machine.
# Creates appscale common nodes in zookeeper.


set -e
set -u


log() {
    local LEVEL=${2:-INFO}
    echo "$(date +'%Y-%m-%d %T'): $LEVEL $1"
}


log "Starting zookeeper"
systemctl start zookeeper

ZK_CLI="/usr/share/zookeeper/bin/zkCli.sh"

log "Waiting for ZooKeeper to start"
while ! ${ZK_CLI} ls / ; do
    sleep 1
done

log "Create root appscale nodes in zookeeper"
/usr/share/zookeeper/bin/zkCli.sh create /appscale ""
/usr/share/zookeeper/bin/zkCli.sh create /appscale/projects ""
