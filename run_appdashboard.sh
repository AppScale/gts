#!/bin/bash

APP="/root/appscale/AppDashboard/"
PORT=9000
KEY=`cat /root/appscale/.appscale/secret.key`
echo "GLOBAL_SECRET_KEY = '$KEY'" > /root/appscale/AppDashboard/lib/secret_key.py
IPADDR=`cat /etc/appscale/my_public_ip`

echo "Starting dev_appserver on port $PORT serving $APP"

CMD="/usr/local/Python-2.7.3/python /root/appscale/AppServer/dev_appserver.py -p $PORT --cookie_secret $KEY --login_server $IPADDR --admin_console_server  --enable_console --nginx_port 8079 --nginx_host $IPADDR --require_indexes --enable_sendmail --xmpp_path $IPADDR --uaserver_path $IPADDR:4343 --datastore_path $IPADDR:8888 --history_path /root/brian/AppLoadBalancer_logs/app.datastore.history -a $IPADDR $APP"
echo $CMD
eval $CMD
