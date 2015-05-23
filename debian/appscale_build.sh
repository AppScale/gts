#!/bin/bash

set -e
export DIST="$(lsb_release -c -s)"
export VENDOR="$(lsb_release -i -s)"

cd `dirname $0`/..

if [ ! -e ./debian/changelog.${DIST} ]; then
    echo "${VENDOR}/${DIST} is not supported."
    exit 1
fi
if [ ! -e VERSION ]; then
    echo "Please checkout whole appscale branch."
    exit 1
fi

supported_dbs=(cassandra)
if [ $1 ]; then
    found=false
    for i in "${supported_dbs[@]}"
    do
        if [ "$i" == $1 ] ; then
            found=true
        fi
    done
    if ! $found ; then
      echo "$1 is not a supported database."
      exit 1
    fi
fi

if [ $2 ]; then
    echo "Usage: bash appscale_build.sh <optional: one database name>"
    exit 1
fi

echo -n "Installing building environment for ${VENDOR}/${DIST} "


apt-get update
apt-get -y install curl wget
curl -d "key=appscale" http://heart-beat.appspot.com/sign || true

export APPSCALE_HOME_RUNTIME=`pwd`

# This will install dependencies from control.core and the specific
# distributions.
PACKAGES="$(find debian -regex ".*\/control\.[a-z]+\.${DIST}\$" -exec mawk -f debian/package-list.awk {} +) $(find debian -regex ".*\/control\.[a-z]+\$" -exec mawk -f debian/package-list.awk {} +)"

if ! apt-get install -y --force-yes ${PACKAGES}; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi

# This will remove all the conflicts packages.
PACKAGES="$(find debian -regex ".*\/control\.[a-z]+\.${DIST}\$" -exec mawk -f debian/remove-list.awk {} +) $(find debian -regex ".*\/control\.[a-z]+\$" -exec mawk -f debian/remove-list.awk {} +)"

if ! apt-get remove --purge -y --force-yes ${PACKAGES}; then
    echo "Fail to remove conflicting packages"
    exit 1
fi

# If we have an option to switch ruby, let's make sure we use 1.9.
if [ -n "$(apt-cache search ruby-switch)" ]; then
        echo "Make sure ruby1.9 is used"
        apt-get install -y ruby-switch
        ruby-switch --set ruby1.9
fi

if [ $1 ]; then
    echo "Installing AppScale with $1 as the only supported database."
    bash debian/appscale_install.sh core || exit 1
    bash debian/appscale_install.sh $1 || exit 1
else
    echo "Installing full AppScale image"
    bash debian/appscale_install.sh all || exit 1
fi

if ! mkdir -p $APPSCALE_HOME_RUNTIME/.appscale/certs; then
    echo "Unable to complete AppScale installation."
    exit 1
fi
echo "AppScale installation completed successfully!"
