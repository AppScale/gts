#!/bin/bash
#
# Simple script for upgrading AppScale to one of release versions.
# Author: AppScale Team <support@appscale.com>

set -e

APPSCALE_REPO="git://github.com/AppScale/appscale.git"
APPSCALE_TOOLS_REPO="git://github.com/AppScale/appscale-tools.git"
AGENTS_REPO="git://github.com/AppScale/appscale-agents.git"
THIRDPARTIES_REPO="git://github.com/AppScale/appscale-thirdparties.git"
GIT_TAG="last"
UNIT_TEST="N"

usage() {
    echo "Usage: ${0} [--tag <git-tag>] [-t]"
    echo
    echo "Options:"
    echo "   --tag <git-tag>    Git tag (e.g.: 3.7.2) to upgrade to."
    echo "                      Default: '${GIT_TAG}' (use the latest release)."
    echo "   -t                 Run unit tests"
    exit 1
}

version_ge() {
    test "$(printf '%s\n' "$@" | sort -V | tail -1)" = "$1"
}


echo -n "Checking to make sure you are root..."
if [ "$(id -u)" != "0" ]; then
   echo "Failed" 1>&2
   exit 1
fi
echo "Success"

echo -n "Checking to make sure \$HOME is /root..."
if [ "$HOME" != "/root" ]; then
   echo "Failed"
   exit 1
fi
echo "Success"

