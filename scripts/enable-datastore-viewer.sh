#!/bin/bash
#
# Enable the datastore viewer, reload nginx and configure the firewall.
usage() {
        echo
        echo "Usage: $0 <APP-ID> [-i <IP>]"
        echo
        echo "Enable the datatore viewer for the given application."
        echo "WARNING: the datastore viewer is not protected! Anyone can browse your data."
        echo "WARNING: restricting by IP should be used judiciously."
        echo
        echo "Options:"
        echo "     -h        this message"
        echo "     -i <IP>   allow connections only from this IP (default is open)"
        echo
}

# Parse command line arguments
APP_ID=""
TRUSTED_IP=""
while [ $# -gt 0 ]; do
        if [ "$1" = "-h" -o "$1" = "-help" -o "$1" = "--help" ]; then
                usage
                exit 1
        fi
        if [ -n "$1" -a "$1" = "-i" ]; then
                if [ -n "$2" ]; then
                        TRUSTED_IP="$2"
                        shift;shift
                        continue
                else
                        usage
                        exit 1
                fi
        fi
        if [ -n "$1" ]; then
                APP_ID=$1
                shift
                continue
        fi
done
if [ ! -n "$APP_ID" ]; then
	usage
	exit 1
fi

# Sanity checks.
if [ ! -e /etc/nginx/sites-enabled ]; then
        echo "ERROR: Cannot find nginx configurations. Is this an AppScale deployment?"
        exit 1
fi

# Find host and port of the admin server
ADMIN_SERVER_PORT=""
APPENGINE_IP=""
for ip in $(cat /etc/appscale/all_ips); do
        OUTPUT=$(ssh $ip -i /etc/appscale/keys/cloud1/*.key 'ps ax | grep appserver \
               | grep -E "(grep|$APP_ID)" | grep -- "--admin_port" \
               | sed "s;.*--admin_port \([0-9]*\).*/var/apps/\(.*\)/app .*;\1 \2;g" \
               | sort -ru')
        for i in $OUTPUT ; do
                if [ "$i" = "$APP_ID" ]; then
                        continue
                else
                        ADMIN_SERVER_PORT=$i
                        APPENGINE_IP=$ip
                        break
                fi
        done
done
if [ ! -n "$ADMIN_SERVER_PORT" -o ! -n "$APPENGINE_IP" ]; then
	echo "ERROR: Cannot find appengine node with admin server running on it"
	exit 1
fi

# Find free port for the viewer
VIEWER_PORT="8100"
while [[ $(lsof -i :$VIEWER_PORT) ]]; do
        let $((VIEWER_PORT += 1))
done

# Determine allow statement for the nginx configuration
if [ -n "$TRUSTED_IP" ]; then
	ALLOW="allow $TRUSTED_IP; deny all;"
else
	ALLOW="allow all;"
fi

# Prepare the nginx config snippet.
CONFIG="
upstream datastore_viewer_$VIEWER_PORT {
  server $APPENGINE_IP:$ADMIN_SERVER_PORT;
}
map \$scheme \$ssl {
    default off;
    https on;
}

server {
    listen $VIEWER_PORT;
    server_name datastore_viewer_server;
    location / {
      $ALLOW
      proxy_pass http://datastore_viewer_$VIEWER_PORT;
    }
}
"

if [ -e /etc/nginx/sites-enabled/appscale-${APP_ID}.conf ]; then
        echo "$CONFIG" > /etc/nginx/sites-enabled/appscale-${APP_ID}_datastore_viewer.conf
        service nginx reload
        sed -i "/AppController/ i\
iptables -A INPUT -p tcp --dport $VIEWER_PORT -j ACCEPT   # Enable datastore viewer" $APPSCALE_HOME/firewall.conf
	    bash $APPSCALE_HOME/firewall.conf
        echo "Datastore viewer enabled for ${APP_ID} at http://$(cat /etc/appscale/my_public_ip):${VIEWER_PORT}. Allowed IP: $TRUSTED_IP."
else
        echo "Cannot find configuration for ${APP_ID}."
fi
