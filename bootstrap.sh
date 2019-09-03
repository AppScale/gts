#!/bin/bash
#
# Simple script to install AppScale.
# Author: AppScale Team <support@appscale.com>

set -e

# Defaults values for script parameters.
APPSCALE_REPO="git://github.com/AppScale/appscale.git"
APPSCALE_TOOLS_REPO="git://github.com/AppScale/appscale-tools.git"
AGENTS_REPO="git://github.com/AppScale/appscale-agents.git"
THIRDPARTIES_REPO="git://github.com/AppScale/appscale-thirdparties.git"
APPSCALE_BRANCH="master"
APPSCALE_TOOLS_BRANCH="master"
AGENTS_BRANCH="master"
THIRDPARTIES_BRANCH="master"
GIT_TAG="last"

BRANCH_PARAM_SPECIFIED="N"
TAG_PARAM_SPECIFIED="N"

usage() {
    echo "Usage: ${0} [--repo <repo>] [--branch <branch>]"
    echo "            [--tools-repo <repo>] [--tools-branch <branch>]"
    echo "            [--tag <git-tag>]"
    echo
    echo "Be aware that tag parameter has priority over repo and branch parameters."
    echo "So if no tag, repos and branches are specified, tag 'last' will be used."
    echo "If you want to bootstrap using master branches of all repos, specify '--tag dev'"
    echo
    echo "Options:"
    echo "   --repo <repo>                   Specify appscale repo (default $APPSCALE_REPO)"
    echo "   --branch <branch>               Specify appscale branch (default $APPSCALE_BRANCH)"
    echo "   --tools-repo <repo>             Specify appscale-tools repo (default $APPSCALE_TOOLS_REPO"
    echo "   --tools-branch <branch>         Specify appscale-tools branch (default $APPSCALE_TOOLS_BRANCH)"
    echo "   --tag <git-tag>                 Use git tag (ie 3.7.2) or 'last' to use the latest release"
    echo "                                   or 'dev' for HEAD (default ${GIT_TAG})"
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

# Let's get the command line arguments.
while [ $# -gt 0 ]; do
    if [ "${1}" = "--repo" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        APPSCALE_REPO="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--branch" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        APPSCALE_BRANCH="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--tools-repo" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        APPSCALE_TOOLS_REPO="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--tools-branch" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        APPSCALE_TOOLS_BRANCH="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--agents-repo" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        AGENTS_REPO="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--agents-branch" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        AGENTS_BRANCH="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--thirdparties-repo" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        THIRDPARTIES_REPO="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--thirdparties-branch" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        THIRDPARTIES_BRANCH="${1}"; BRANCH_PARAM_SPECIFIED="Y"
        shift; continue
    fi
    if [ "${1}" = "--tag" ]; then
        shift; if [ -z "${1}" ]; then usage; fi
        GIT_TAG="${1}";
        if [${GIT_TAG} != "dev" ]; then TAG_PARAM_SPECIFIED="Y"; fi
        shift; continue
    fi
    echo "Parameter '$1' is not recognized"
    echo
    usage
done


# Validate parameters combination
if [ "${BRANCH_PARAM_SPECIFIED}" = "Y" ] && [ "${TAG_PARAM_SPECIFIED}" = "Y" ]; then
    echo "Repo/Branch parameters can't be used if --tag parameter is specified"
    exit 1
fi

# Determine if we use official repos with tag or custom branches
if [ "${BRANCH_PARAM_SPECIFIED}" = "Y" ] || [ "${GIT_TAG}" = "dev" ]; then
    RELY_ON_TAG="N"
else
    RELY_ON_TAG="Y"
    if [ "${GIT_TAG}" = "last" ]; then
        echo "Determining the latest tag in AppScale/appscale repo"
        GIT_TAG=$(curl --fail https://api.github.com/repos/appscale/appscale/tags \
                  | grep '"name"' | head -1 \
                  | awk -F ':' '{ print $2 }' | tr --delete ' ,"')
    fi
    VERSION="${GIT_TAG}"
fi

# At this time we expect to be installed in $HOME.
cd $HOME

echo
if [ "${RELY_ON_TAG}" = "Y" ]; then
    echo "Will be using the following github repos:"
    echo "AppScale:        ${APPSCALE_REPO} - Tag ${GIT_TAG}"
    echo "AppScale-Tools:  ${APPSCALE_TOOLS_REPO} - Tag ${GIT_TAG}"
    if version_ge ${VERSION} 3.8.0; then echo "Cloud-Agents:    ${AGENTS_REPO} - Tag ${GIT_TAG}"; fi
    if version_ge ${VERSION} 4.0.0; then echo "Thirdparties:    ${THIRDPARTIES_REPO} - Tag ${GIT_TAG}"; fi
    echo "Exit now (ctrl-c) if this is incorrect"
else
    echo "Will be using the following github repos:"
    echo "AppScale:        ${APPSCALE_REPO} - Branch ${APPSCALE_BRANCH}"
    echo "AppScale-Tools:  ${APPSCALE_TOOLS_REPO} - Branch ${APPSCALE_TOOLS_BRANCH}"
    echo "Cloud-Agents:    ${AGENTS_REPO} - Branch ${AGENTS_BRANCH}"
    echo "Thirdparties:    ${THIRDPARTIES_REPO} - Branch ${THIRDPARTIES_BRANCH}"
    echo "Exit now (ctrl-c) if this is incorrect"
fi
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

APPSCALE_DIRS="\
    /root/appscale /root/appscale-tools /root/appscale-agents /root/appscale-thirdparties \
    /etc/appscale /opt/appscale /var/log/appscale /var/appscale /run/appscale"

for appscale_presence_marker in ${APPSCALE_DIRS}; do
    if [ -d ${appscale_presence_marker} ] ; then
        echo "${appscale_presence_marker} already exists!"
        echo "bootstrap.sh script should be used for initial installation only."
        echo "Use upgrade.sh for upgrading existing deployment"
        echo "It can be found here: https://raw.githubusercontent.com/AppScale/appscale/master/upgrade.sh."
        exit 1
    fi
done


echo "Cloning appscale repositories"
# We split the commands, to ensure it fails if branch doesn't
# exists (Precise git will not fail otherwise).
git clone ${APPSCALE_REPO} appscale
VERSION=$(cat /root/appscale/VERSION | grep -oE "[0-9]+\.[0-9]+\.[0-9]+")
git clone ${APPSCALE_TOOLS_REPO} appscale-tools
if version_ge ${VERSION} 3.8.0; then git clone ${AGENTS_REPO} appscale-agents; fi
if version_ge ${VERSION} 4.0.0; then git clone ${THIRDPARTIES_REPO} appscale-thirdparties; fi

# Use tags if we specified it.
if [ "${RELY_ON_TAG}" = "Y"  ]; then
    (cd appscale; git checkout "${GIT_TAG}")
    (cd appscale-tools; git checkout "${GIT_TAG}")
    if version_ge ${VERSION} 3.8.0; then (cd appscale-agents; git checkout "${GIT_TAG}"); fi
    if version_ge ${VERSION} 4.0.0; then (cd appscale-thirdparties; git checkout "${GIT_TAG}"); fi
else
    (cd appscale; git checkout ${APPSCALE_BRANCH})
    (cd appscale-tools; git checkout ${APPSCALE_TOOLS_BRANCH})
    if version_ge ${VERSION} 3.8.0; then (cd appscale-agents; git checkout ${AGENTS_BRANCH}); fi
    if version_ge ${VERSION} 4.0.0; then (cd appscale-thirdparties; git checkout ${THIRDPARTIES_BRANCH}); fi
fi

echo -n "Building AppScale..."
if ! (cd appscale/debian; bash appscale_build.sh) ; then
    echo "Failed to install AppScale core"
    exit 1
fi

if version_ge ${VERSION} 3.8.0; then
    echo -n "Installing AppScale Agents..."
    if ! (cd appscale-agents/; make install-no-venv) ; then
        echo "Failed to install AppScale Agents"
        exit 1
    fi
fi

echo -n "Building AppScale Tools..." 
if ! (cd appscale-tools/debian; bash appscale_build.sh) ; then
    echo "Failed to install AppScale-Tools"
    exit 1
fi

if version_ge ${VERSION} 4.0.0; then
    echo -n "Installing Thirdparty software..."
    if ! (cd appscale-thirdparties/; bash install_all.sh) ; then
        echo "Failed to install Thirdparties software"
        exit 1
    fi
fi

# Let's source the profiles so this image can be used right away.
. /etc/profile.d/appscale.sh

echo "****************************************"
echo "  AppScale is installed on the machine  "
echo "****************************************"
exit 0
