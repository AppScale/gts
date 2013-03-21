#!/bin/bash

APP="/root/appscale/AppDashboard/"
PORT=9000
KEY=`cat /root/appscale/.appscale/secret.key`
echo "GLOBAL_SECRET_KEY = '$KEY'" > /root/appscale/AppDashboard/lib/secret_key.py

echo "Starting dev_appserver on port $PORT serving $APP"

CMD="/usr/local/Python-2.7.3/python /root/appscale/AppServer/dev_appserver.py -p $PORT --cookie_secret $KEY --login_server 192.168.33.168 --admin_console_server  --enable_console --nginx_port 8079 --nginx_host 192.168.33.168 --require_indexes --enable_sendmail --xmpp_path 192.168.33.168 --uaserver_path 192.168.33.168:4343 --datastore_path 192.168.33.168:8888 --history_path /root/brian/AppLoadBalancer_logs/app.datastore.history -a 192.168.33.168 $APP"
echo $CMD
eval $CMD
