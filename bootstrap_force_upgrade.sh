#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

exec &>>/var/log/appscale/bootstrap-upgrade.log

# Let's get the  command line arguments.
while [ $# -gt 0 ]; do
        if [ "${1}" = "--local-ip" ]; then
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                LOCAL_IP="${1}"
                shift
                continue
        fi
        usage
done

echo "Copying database files needed from /etc/appscale to a temporary directory before running bootstrap script."
TEMPDIR=`mktemp -d`
echo $TEMPDIR
cp -r /etc/appscale/. $TEMPDIR
(cd $TEMPDIR; rm -r 2.8.0; rm -r certs; rm environment.yaml; rm home; rm VERSION)

echo "Running the bootstrap script with a --force-upgrade."

(cd ~/appscale; bash bootstrap.sh --force-upgrade)
if [ $? -gt 0 ]; then
        echo "Running bootstrap script failed!"
        exit 1
fi

echo "Coping database files back from the temporary location to /etc/appscale."
(cp -r $TEMPDIR/* /etc/appscale/)

MASTER_IP=$( cat /etc/appscale/masters )
# Local token is not needed currently for this upgrade process so empty token is passed.
LOCAL_TOKEN=""

echo "Running python script to set up Cassandra config files."
(python ~/appscale/scripts/setup_cassandra_config_files.py --local-ip $LOCAL_IP --master-ip $MASTER_IP --local-token $LOCAL_TOKEN --replication 1 --jmx-port 7070)
if [ $? -gt 0 ]; then
        echo "Python script to set up Cassandra config files failed!"
        exit 1
fi

rm -rf $TEMPDIR
echo "Completed Bootstrap process and restored the database files needed for the upgrade script."
exit 0
