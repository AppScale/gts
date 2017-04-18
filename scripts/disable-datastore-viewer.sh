#!/bin/bash
#
# Disable the datastore viewer, reload nginx and configure the firewall.
set -e
set -u

usage() {
    echo
    echo "Usage: $0 <APP-ID>"
    echo
    echo "Disable the datatore viewer for the given application."
    echo
    echo "Options:"
    echo "     -h    this message"
    echo
}

# Parse command line arguments
APP_ID=""
while [ $# -gt 0 ]; do
    if [ "$1" = "-h" -o "$1" = "-help" -o "$1" = "--help" ]; then
        usage
        exit 1
    fi
    if [ -n "$1" ]; then
        APP_ID=$1
        shift
        continue
    fi
done
if [ -z "$APP_ID" ]; then
    usage
    exit 1
fi

# Sanity checks.
if [ ! -e /etc/nginx/sites-enabled ]; then
    echo "ERROR: Cannot find nginx configurations. Is this an AppScale deployment?"
    exit 1
fi

VIEWER_CONF=/etc/nginx/sites-enabled/appscale-${APP_ID}_datastore_viewer.conf
if [ -e "$VIEWER_CONF" ]; then
    VIEWER_PORT=$(grep listen ${VIEWER_CONF} | sed -r "s/.*listen ([0-9]+).*/\1/")
    rm ${VIEWER_CONF}
    nginx -t
    service nginx reload
    sed -i "/${VIEWER_PORT}.*Enable datastore viewer/d" $APPSCALE_HOME/firewall.conf
    bash $APPSCALE_HOME/firewall.conf
    echo "Datastore viewer disabled for ${APP_ID}"
else
    echo "Cannot find datastore viewer for ${APP_ID}."
fi
