#!/bin/bash
#
# Simple script to rebalance the load on a Cassandra pool. This works only for
# AppScale deployment.
#

# Where to find the command to query cassadra.
CMD=/root/appscale/AppDB/cassandra/cassandra/bin/nodetool

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
        echo "This script can only run on the head node $LOGIN_IP"
        exit 1
fi

 
# Let's see how many nodes AppScale believes we have.
AS_NUM_HOSTS="$(cat /etc/appscale/masters /etc/appscale/slaves|sort -u|wc -l)"
MASTER="$(cat /etc/appscale/masters|head -n 1)"
 
# Get the list of Database nodes in this pool.
NUM_HOSTS=0
DB_HOSTS=""
MAX_SIZE=0
CURR_DRIFT=0
M_UNIT=""
REBALANCE="NO"
while read -r a x y z ; do
        # First parameter is the key/token owned by the host.

        # Then we have the node's IP address.
        if [ -z "${DB_HOSTS}" ]; then
                DB_HOSTS="${x}"
        else
                DB_HOSTS="${DB_HOSTS} ${x}"
        fi

        # We then have the load of the node in size first.
        y=${y%.*}
        if [ ${y} -gt ${MAX_SIZE} ]; then
                MAX_SIZE=${y}
                if [ ${MAX_SIZE} -lt ${DRIFT} ]; then
                        CURR_DRIFT=1
                else
                        let $((CURR_DRIFT=( MAX_SIZE * DRIFT) / 100))
                        CURR_DRIFT=${CURR_DRIFT%.*}
                fi
        else
                let $((DIFF=MAX_SIZE - y))
                if [ ${DIFF} -gt ${CURR_DRIFT} ]; then
                        echo "Difference too big (${DIFF} vs ${CURR_DRIFT}): rebalancing"
                        REBALANCE="YES"
                fi
        fi

        # This is the load of the node in measurement unit (ie MB or GB or
        # TB). If we are using different units, we need to rebalance.
        if [ -z "${M_UNIT}" ]; then
                M_UNIT=${z}
        else
                if [ "${M_UNIT}" != "${z}" ]; then
                        echo "Difference too big (different units): rebalancing"
                        REBALANCE="YES"
                fi
        fi

        # All good: we parsed this node.
        let $((NUM_HOSTS += 1))
done < <(ssh $MASTER $CMD status|grep UN|awk '{print $7, $2, $3, $4}'|sort) 
if [ -z "$DB_HOSTS" ]; then
        echo "Cannot find Cassandra pool!"
        exit 1
fi
if [ $AS_NUM_HOSTS -ne $NUM_HOSTS ]; then
        echo "Error: discrepancy in the number of nodes available!"
        exit 1
fi
echo "Found $NUM_HOSTS Cassandra nodes ($DB_HOSTS)"

# Rebalance only if we have more than one node.
if [ ${NUM_HOSTS} -gt 1 -a "${REBALANCE}" = "YES" ]; then
        echo "Rebalancing nodes."

        # Collect samples key per host and order it.
        TMP_FILE="/tmp/rangekeysample.$$"
        echo "" > $TMP_FILE
        for x in $DB_HOSTS ; do
                # Only newest version of AppScale can do it.
                if ! ssh $x "[ ! -e ${KEY_SAMPLES} ] && exit 1" ; then 
                        echo "AppScale needs to be upgraded."
                        exit 1
                fi

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
                key="$(sed -n ${num_key}p $TMP_FILE.sorted)"
                ssh $MASTER $CMD move $key -h $x > /dev/null
                echo "   node $x gets token $key"
                let $((num_key += slice))
        done
fi

# Repair needs to be done before gc_grace_seconds expires to avoid deleted
# rows to resurface on replicas. Cleanup will delete rows no longer
# pertinent to the node (for ecample because of a re-balance).
echo "Repairing and cleaning nodes."
for x in $DB_HOSTS ; do
        echo -n "   working on $x: repairing,"
        ssh $MASTER $CMD repair -pr ${KEYSPACE} -h $x > /dev/null
        echo " cleaning."
        ssh $MASTER $CMD cleanup -h $x > /dev/null
done
 
# Repair DB and delete temp files.
rm -f $TMP_FILE $TMP_FILE.sorted
