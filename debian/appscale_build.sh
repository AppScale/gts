#!/bin/bash

DIST=`lsb_release -c -s`

cd `dirname $0`/..

if [ ! -e ./debian/changelog.${DIST} ]; then
    echo "${DIST} is not supported."
    exit 1
fi
if [ ! -e VERSION ]; then
    echo "Please checkout whole appscale branch."
    exit 1
fi

echo "Installing Ubuntu ${DIST} building environment."

apt-get -y install curl
curl -d "key=appscale" http://heart-beat.appspot.com/sign

export APPSCALE_HOME_RUNTIME=`pwd`

if [ "$DIST" = "lucid" ]; then
    # install add-apt-repository command
    apt-get -y install python-software-properties
    # add repository
    add-apt-repository ppa:fkrull/deadsnakes
fi

apt-get update

# Accept the sun licencing agreement 
echo sun-java5-jdk shared/accepted-sun-dlj-v1-1 select true | /usr/bin/debconf-set-selections
echo sun-java5-jre shared/accepted-sun-dlj-v1-1 select true | /usr/bin/debconf-set-selections
echo sun-java6-jdk shared/accepted-sun-dlj-v1-1 select true | /usr/bin/debconf-set-selections
echo sun-java6-jre shared/accepted-sun-dlj-v1-1 select true | /usr/bin/debconf-set-selections

# Solves the localization error messages 
export LANGUAGE=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
locale-gen en_US.UTF-8
dpkg-reconfigure locales

# fix /etc/hosts file for collectd installation
HOSTNAME=`hostname`
if [ `grep "$HOSTNAME" /etc/hosts | wc -l` -eq 0 ]; then
    echo "127.0.1.1 $HOSTNAME" >> /etc/hosts
fi

# By default MySQL prompts the user for a password when installing
# We temporarily set the frontend to noninteractive so it doesn't prompt us
export DEBIAN_FRONTEND=noninteractive
apt-get install -y mysql-server-5.0
# Change it back since this can affect the installation of other packages (e.g. java)
export DEBIAN_FRONTEND=''

# install runtime dependency
# for distro
PACKAGES=`find debian -regex ".*\/control\.[a-z]+\.${DIST}\$" -exec mawk -f debian/package-list.awk {} +`
apt-get install -y ${PACKAGES}
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi
# for general
PACKAGES=`find debian -regex ".*\/control\.[a-z]+\$" -exec mawk -f debian/package-list.awk {} +`
apt-get install -y ${PACKAGES}
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for runtime."
    exit 1
fi

# Install cmake prior to the other packages since seems to fail if installed with the other packages
apt-get install -y cmake

# install package for build
apt-get install -y autoconf automake libtool gcc g++ pkg-config ant maven2\
 doxygen graphviz rsync tcl-dev python-tk tk8.4-dev ntp cvs wget\
 bzr xterm screen build-essential bison flex byacc unzip bzip2\
 libc6-dev subversion\
 erlang\
 dpkg-dev dh-make debhelper fakeroot\
 python-dev libssl-dev\
 libevent-dev\
 ruby1.8-dev\
 thin1.8\
 unixodbc-dev\
 zlib1g-dev\
 liblog4cpp5-dev libexpat1-dev\
 libncurses5-dev\
 libbz2-dev libreadline-dev libgdbm-dev swig screen\
 libsqlite3-dev\
 libcppunit-dev\
 libcairo2-dev libpango1.0-dev libxml2-dev libart-2.0-2

if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for building."
    exit 1
fi


# distro specific build environment
if [ "${DIST}" = "jaunty" ]; then
    apt-get install -y libboost1.37-dev
elif [ "${DIST}" = "karmic" -o "${DIST}" = "lucid" ]; then
    apt-get install -y libboost1.40-dev
fi
if [ $? -ne 0 ]; then
    echo "Fail to install depending packages for building."
    exit 1
fi

# remove conflict package
apt-get -y purge haproxy

# install scripts

bash debian/appscale_install.sh all
if [ $? -ne 0 ]; then
    echo "Unable to complete AppScale installation."
    exit 1
fi
echo "AppScale installation completed successfully!"
