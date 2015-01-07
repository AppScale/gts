#!/bin/bash
#
# Simple script to rebalance the load on a Cassandra pool. This works only for
# AppScale deployment.
#
# Author: graziano

# Cassandra nodetool.
CMD="/root/appscale/AppDB/cassandra/cassandra/bin/nodetool"

# The keyspace to work on.
KEYSPACE="Keyspace1"

set -e

help() {
        echo "$0 {-cleanup|-rebalance|-repair}"
        echo
        echo "Utility for an AppScale Cassandra cluster:"
        echo "   -repair               repair the cluster (should run routinely)."
        echo "   -cleanup              cleanup the cluster (WARNING: it may take a long time)."
        echo "   -help                 print this message."
        echo
}

# This script can only run on the login node.
am_i_login_node() {
        if [ -e /etc/appscale/login_private_ip ]; then
                LOGIN_IP="$(cat /etc/appscale/login_private_ip)"
                for x in $(ip addr show|awk '/inet / {print $2}'|sed 's;/.*;;') ; do
                        [ "$LOGIN_IP" = "$x" ] && return 0
                done
        fi
        return 1
}

# Check if we are on the head node.
if ! am_i_login_node ; then
        echo "This script should run on the head node."
        exit 1
fi

# Check for other running instances of this script.
output=$(ps aux | grep "/bin/sh -c bash /root/db_repair.sh" | grep -v grep | wc -l)
if [ "$output" -gt "1" ]; then
        echo -e "\nAnother instance is already running. Exiting..."
        exit 1
fi

# Function that checks the ssh key of the host.
# It won't change once created.
test_get_ssh_host_key() {
        # Sanity check.
        if [ -z "$1" ]; then
                echo "Need a hostname or IP address."
                return 1
        fi
        # Check if we have it already.
        if ! ssh-keygen -F ${1} > /dev/null ; then
                ssh-keyscan -H ${1} >> ~/.ssh/known_hosts 2> /dev/null
        fi
        return 0
}

# Check if all ssh host keys of all components are present.
for x in  $(cat /etc/appscale/all_ips); do
        test_get_ssh_host_key $x
done

# Number of AppScale's Database nodes.
AS_NUM_HOSTS="$(cat /etc/appscale/masters /etc/appscale/slaves|sort -u|wc -l)"
MASTER="$(cat /etc/appscale/masters|head -n 1)"

# Sanity checks.
if [ $AS_NUM_HOSTS -lt 1 ]; then
        echo "Error: cannot find Database nodes."
        exit 1
fi
if [ -z "$MASTER" ]; then
        echo "Error: cannot find the master Database node."
        exit 1
fi

# Repair and/or cleanup the cluster.
repair_or_cleanup() {
        IPS_TO_USE=""

        while read -r x y ; do
                # Skip all the nodes that are not in 'Normal' state.
                case "$x" in
                UM)
                        echo "Skipping node $y since it is Moving."
                        ;;
                UL)
                        echo "Skipping node $y since it is Leaving."
                        ;;
                UJ)
                        echo "Skipping node $y since it is Joining."
                        ;;
                UN)
                        IPS_TO_USE="${IPS_TO_USE} $y"
                        ;;
                *)
                        echo "Unknown status $x for node $y."
                        exit 1
                        ;;
                esac

                # Let's query the Cassandra pool (via the master node) and capture
                # the following:
                #  $1 - the status of the node
                #  $2 - the IP address of the node.
        done < <(ssh $MASTER $CMD status|grep ^U|awk '{print $1, $2}')

        # Perform operation.
        for x in ${IPS_TO_USE} ; do
		echo
                echo -n "Working on $x:"
                if [ -n "$1" -a "$1" = "CLEANUP" ]; then
                        echo -n "cleaning..."
                        if ! ssh $x "$CMD cleanup" > /dev/null ; then
                                echo "failed."
                                exit 1
                        fi
                else
                        echo -n "repairing..."
                        if  ! (time ssh $x "$CMD repair -pr ${KEYSPACE}" > /dev/null) ; then
                                echo "failed."
                                exit 1
                        fi
                fi
                echo "done."
        done
}

# Parse command line, and perform operations.
DONE="NO"
while [ $# -ge 0 ]; do
        if [ "$1" = "-repair" ]; then
                repair_or_cleanup
                DONE="YES"
                shift
                continue
        fi
        if [ "$1" = "-cleanup" ]; then
                repair_or_cleanup CLEANUP
                DONE="YES"
                shift
                continue
        fi
        if [ ${DONE} = "YES" ]; then
                exit 0
        fi
        help
        exit 1
done
