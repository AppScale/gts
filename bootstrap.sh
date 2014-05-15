#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

set -e

# Defaults values for repositories and branches.
APPSCALE_REPO="git://github.com/AppScale/appscale.git"
APPSCALE_TOOLS_REPO="git://github.com/AppScale/appscale-tools.git"
APPSCALE_BRANCH="master"
APPSCALE_TOOLS_BRANCH="master"
FORCE_UPGRADE="N"
UNIT_TEST="n"

usage() {
        echo "Usage: ${0} [--repo <repo>][--tools-repo <repo>][-t]"
        echo
        echo "Options:"
        echo "   --repo <repo>            Specify appscale repo (default $APPSCALE_REPO)"
        echo "   --branch <branch>        Specify appscale branch (default $APPSCALE_BRANCH)"
        echo "   --tools-repo <repo>      Specify appscale-tools repo (default $APPSCALE_TOOLS_REPO"
        echo "   --tools-branch <branch>  Specify appscale-tools branch (default $APPSCALE_TOOLS_BRANCH)"
        echo "   --force-upgrade          Force upgrade even if some check fails."
        echo "   -t                       Run unit tests"
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
        if [ "${1}" = "--repo" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                APPSCALE_REPO="${1}"
                shift
                continue
        fi
        if [ "${1}" = "--branch" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                APPSCALE_BRANCH="${1}"
                shift
                continue
        fi
        if [ "${1}" = "--tools-repo" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                APPSCALE_TOOLS_REPO="${1}"
                shift
                continue
        fi
        if [ "${1}" = "--tools-branch" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                APPSCALE_TOOLS_BRANCH="${1}"
                shift
                continue
        fi
        if [ "${1}" = "--force-upgrade" ]; then
                FORCE_UPGRADE="Y"
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
echo "Will be using the follogin github repo:"
echo "git clone ${APPSCALE_REPO} --branch ${APPSCALE_BRANCH}"
echo "git clone ${APPSCALE_TOOLS_REPO} --branch ${APPSCALE_TOOLS_BRANCH}"
echo "Exit now (ctrl-c) if this is incorrect"
echo
sleep 5
apt-get install -y git
if [ -d appscale ]; then
        APPSCALE_MAJOR="$(sed -n 's/.*\([0-9]\)\.\([0-9][0-9]\)\.[0-9]/\1/gp' appscale/VERSION)"
        APPSCALE_MINOR="$(sed -n 's/.*\([0-9]\)\.\([0-9][0-9]\)\.[0-9]/\2/gp' appscale/VERSION)"
        if [ -z "$APPSCALE_MAJOR" -o -z "$APPSCALE_MINOR" ]; then
                echo "Cannot determine version of AppScale!"
                exit 1
        fi
        echo
        echo "Found AppScale version $APPSCALE_MAJOR.$APPSCALE_MINOR: upgrading it."
        # Make sure AppScale is not running.
        MONIT=$(which monit)
        if [ -n "$MONIT" ]; then
                if $MONIT summary |grep controller > /dev/null ; then
                        echo "AppScale is still running: please stop it"
                        [ "$FORCE_UPGRADE" = "Y" ] || exit 1
                elif echo $MONIT |grep local > /dev/null ; then
                        # AppScale is not running but there is a monit
                        # leftover from the custom install.
                        $MONIT quit
                fi
        fi

        # This sleep is to allow the user to Ctrl-C in case an upgrade is
        # not wanted.
        sleep 5
        # Let's keep a copy of the old config: we need to move it to avoid
        # questions from dpkg.
        if [ -e /etc/haproxy/haproxy.cfg ]; then
                mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.appscale.old
        fi
        # Remove control files we added before 1.14, and re-add the
        # default ones.
        if [ $APPSCALE_MAJOR -le 1 -a $APPSCALE_MINOR -le 14 ]; then
                rm -f /etc/default/haproxy /etc/init.d/haproxy /etc/default/monit /etc/monitrc
                if dpkg-query -l haproxy > /dev/null 2> /dev/null ; then
                        apt-get -o DPkg::Options::="--force-confmiss" --reinstall install haproxy
                fi
                if dpkg-query -l monit > /dev/null 2> /dev/null ; then
                        apt-get -o DPkg::Options::="--force-confmiss" --reinstall install monit
                fi
        fi
        (cd appscale; git pull)
        (cd appscale-tools; git pull)
else
        git clone ${APPSCALE_REPO} --branch ${APPSCALE_BRANCH}
        git clone ${APPSCALE_TOOLS_REPO} --branch ${APPSCALE_TOOLS_BRANCH}
fi

echo "Building AppScale..."
(cd appscale/debian; bash appscale_build.sh)

echo "Building AppScale Tools..." 
(cd appscale-tools/debian; bash appscale_build.sh)

# Run unit tests if asked.
if [ "$UNIT_TEST" = "Y" ]; then
        echo "Running Unit tests"
        (cd appscale; rake)
        if [ $? -gt 0 ]; then
            echo "Unit tests failed for appscale!"
            exit 1
        fi
        (cd appscale-tools; rake)
        if [ $? -gt 0]; then
            echo "Unit tests failed for appscale-tools!"
            exit 1
        fi
        echo "Unit tests complete"
fi

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
exit 0
