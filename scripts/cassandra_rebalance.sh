#!/bin/bash
#
# Simple script to rebalance the load on a Cassandra pool. This works only for
# AppScale deployment.
#
# Author: graziano

# Where to find the command to query cassadra.
CMD="/root/appscale/AppDB/cassandra/cassandra/bin/nodetool"

# The keyspace we want to work on.
KEYSPACE="Keyspace1"

# The percentage we tolerate before triggering rebalancing.
DRIFT="15"

# Where AppScale saves the sample keys.
KEY_SAMPLES="/opt/appscale/rangekeysample.out"

# Keep only this many keys around.
MAX_KEYS="10000"

set -e
 
# This script can only run on the login node.
am_i_login_node() {
        LOGIN_IP="$(cat /etc/appscale/login_private_ip)"
        for x in $(ifconfig |awk '/inet addr:/ {print $2}'|sed 's/addr://') ; do
                [ "$LOGIN_IP" = "$x" ] && return 0
        done
        return 1
}

# Check if we are on the head node.
if ! am_i_login_node ; then
        echo "This script runs on the head node (on this deployment $LOGIN_IP)."
        exit 1
fi

 
# Let's see how many nodes AppScale believes we have.
AS_NUM_HOSTS="$(cat /etc/appscale/masters /etc/appscale/slaves|sort -u|wc -l)"
MASTER="$(cat /etc/appscale/masters|head -n 1)"

# Sanity checks.
if [ $AS_NUM_HOSTS -lt 1 ]; then
        echo "Error: cannot find Database nodes!"
        exit 1
fi
if [ -z "$MASTER" ]; then
        echo "Error: cannot find the master Database node!"
        exit 1
fi
 
# Get the list of Database nodes in this pool.
NUM_HOSTS=0
DB_HOSTS=""
MAX_LOAD=0
MIN_LOAD=-1
M_UNIT=""
REBALANCE="NO"
OLD_KEYS=""
while read -r a x y z ; do
        # Let's record the IP addresses of the nodes, and also the list of
        # the keys (tokens) we are currently using.
        OLD_KEYS="${OLD_KEYS} ${a}"
        if [ -z "${DB_HOSTS}" ]; then
                DB_HOSTS="${x}"
        else
                DB_HOSTS="${DB_HOSTS} ${x}"
        fi

        # No arithmetic with decimal point.
        y=${y%.*}

        # Let's find most loaded and least loaded values.
        if [ ${y} -gt ${MAX_LOAD} ]; then
                MAX_LOAD=${y}
        fi
        if [ ${MIN_LOAD} -lt 0 ]; then
                # First time around, initialize some values.
                MIN_LOAD=${y}
                M_UNIT=${z}
        elif [ ${MIN_LOAD} -gt ${y} ]; then
                MIN_LOAD=${y}
        fi

        # This is the load of the node in measurement unit (ie MB or GB or
        # TB). If we are using different units, we need to rebalance.
        if [ "${M_UNIT}" != "${z}" ]; then
                echo "Difference too big (different units): rebalancing"
                REBALANCE="YES"
        fi

        # Let's query the Cassandra pool (via the master node) and capture
        # the following: 
        #  $8 - the key (token) assigned to the node
        #  $1 - the IP address of the node
        #  $5 - the load (in size) of the node
        #  $6 - the measurement unit of the load (MB, GB, TB)
        # We sort the result to ensure we move tokens around the list.
done < <(ssh $MASTER $CMD ring|grep Up|awk '{print $8, $1, $5, $6}'|sort) 

# Sanity check on what we parsed. Cound the number of nodes that are up
# (ie not moving or down) and see if it is consistent with what we have
# configured.
NUM_HOSTS=$(ssh $MASTER $CMD status|grep ^UN|wc -l)
if [ -z "$DB_HOSTS" ]; then
        echo "Error: cannot find Cassandra pool!"
        exit 1
fi
if [ $AS_NUM_HOSTS -ne $NUM_HOSTS ]; then
        echo "Error: discrepancy in the number of nodes available!"
        exit 1
