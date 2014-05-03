#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

# Defaults vaules
BRANCH="master"
USER="AppScale"
UNIT_TEST="n"

usage() {
        echo "Usage: ${0} [-b <branch>][-u <user>][-t]"
        echo
        echo "Options:"
        echo "   -b <branch>       a specific branch to use (default master)"
        echo "   -u <user>         a specific user to pull the fork (default AppScale)"
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
if [ -d appscale ]; then
        echo
        echo "Found previous AppScale installation: upgrading it"
        sleep 5
        # keep a copy of the old config: we need to move it to avoid
        # questions
        if [ -e /etc/haproxy/haproxy.cfg ]; then
                mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.appscale.old
        fi
        # remove control file we added before 1.14.
        if [ $(sed  -n 's/.*1.\([0-9][0-9]\)\.[0-9]/\1/gp' VERSION) -le 14 ]; then
                rm -f /etc/default/haproxy /etc/init.d/haproxy /etc/default/monit
        fi
        (cd appscale; git pull)
        (cd appscale-tools; git pull)
else
        git clone https://github.com/$USER/appscale.git --branch $BRANCH
        git clone https://github.com/$USER/appscale-tools.git --branch $BRANCH
fi

# and build AppScale
echo "Building AppScale..."
(cd appscale/debian; bash appscale_build.sh)

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
