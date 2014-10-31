#!/bin/bash
#
# Simple script to repair and clean a Cassandra pool. This works only for
# AppScale deployment.
#
# Repair needs to be done before gc_grace_seconds expires to avoid deleted
# rows to resurface on replicas. Cleanup will delete rows no longer
# pertinent to the node (for example because of a re-balance).
#
# Author: graziano

# Where to find the command to query cassandra.
CMD="/root/appscale/AppDB/cassandra/cassandra/bin/nodetool"

# The keyspace we want to work on.
KEYSPACE="Keyspace1"

# Do we run in parallel?
PARALLEL="NO"

set -e
 
help() {
        echo "$0 [-parallel]"
        echo
        echo " Repairs and cleans an AppScale Cassandra cluster."
        echo "   -parallel              run repair in parallel on all nodes."
        echo
}

# This script can only run on the login node.
am_i_login_node() {
        LOGIN_IP="$(cat /etc/appscale/login_private_ip)"
        for x in $(ip addr show|awk '/inet / {print $2}'|sed 's;/.*;;') ; do
                [ "$LOGIN_IP" = "$x" ] && return 0
        done
        return 1
}

# Check if we are on the head node.
if ! am_i_login_node ; then
        echo "This script runs on the head node (on this deployment $LOGIN_IP)."
        exit 1
fi
 
# Parse command line.
while [ $# -gt 0 ]; do
        if [ "$1" = "-parallel" ]; then
                PARALLEL="YES"
                shift
                continue
        fi
        help
        exit 1
done

# Let's see how many nodes AppScale believes we have.
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
 
while read -r x y ; do
        # Make sure we got the host key.
        ssh-keygen -R ${y}
        ssh-keyscan -H ${y} >> ~/.ssh/known_hosts

        # Let's skip all the nodes that are not in 'Normal' state.
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
                echo -n "Working on $y: repairing..."
                if [ "$PARALLEL" = "NO" ]; then
                        if  ! ssh $MASTER "$CMD -h $y repair -pr ${KEYSPACE}" > /dev/null ; then
                                echo "failed."
                                exit 1
                        fi
                        echo -n "cleaning..."
                        if ! ssh $MASTER "$CMD -h $y cleanup" > /dev/null ; then
                                echo "failed."
                                exit 1
                        fi
                else
                        ( ssh $y "$CMD repair -pr ${KEYSPACE}") &
                        echo -n "cleaning..."
                        ( ssh $y "$CMD cleanup" ) &
                fi
                echo "done."
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
