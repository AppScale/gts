#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
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
    echo "Usage: ${0} [--repo <repo>] [--tools-repo <repo>]"
    echo "            [--tools-repo <repo>] [--tools-branch <branch>]"
    echo "            [--agents-repo <repo>] [--agents-branch <branch>]"
    echo "            [--thirdparties-repo <repo>] [--thirdparties-branch <branch>]"
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
    echo "   --agents-repo <repo>            Specify appscale-agents repo (default $AGENTS_REPO"
    echo "   --agents-branch <branch>        Specify appscale-agents branch (default $AGENTS_BRANCH)"
    echo "   --thirdparties-repo <repo>      Specify appscale-thirdparties repo (default $THIRDPARTIES_REPO"
    echo "   --thirdparties-branch <branch>  Specify appscale-thirdparties branch (default $THIRDPARTIES_BRANCH)"
    echo "   --tag <git-tag>                 Use git tag (ie 3.7.2) or 'last' to use the latest release"
    echo "                                   or 'dev' for HEAD (default ${GIT_TAG})"
    exit 1
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
    usage
done


# Empty tag means we use the latest available.
if [ "${BRANCH_PARAM_SPECIFIED}" = "Y" ] \
   && [ "${TAG_PARAM_SPECIFIED}" = "Y" ] \
   && [ "${GIT_TAG}" != "dev" ]; then
    echo "Repo/Branch parameters can't be used if --tag parameter is specified"
    exit 1
fi

declare -A REPOS=(
    ["appscale"]="${APPSCALE_REPO}"
    ["appscale-tools"]="${APPSCALE_TOOLS_REPO}"
    ["appscale-agents"]="${AGENTS_REPO}"
    ["appscale-thirdparties"]="${THIRDPARTIES_REPO}"
)
declare -A BRANCHES=(
    ["appscale"]="${APPSCALE_BRANCH}"
    ["appscale-tools"]="${APPSCALE_TOOLS_BRANCH}"
    ["appscale-agents"]="${AGENTS_BRANCH}"
    ["appscale-thirdparties"]="${THIRDPARTIES_BRANCH}"
)

# At this time we expect to be installed in $HOME.
cd $HOME

# Let's pull the github repositories.
echo
if [ "${TAG_PARAM_SPECIFIED}" = "Y" ]; then
    echo "Will be using the following github repos:"
    echo "Repo: ${APPSCALE_REPO} Tag ${GIT_TAG}"
    echo "Repo: ${APPSCALE_TOOLS_REPO} Tag ${GIT_TAG}"
    echo "Repo: ${AGENTS_REPO} Tag ${GIT_TAG}"
    echo "Repo: ${THIRDPARTIES_REPO} Tag ${GIT_TAG}"
    echo "Exit now (ctrl-c) if this is incorrect"
else
    echo "Will be using the following github repos:"
    echo "Repo: ${APPSCALE_REPO} Branch: ${APPSCALE_BRANCH}"
    echo "Repo: ${APPSCALE_TOOLS_REPO} Branch: ${APPSCALE_TOOLS_BRANCH}"
    echo "Repo: ${AGENTS_REPO} Branch: ${AGENTS_BRANCH}"
    echo "Repo: ${THIRDPARTIES_REPO} Branch: ${THIRDPARTIES_BRANCH}"
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
        echo "Use bootstrap-upgrade.sh for upgrading existing deployment"
        echo "It can be found here: https://raw.githubusercontent.com/AppScale/appscale/master/bootstrap-upgrade.sh."
    fi
done


echo "Cloning appscale repositories"
# We split the commands, to ensure it fails if branch doesn't
# exists (Precise git will not fail otherwise).
git clone ${APPSCALE_REPO} appscale
git clone ${APPSCALE_TOOLS_REPO} appscale-tools
git clone ${AGENTS_REPO} appscale-agents
git clone ${THIRDPARTIES_REPO} appscale-thirdparties

# Use tags if we specified it.
if [ "$TAG_PARAM_SPECIFIED" = "Y"  ]; then
    if [ "$GIT_TAG" = "last" ]; then
        GIT_TAG="$(cd appscale; git tag | tail -n 1)"
    fi
    (cd appscale; git checkout "$GIT_TAG")
    (cd appscale-tools; git checkout "$GIT_TAG")
    (cd appscale-agents; git checkout "$GIT_TAG")
    (cd appscale-thirdparties; git checkout "$GIT_TAG")
else
    (cd appscale; git checkout ${APPSCALE_BRANCH})
    (cd appscale-tools; git checkout ${APPSCALE_TOOLS_BRANCH})
    (cd appscale-agents; git checkout ${AGENTS_BRANCH})
    (cd appscale-thirdparties; git checkout ${THIRDPARTIES_BRANCH})
fi

echo -n "Building AppScale..."
if ! (cd appscale/debian; bash appscale_build.sh) ; then
    echo "failed!"
    exit 1
fi

echo -n "Installing AppScale Agents..."
if ! (cd appscale-agents/; make install-no-venv) ; then
    echo "Failed to install AppScale Agents"
    exit 1
fi

echo -n "Building AppScale Tools..." 
if ! (cd appscale-tools/debian; bash appscale_build.sh) ; then
    echo "failed!"
    exit 1
fi

echo -n "Downloading Thirdparty artifacts..."
if ! (cd appscale-thirdparties/; bash download_all_artifacts.sh) ; then
    echo "failed!"
    exit 1
fi

# Let's source the profiles so this image can be used right away.
. /etc/profile.d/appscale.sh

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
exit 0
