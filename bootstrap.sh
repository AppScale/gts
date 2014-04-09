#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

# Defaults vaules
BRANCH="master"
USER="AppScale"
DATABASE="cassandra"
UNIT_TEST="n"

usage() {
        echo "Usage: ${0} [-b <branch>][-u <user>][-d <database>][-t]"
        echo
        echo "Options:"
        echo "   -b <branch>       a specific branch to use (default master)"
        echo "   -u <user>         a specific user to pull the fork (default AppScale)"
        echo "   -d <database>     a specific database to user as backend (default cassandra)"
        echo "   -t                run unit tests"
        exit 1
}

echo -n "Checking to make sure you are root..."
if [ "$(id -u)" != "0" ]; then
   echo "Failed" 1>&2
   exit 1
fi
echo "Success"

set -e

# set command line arguments
while [ $# -gt 0 ]; do
        if [ "${1}" = "-b" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                BRANCH="${1}"
                shift
                continue
        fi
        if [ "${1}" = "-u" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                USER="${1}"
                shift
                continue
        fi
        if [ "${1}" = "-d" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                DATABASE="${1}"
                shift
                continue
        fi
        if [ "${1}" = "-t" ]; then 
                UNIT_TEST="Y"
                shift
                continue
        fi
        usage
done


# let's pull the repos
echo
echo "Will be using github branch \"$BRANCH\" for user \"$USER\""
echo "git clone https://github.com/$USER/appscale.git --branch $BRANCH"
echo "git clone https://github.com/$USER/appscale-tools.git --branch $BRANCH"
echo "Exit now (ctrl-c) if this is incorrect"
echo
sleep 3
apt-get install -y git-core
git clone https://github.com/$USER/appscale.git --branch $BRANCH
git clone https://github.com/$USER/appscale-tools.git --branch $BRANCH

# and build AppScale
echo "Building AppScale..."
(cd appscale/debian; bash appscale_build.sh ${DATABASE})

echo "Building AppScale Tools..." 
(cd appscale-tools/debian; bash appscale_build.sh)

# Run unit tests
if [ "$UNIT_TEST" = "Y" ]; then
        echo "Running Unit tests"
        (cd appscale; rake)
        (cd appscale-tools; rake)
        echo "Unit tests complete"
fi

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
