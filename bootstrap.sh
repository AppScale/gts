#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

# Defaults vaules
BRANCH="master"
USER="AppScale"
TOOLS_BRANCH="master"
TOOLS_USER="AppScale"
UNIT_TEST="n"

usage() {
        echo "Usage: ${0} [-b <branch>][-u <user>][-tu <user>][-tb <branch>][-t]"
        echo
        echo "Options:"
        echo "   -b <branch>       the branch to use for appscale repo (default master)"
        echo "   -u <user>         the user to pull the appscale repo (default AppScale)"
        echo "   -tb <branch>      the branch to use for appscale-tools repo (default master)"
        echo "   -tu <user>        the user to pull the appscale-tools repo (default AppScale)"
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

# Let's get the  command line arguments.
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
        if [ "${1}" = "-tb" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                TOOLS_BRANCH="${1}"
                shift
                continue
        fi
        if [ "${1}" = "-tu" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                TOOLS_USER="${1}"
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


# Let's pull the github repositories.
echo
echo "Will be pulling from github with the following:"
echo "   git clone https://github.com/$USER/appscale.git --branch $BRANCH"
echo "   git clone https://github.com/$TOOLS_USER/appscale-tools.git --branch $TOOLS_BRANCH"
echo "Exit now (ctrl-c) if this is incorrect"
echo
sleep 5
apt-get install -y git
if [ -d appscale ]; then
        APPSCALE_MAJOR="$(sed -n 's/.*\([0-9]\)\.\([0-9][0-9]\)\.[0-9]/\1/gp' VERSION)"
        APPSCALE_MINOR="$(sed -n 's/.*\([0-9]\)\.\([0-9][0-9]\)\.[0-9]/\2/gp' VERSION)"
        if [ -z "$APPSCALE_MAJOR" -o -z "$APPSCALE_MINOR" ]; then
                echo "Cannot determine version of AppScale!"
                exit 1
        fi
        echo
        echo "Found AppScale version $APPSCALE_MAJOR.$APPSCALE_MINOR: upgrading it."
        # This sleep is to allow the user to Ctrl-C in case an upgrade is
        # not wanted.
        sleep 5
        # Let's keep a copy of the old config: we need to move it to avoid
        # questions from dpkg.
        if [ -e /etc/haproxy/haproxy.cfg ]; then
                mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.appscale.old
        fi
        # Remove control file we added before 1.14.
        if [ $APPSCALE_MAJOR -le 1 -a $APPSCALE_MINOR -le 14 ]; then
                rm -f /etc/default/haproxy /etc/init.d/haproxy /etc/default/monit /etc/monitrc
        fi
        (cd appscale; git pull)
        (cd appscale-tools; git pull)
else
        git clone https://github.com/$USER/appscale.git --branch $BRANCH
        git clone https://github.com/$TOOLS_USER/appscale-tools.git --branch $TOOLS_BRANCH
fi

echo "Building AppScale..."
(cd appscale/debian; bash appscale_build.sh)

echo "Building AppScale Tools..." 
(cd appscale-tools/debian; bash appscale_build.sh)

# Run unit tests if asked.
if [ "$UNIT_TEST" = "Y" ]; then
        echo "Running Unit tests"
        (cd appscale; rake)
        (cd appscale-tools; rake)
        echo "Unit tests complete"
fi

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
