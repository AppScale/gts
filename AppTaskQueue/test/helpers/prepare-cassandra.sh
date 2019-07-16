#!/usr/bin/env bash
#
# Ensures that single-node Cassandra cluster is running on this machine.
# Creates AppScale-related tables in Cassandra.

set -e
set -u

usage() {
    echo "Usage: ${0} --private-ip <IP> --zk-ip <IP>"
    echo
    echo "Options:"
    echo "   --private-ip <IP>  Private IP of this machine"
    echo "   --zk-ip <IP>       IP of the zookeeper machine"
    exit 1
}

PRIVATE_IP=
ZK_IP=

# Let's get the command line arguments.
while [ $# -gt 0 ]; do
    if [ "${1}" = "--private-ip" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        PRIVATE_IP="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--zk-ip" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        ZK_IP="${1}"
        shift
        continue
    fi
    usage
done

log() {
    LEVEL=${2:-INFO}
    echo "$(date +'%a %b %d %T %Y'): $LEVEL $1"
}

if [ -z ${PRIVATE_IP} ] || [ -z ${ZK_IP} ]; then
    usage
fi


echo ${PRIVATE_IP} > /etc/appscale/masters
echo ${PRIVATE_IP} > /etc/appscale/slaves
echo ${ZK_IP} > /etc/appscale/zookeeper_locations


log "Configuring Cassandra"
/root/appscale/scripts/setup_cassandra_config_files.py --local-ip ${PRIVATE_IP} \
  --master-ip ${PRIVATE_IP}

log "Starting Cassandra"
su -c '/opt/cassandra/cassandra/bin/cassandra -p cassandra.pid' cassandra
cassandra_wait_start=$(date +%s)
while ! (/opt/cassandra/cassandra/bin/nodetool status | grep UN); do
    current_time=$(date +%s)
    elapsed_time=$((current_time - cassandra_wait_start))
    if [ "${elapsed_time}" -gt 60 ]
    then
        log "Timed out waiting for Cassandra to start" "ERROR"
        exit 1
    fi
    sleep 1
done

log "Creating tables"
for i in 1 2 3 ; do
    RESULT=FAILED
    appscale-prime-cassandra --replication 1 && RESULT=OK && break
    log "Failed to create Cassandra tables" "WARNING"
    sleep 15
done

if [ ${RESULT} = FAILED ]; then
    log "Failed to create Cassandra tables after 3 retries" "ERROR"
    exit 1
fi
