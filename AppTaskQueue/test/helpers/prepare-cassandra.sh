#!/usr/bin/env bash
#
# Ensures that single-node Cassandra cluster is running on this machine.
# Creates AppScale-related tables in Cassandra.

set -e
set -u

usage() {
    echo "Usage: ${0} --private-ip <IP>"
    echo
    echo "Options:"
    echo "   --private-ip <IP>  Private IP of this machine"
    exit 1
}

PRIVATE_IP=

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
    usage
done

log() {
    LEVEL=${2:-INFO}
    echo "$(date +'%a %b %d %T %Y'): $LEVEL $1"
}

if [ -z ${PRIVATE_IP} ]; then
    usage
fi


log "Configuring Cassandra"
/root/appscale/scripts/setup_cassandra_config_files.py --local-ip ${PRIVATE_IP} \
  --master-ip ${PRIVATE_IP}

log "Starting Cassandra"
su -c '/opt/cassandra/cassandra/bin/cassandra -p cassandra.pid' cassandra
while ! (/opt/cassandra/cassandra/bin/nodetool status | grep UN); do
    sleep 1
done

echo ${PRIVATE_IP} > /etc/appscale/masters
echo ${PRIVATE_IP} > /etc/appscale/slaves

log "Creating tables"
appscale-prime-cassandra --replication 1
