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
GIT_TAG=""

usage() {
        echo "Usage: ${0} [--repo <repo>][--tools-repo <repo>][-t]"
        echo
        echo "Options:"
        echo "   --repo <repo>            Specify appscale repo (default $APPSCALE_REPO)"
        echo "   --branch <branch>        Specify appscale branch (default $APPSCALE_BRANCH)"
        echo "   --tools-repo <repo>      Specify appscale-tools repo (default $APPSCALE_TOOLS_REPO"
        echo "   --tools-branch <branch>  Specify appscale-tools branch (default $APPSCALE_TOOLS_BRANCH)"
        echo "   --force-upgrade          Force upgrade even if some check fails."
        echo "   --tag <git-tag>          Use specific git tag (ie 2.2.0) or 'last' to use the latest release"
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
        if [ "${1}" = "--tag" ]; then 
                shift
                if [ -z "${1}" ]; then
                        usage
                fi
                GIT_TAG="${1}"
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

# At this time we expect to be installed in $HOME.
cd $HOME

# Let's pull the github repositories.
echo
echo "Will be using the following github repo:"
echo "git clone ${APPSCALE_REPO} --branch ${APPSCALE_BRANCH}"
echo "git clone ${APPSCALE_TOOLS_REPO} --branch ${APPSCALE_TOOLS_BRANCH}"
echo "Exit now (ctrl-c) if this is incorrect"
echo

sleep 5
apt-get update
apt-get install -y git
if [ ! -d appscale ]; then
        git clone ${APPSCALE_REPO} --branch ${APPSCALE_BRANCH}
        git clone ${APPSCALE_TOOLS_REPO} --branch ${APPSCALE_TOOLS_BRANCH}

        # Use tags if we specified it.
        if [ -n "$GIT_TAG" ]; then
                if [ "$GIT_TAG" = "last" ]; then
                        GIT_TAG="$(cd appscale; git tag|tail -n 1)"
                fi
                (cd appscale; git checkout "$GIT_TAG")
                (cd appscale-tools; git checkout "$GIT_TAG")
        fi
fi

echo -n "Building AppScale..."
if ! (cd appscale/debian; bash appscale_build.sh) ; then
        echo "failed!"
        exit 1
fi

echo -n "Building AppScale Tools..." 
if ! (cd appscale-tools/debian; bash appscale_build.sh) ; then
        echo "failed!"
        exit 1
fi

# Run unit tests if asked.
if [ "$UNIT_TEST" = "Y" ]; then
        echo "Running Unit tests"
        (cd appscale; rake)
        if [ $? -gt 0 ]; then
            echo "Unit tests failed for appscale!"
            exit 1
        fi
        (cd appscale-tools; rake)
        if [ $? -gt 0 ]; then
            echo "Unit tests failed for appscale-tools!"
            exit 1
        fi
        echo "Unit tests complete"
fi

# Let's source the profles so this image can be used right away.
. /etc/profile.d/appscale.sh
. /etc/profile.d/appscale-tools.sh

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
exit 0
