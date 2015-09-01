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
        echo "   --tag <git-tag>          Use git tag (ie 2.2.0) or 'last' to use the latest release or 'dev' for HEAD"
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

# Empty tag means we use the latest available.
if [ -z "${GIT_TAG}" ]; then
        GIT_TAG="last"
else
        # We don't use Tag and Branch at the same time.
        if [ "${APPSCALE_BRANCH}" != "master" ]; then
                echo "--branch cannot be specified with --tag"
                exit 1
        fi
fi

# A tag of 'dev' means don't use tag.
if [ "${GIT_TAG}" = "dev" ]; then
        GIT_TAG=""
fi

# At this time we expect to be installed in $HOME.
cd $HOME

# Let's pull the github repositories.
echo
echo "Will be using the following github repo:"
echo "Repo: ${APPSCALE_REPO} Branch: ${APPSCALE_BRANCH}"
echo "Repo: ${APPSCALE_TOOLS_REPO} Branch: ${APPSCALE_TOOLS_BRANCH}"
echo "Exit now (ctrl-c) if this is incorrect"
echo

sleep 5
apt-get update
apt-get install -y git
if [ ! -d appscale ]; then
        # We split the commands, to ensure it fails if branch doesn't
        # exists (Precise git will not fail otherwise).
        git clone ${APPSCALE_REPO} appscale
        (cd appscale; git checkout ${APPSCALE_BRANCH})
        git clone ${APPSCALE_TOOLS_REPO} appscale-tools
        (cd appscale-tools; git checkout ${APPSCALE_TOOLS_BRANCH})

        # Use tags if we specified it.
        if [ -n "$GIT_TAG" -a "${APPSCALE_BRANCH}" = "master" ]; then
                if [ "$GIT_TAG" = "last" ]; then
                        GIT_TAG="$(cd appscale; git tag|tail -n 1)"
                fi
                (cd appscale; git checkout "$GIT_TAG")
                (cd appscale-tools; git checkout "$GIT_TAG")
        fi
fi

# Since the last step in appscale_build.sh is to create the certs directory,
# its existence indicates that appscale has already been installed.
if [ -d appscale/.appscale/certs ]; then
        # For upgrade, we don't switch across branches.
        if [ "${APPSCALE_BRANCH}" != "master" ]; then
                echo "Cannot use --branch when upgrading"
                exit 1
        fi
        if [ "${APPSCALE_TOOLS_BRANCH}" != "master" ]; then
                echo "Cannot use --tools-branch when upgrading"
                exit 1
        fi
        if [ -z "$GIT_TAG" ]; then
                echo "Cannot use --tag dev when upgrading"
                exit 1
        fi

        APPSCALE_MAJOR="$(sed -n 's/.*\([0-9]\)\+\.\([0-9]\)\+\.[0-9]/\1/gp' appscale/VERSION)"
        APPSCALE_MINOR="$(sed -n 's/.*\([0-9]\)\+\.\([0-9]\)\+\.[0-9]/\2/gp' appscale/VERSION)"
        if [ -z "$APPSCALE_MAJOR" -o -z "$APPSCALE_MINOR" ]; then
                echo "Cannot determine version of AppScale!"
                exit 1
        fi

        # This is an upgrade, so let's make sure we use a tag that has
        # been passed, or the last one available. Let's fetch all the
        # available tags first.
        (cd appscale; git fetch origin)
        (cd appscale-tools; git fetch origin)
        if [ "$GIT_TAG" = "last" ]; then
                GIT_TAG="$(cd appscale; git tag|tail -n 1)"
        fi

        # We can pull a tag only if we are on the master branch.
        CURRENT_BRANCH="$(cd appscale; git branch --no-color|grep '^*'|cut -f 2 -d ' ')"
        if [ "${CURRENT_BRANCH}" != "master" ]; then
                CURRENT_BRANCH="$(cd appscale; git tag -l | grep $(git describe))"
                if [ "${CURRENT_BRANCH}" = "${GIT_TAG}" ]; then
                        echo "AppScale is at the latest release already."
                        exit 0
                fi
        fi

        # If CURRENT_BRANCH is empty, then we are not on master, and we
        # are not on a released version: we don't upgrade then.
        if [ -z "${CURRENT_BRANCH}" ]; then
                echo "Error: git repository is not 'master' or a released version."
                exit 1
        fi

        echo
        echo "Found AppScale version $APPSCALE_MAJOR.$APPSCALE_MINOR. An upgrade"
        echo "to the latest version available will be attempted in 5 seconds."
        sleep 5

        # Make sure AppScale is not running.
        MONIT=$(which monit)
        if $MONIT summary |grep controller > /dev/null ; then
                echo "AppScale is still running: please stop it"
                [ "$FORCE_UPGRADE" = "Y" ] || exit 1
        elif echo $MONIT |grep local > /dev/null ; then
                # AppScale is not running but there is a monit
                # leftover from the custom install.
                $MONIT quit
        fi

        # Let's keep a copy of the old config: we need to move it to avoid
        # questions from dpkg.
        if [ -e /etc/haproxy/haproxy.cfg ]; then
                mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.appscale.old
        fi

        # Remove outdated appscale-controller and appscale-progenitor.
        if [ $APPSCALE_MAJOR -le 2 -a $APPSCALE_MINOR -le 2 ]; then
                rm -f /etc/init.d/appscale-controller
                rm -f /etc/init.d/appscale-progenitor
                update-rc.d -f appscale-progenitor remove || true
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


        # Let's upgrade the repository: if GIT_TAG is empty we are on HEAD.
        if [ -n "${GIT_TAG}" ]; then
                (cd appscale; git checkout "$GIT_TAG")
                (cd appscale-tools; git checkout "$GIT_TAG")
        else
                (cd appscale; git pull)
                (cd appscale-tools; git pull)
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