fi
echo "Found $NUM_HOSTS Cassandra nodes ($DB_HOSTS)"

# We have the load of the node (size in MB, GB or TB). We'll rebalance
# only if the difference between the most loaded and the least loaded node
# is less than $DRIFT %. 
if [ "$REBALANCE" = "NO" ]; then
        # Avoid weird errors while working with 0.
        set +e

        # Calculate DRIFT % of the loaded node, and check it's within
        # distance of the MIN_LOAD node.
        CURR_DRIFT=0
        let $((CURR_DRIFT=(MAX_LOAD * DRIFT) / 100))
        let $((DIFF=MAX_LOAD - MIN_LOAD))
        if [ ${DIFF} -gt ${CURR_DRIFT} ]; then
                echo "Difference too big (${DIFF} ${M_UNIT}): rebalancing"
                REBALANCE="YES"
        fi
        set -e
fi

# Rebalance only if we have more than one node.
if [ ${NUM_HOSTS} -gt 1 -a "${REBALANCE}" = "YES" ]; then
        # Sanity check: make sure we have keys to work on. Some hosts may
        # not have it yet, but at least one should have them.
        NEED_UPGRADE="YES"
        for x in $DB_HOSTS ; do
                # Only newest version of AppScale can do it. 
                if ssh $x "if [ ! -e ${KEY_SAMPLES} ];  then exit 1; fi" ; then 
                        NEED_UPGRADE="NO"
                        break
                fi
        done
        if [ "$NEED_UPGRADE" = "YES" ]; then
                echo "AppScale needs to be upgraded."
                exit 1
        fi

        echo "Rebalancing nodes."

        # Collect samples key per host and order it.
        TMP_FILE="/tmp/rangekeysample.$$"
        echo "" > $TMP_FILE
        for x in $DB_HOSTS ; do
                # Since some hosts may not have the keys yet, let's make
                # subsequent ssh works.
                ssh $x "touch ${KEY_SAMPLES}"

                # Make sure we don't have more than MAX_KEYS.
                ssh $x "tail -n ${MAX_KEYS} -q ${KEY_SAMPLES} > /tmp/pippo$$; mv /tmp/pippo$$ ${KEY_SAMPLES}"

                # Copy the keys over.
                ssh $x "cat ${KEY_SAMPLES}" >> $TMP_FILE
        done
        sort -g  $TMP_FILE > $TMP_FILE.sorted

        # Sliced it amongst the hosts.
        lines="$(cat $TMP_FILE.sorted|wc -l)"
        slice=0
        let $((slice = lines / NUM_HOSTS))
        [ $slice -lt 1 ] && exit 0

        # Inform how many keys we got.
        echo "   working on $lines keys. Each node gets $slice keys." 

        num_key=$slice

        # Loop through the nodes, and assign the new token. This will
        # trigger Cassandra to move data around.
        for x in $DB_HOSTS ; do
                IN_USE="NO"
                key="$(sed -n ${num_key}p $TMP_FILE.sorted)"

                # If the key is already in use, we have to do nothing.
                for y in $OLD_KEYS ; do
                        if [ "$y" = "$key" ]; then
                                echo "   $key already in use, skipping it"
                                IN_USE="YES"
                        fi
                done
                if [ "$IN_USE" = "NO" ]; then
                        echo "   node $x gets token $key"
                        ssh $MASTER "$CMD -h $x move $key" > /dev/null
                fi
                let $((num_key += slice))
        done
fi

# Repair needs to be done before gc_grace_seconds expires to avoid deleted
# rows to resurface on replicas. Cleanup will delete rows no longer
# pertinent to the node (for ecample because of a re-balance).
echo "Repairing and cleaning nodes."
for x in $DB_HOSTS ; do
        echo -n "   working on $x: repairing,"
        ssh $MASTER "$CMD repair -pr ${KEYSPACE} -h $x" > /dev/null
        echo " cleaning."
        ssh $MASTER "$CMD cleanup -h $x" > /dev/null
done
 
# Delete temp files.
rm -f $TMP_FILE $TMP_FILE.sorted
