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

# Let's make sure we use ruby 1.9.
if [ "${DIST}" = "precise" ]; then
        apt-get install -y ruby1.9.1 ruby1.9.1-dev rubygems1.9.1 irb1.9.1 \
            ri1.9.1 rdoc1.9.1 build-essential libopenssl-ruby1.9.1 libssl-dev \
            zlib1g-dev
        update-alternatives --install /usr/bin/ruby ruby /usr/bin/ruby1.9.1 400 \
            --slave   /usr/share/man/man1/ruby.1.gz ruby.1.gz \
                          /usr/share/man/man1/ruby1.9.1.1.gz \
            --slave   /usr/bin/ri ri /usr/bin/ri1.9.1 \
            --slave /usr/bin/irb irb /usr/bin/irb1.9.1 \
            --slave /usr/bin/rdoc rdoc /usr/bin/rdoc1.9.1
elif [ -n "$(apt-cache search ruby-switch)" ]; then
        echo "Make sure ruby1.9 is used"
        apt-get install -y ruby rubygems ruby-switch
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