# Let's get the command line argument.
while [ $# -gt 0 ]; do
    if [ "${1}" = "--tag" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        GIT_TAG="${1}";
        shift; continue
    fi
    if [ "${1}" = "-t" ]; then
        UNIT_TEST="Y"
        shift; continue
    fi
    echo -e "\nParameter '$1' is not recognized\n"
    usage
done


# Determine the latest git tag on the AppScale/appscale repo
if [ "$GIT_TAG" = "last" ]; then
    echo "Determining the latest tag in AppScale/appscale repo"
    GIT_TAG=$(curl --fail https://api.github.com/repos/appscale/appscale/releases/latest \
              | python -m json.tool | grep '"tag_name"' \
              | awk -F ':' '{ print $2 }' | tr --delete ' ,"')
fi
VERSION="${GIT_TAG}"

echo
echo "Will be using the following github repos:"
echo "AppScale:        ${APPSCALE_REPO} - Tag ${GIT_TAG}"
echo "AppScale-Tools:  ${APPSCALE_TOOLS_REPO} - Tag ${GIT_TAG}"
if version_ge ${VERSION} 3.8.0; then echo "Cloud-Agents:    ${AGENTS_REPO} - Tag ${GIT_TAG}"; fi
if version_ge ${VERSION} 4.0.0; then echo "Thirdparties:    ${THIRDPARTIES_REPO} - Tag ${GIT_TAG}"; fi
echo "Exit now (ctrl-c) if this is incorrect"
echo
sleep 5

# Wait up to 30 seconds for the package lists lock to become available.
lock_wait_start=$(date +%s)
printed_status=false
while fuser /var/lib/apt/lists/lock; do
    if [ "${printed_status}" = false ]; then
        echo "Waiting for another process to update package lists"
        printed_status=true
    fi
    current_time=$(date +%s)
    elapsed_time=$((current_time - lock_wait_start))
    if [ "${elapsed_time}" -gt 30 ]; then break; fi
    sleep 1
done
apt-get update

# Wait up to 2 min for the dpkg lock to become available.
lock_wait_start=$(date +%s)
printed_status=false
while fuser /var/lib/dpkg/lock; do
    if [ "${printed_status}" = false ]; then
        echo "Waiting for another process to update packages"
        printed_status=true
    fi
    current_time=$(date +%s)
    elapsed_time=$((current_time - lock_wait_start))
    if [ "${elapsed_time}" -gt 120 ]; then break; fi
    sleep 1
done
apt-get install -y git


if [ -d /etc/appscale/certs ]; then
    CURRENT_VERSION=$(cat /root/appscale/VERSION | grep -oE "[0-9]+\.[0-9]+\.[0-9]+")
    if [ -z "${CURRENT_VERSION}" ]; then
        echo "Cannot determine version of AppScale!"
        exit 1
    fi

    # Make sure AppScale is not running.
    if systemctl is-active appscale-controller > /dev/null ; then
        echo "AppScale is still running: please stop it"
        [ "${FORCE_UPGRADE}" = "Y" ] || exit 1
    fi

    # Let's keep a copy of the old config: we need to move it to avoid
    # questions from dpkg.
    if [ -e /etc/haproxy/haproxy.cfg ]; then
        mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.appscale.old
    fi

    # Remove outdated init scripts.
    [ ! -f "/etc/init.d/appscale-controller" ] || rm -fv "/etc/init.d/appscale-controller"
    [ ! -f "/etc/init.d/appscale-progenitor" ] || rm -fv "/etc/init.d/appscale-progenitor"
    [ ! -f "/etc/init.d/appscale-unmonit" ]    || rm -fv "/etc/init.d/appscale-unmonit"

    echo "Found AppScale version ${CURRENT_VERSION}. "\
         "An upgrade to the ${GIT_TAG} version will be attempted in 5 seconds."
    echo "Exit now (ctrl-c) if this is incorrect"
    sleep 5
else
    echo "No previous AppScale installation was found. Installing it from scratch."
fi


declare -A REPOS=(
    ["appscale"]="${APPSCALE_REPO}"
    ["appscale-tools"]="${APPSCALE_TOOLS_REPO}"
)
if version_ge "${VERSION}" 3.8.0; then REPOS+=(["appscale-agents"]="${AGENTS_REPO}"); fi
if version_ge "${VERSION}" 4.0.0; then REPOS+=(["appscale-thirdparties"]="${THIRDPARTIES_REPO}"); fi

# At this time we expect to be installed in $HOME.
cd $HOME


echo "Ensuring all appscale repos are pulled and checked out to the tag"
for repo_name in "${!REPOS[@]}"; do
    repo="${REPOS[$repo_name]}"
    if [ -d "/root/${repo_name}" ]; then
        cd ${repo_name}
        # <Repo directory context>...
        remote=$(git remote -v | grep "${repo} " | head -1 | awk '{ print $1 }')
        if [ -z "${remote}" ]; then
            remote="upgrade-$(date +%Y-%m-%d_%H-%M-%S)"
            git remote add ${remote} "${repo}"
        fi
        git fetch ${remote} -t
        current_branch="$(git branch --no-color | grep '^*' | cut -f 2 -d ' ')"
        echo "Checking out /root/${repo_name} from '${current_branch}' to '${GIT_TAG}'"
        if ! git checkout "tags/${GIT_TAG}"; then
            echo "Please stash your local unsaved changes at "\
                 "/root/${repo_name} and checkout the version of AppScale "\
                 "you are currently using to fix this error."
            echo "e.g.: git stash; git checkout tags/${GIT_TAG}"
            exit 1
        fi
        # ...</Repo directory context>
        cd $HOME
    else
        git clone "${repo}" ${repo_name}
        (cd ${repo_name}; git checkout "tags/${GIT_TAG}")
    fi
done


echo -n "Building AppScale..."
if ! (cd appscale/debian; bash appscale_build.sh) ; then
    echo "Failed to upgrade AppScale core"
    exit 1
fi

if version_ge ${VERSION} 3.8.0; then
    echo -n "Installing AppScale Agents..."
    if ! (cd appscale-agents/; make install-no-venv) ; then
        echo "Failed to upgrade AppScale Agents"
        exit 1
    fi
fi

echo -n "Building AppScale Tools..." 
if ! (cd appscale-tools/debian; bash appscale_build.sh) ; then
    echo "Failed to upgrade AppScale Tools"
    exit 1
fi

if version_ge ${VERSION} 4.0.0; then
    echo -n "Downloading Thirdparty artifacts..."
    if ! (cd appscale-thirdparties/; bash install_all.sh) ; then
        echo "Failed to upgrade Thirdparties software"
        exit 1
    fi
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

# Let's source the profiles so this image can be used right away.
. /etc/profile.d/appscale.sh

echo "**********************************"
echo "AppScale is upgraded to ${GIT_TAG}"
echo "**********************************"
exit 0
