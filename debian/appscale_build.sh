#!/bin/bash

set -e
export DIST=`lsb_release -c -s`

cd `dirname $0`/..

if [ ! -e ./debian/changelog.${DIST} ]; then
    echo "${DIST} is not supported."
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

echo "Installing Ubuntu ${DIST} building environment."

apt-get update
apt-get -y install curl wget
curl -d "key=appscale" http://heart-beat.appspot.com/sign

export APPSCALE_HOME_RUNTIME=`pwd`

if [ "$DIST" = "lucid" ]; then
    echo "Running lucid specific commands"
    # install add-apt-repository command
    apt-get -y install python-software-properties
    # add repository
    add-apt-repository "deb http://ppa.launchpad.net/fkrull/deadsnakes/ubuntu lucid main"
    add-apt-repository "deb-src http://ppa.launchpad.net/fkrull/deadsnakes/ubuntu lucid main" 
    add-apt-repository "deb http://archive.canonical.com/ lucid partner"

    # For rabbitmq
    add-apt-repository "deb http://www.rabbitmq.com/debian/ testing main"
    wget -O - http://www.rabbitmq.com/rabbitmq-signing-key-public.asc | sudo apt-key add -

fi

apt-get update

# Solves the localization error messages 
export LANGUAGE=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
locale-gen en_US.UTF-8
dpkg-reconfigure locales

# fix /etc/hosts file for collectd installation
HOSTNAME=`hostname`
if [ `grep "$HOSTNAME" /etc/hosts | wc -l` -eq 0 ]; then
    echo "127.0.1.1 ${HOSTNAME} ${HOSTNAME}.localdomain" >> /etc/hosts
fi


# Install cmake prior to the other packages since seems to fail if installed with the other packages
apt-get install -y cmake

# install package for build
apt-get install -y autoconf automake libtool gcc g++ pkg-config ant maven2\
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


if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for building."
    exit 1
fi

# for distro
PACKAGES=`find debian -regex ".*\/control\.[a-z]+\.${DIST}\$" -exec mawk -f debian/package-list.awk {} +`
apt-get install -y --force-yes ${PACKAGES}
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi
# for general
PACKAGES=`find debian -regex ".*\/control\.[a-z]+\$" -exec mawk -f debian/package-list.awk {} +`
apt-get install -y --force-yes ${PACKAGES}
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi


# remove conflict package
apt-get -y purge haproxy
apt-get -y remove consolekit

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
