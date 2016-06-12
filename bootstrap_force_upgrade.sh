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

echo "Copying database files needed from /etc/appscale to a temporary location /root/database-temp"
mkdir -p /root/database-temp
cp -r /etc/appscale/. /root/database-temp
cd /root/database-temp ; rm -r 2.8.0; rm -r certs; rm environment.yaml; rm home; rm VERSION

echo "Running the bootstrap script with a --force-upgrade"

(cd; cd appscale; bash bootstrap.sh --force-upgrade)
if [ $? -gt 0 ]; then
        echo "Running bootstrap script failed!"
        exit 1
fi

echo "Coping database files back from the temporary location to /etc/appscale."
cd; cp -r /root/database-temp/. /etc/appscale

MASTER_IP=$( cat /etc/appscale/masters )

LOCAL_TOKEN=""
SLAVES_IPS_LENGTH=$( cat /etc/appscale/slaves | wc -l )

get_local_token() {
        if [ "$MASTER_IP" = "$LOCAL_IP" ]; then
                return
        fi

        cat /etc/appscale/slaves | while read line
        do
                index=0
                declare -i index
                if [ "$line" = "$LOCAL_IP" ]; then
                        LOCAL_TOKEN="Expression TBD"
                fi
                index=index+1
        done
}

get_local_token

cd /root/appscale/; cd AppDB/cassandra_env/templates/

for file in *
do
        (sed -i "s/APPSCALE-LOCAL/${LOCAL_IP}/g" $file)
        (sed -i "s/APPSCALE-MASTER/${MASTER_IP}/g" $file)
        (sed -i "s/APPSCALE-TOKEN/${LOCAL_TOKEN}/g" $file)
        (sed -i "s/REPLICATION/1/g" $file)
        (sed -i "s/APPSCALE-JMX-PORT/7070/g" $file)

done

cd; cp /root/appscale/AppDB/cassandra_env/templates/* /opt/cassandra/cassandra/conf/

exit 0
