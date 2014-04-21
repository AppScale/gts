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

# install dependencies for core and specific distro
PACKAGES="$(find debian -regex ".*\/control\.[a-z]+\.${DIST}\$" -exec mawk -f debian/package-list.awk {} +) $(find debian -regex ".*\/control\.[a-z]+\$" -exec mawk -f debian/package-list.awk {} +)"
apt-get install -y --force-yes ${PACKAGES}
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi

# if we have an option to switch ruby, let's make sure we use 1.8
if apt-cache search ruby-switch 2> /dev/null > /dev/null ; then
        echo "Make sure ruby1.8 is used"
        apt-get install -y ruby-switch
        ruby-switch --set ruby1.8
fi

# install package for build
apt-get install -y autoconf automake libtool gcc g++ pkg-config ant\
 rsync ntp\
 build-essential bison flex byacc unzip bzip2\
 libc6-dev subversion\
 erlang\
 dpkg-dev dh-make debhelper fakeroot\
 python-dev libssl-dev\
 libevent-dev\
 ruby1.8-dev\
 zlib1g-dev\
 libexpat1-dev\
 libcppunit-dev\
 libbz2-dev libreadline-dev\
 libxml2-dev

if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for building."
    exit 1
fi

# remove conflict package
if [ $1 ]; then
    echo "Installing AppScale with $1 as the only supported database."
    bash debian/appscale_install.sh core || exit 1
    bash debian/appscale_install.sh $1 || exit 1
else
    echo "Installing full AppScale image"
    bash debian/appscale_install.sh all || exit 1
fi

mkdir -p $APPSCALE_HOME_RUNTIME/.appscale/certs

if [ $? -ne 0 ]; then
    echo "Unable to complete AppScale installation."
    exit 1
fi
echo "AppScale installation completed successfully!"
