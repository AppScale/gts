#!/bin/bash
#
# Simple script to install AppScale and tools from the master branch
# Author: AppScale Team <support@appscale.com>

set -e

# Defaults values for repositories and branches.
APPSCALE_REPO="git://github.com/AppScale/appscale.git"
APPSCALE_TOOLS_REPO="git://github.com/AppScale/appscale-tools.git"
AGENTS_REPO="git://github.com/AppScale/appscale-agents.git"
APPSCALE_BRANCH="master"
APPSCALE_TOOLS_BRANCH="master"
AGENTS_BRANCH="master"
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

echo -n "Checking to make sure \$HOME is /root..."
if [ "$HOME" != "/root" ]; then
   echo "Failed"
   exit 1
fi
echo "Success"

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
    if [ "${1}" = "--agents-repo" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        AGENTS_REPO="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--agents-branch" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        AGENTS_BRANCH="${1}"
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
    if [ "${FORCE_UPGRADE}" = "N"  ] && [  "${APPSCALE_BRANCH}" != "master" ]; then
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
if [ ! -d appscale ]; then
    # We split the commands, to ensure it fails if branch doesn't
    # exists (Precise git will not fail otherwise).
    git clone ${APPSCALE_REPO} appscale
    (cd appscale; git checkout ${APPSCALE_BRANCH})

    git clone ${APPSCALE_TOOLS_REPO} appscale-tools
    (cd appscale-tools; git checkout ${APPSCALE_TOOLS_BRANCH})

    git clone ${AGENTS_REPO} appscale-agents
    (cd appscale-agents; git checkout ${AGENTS_BRANCH})


    # Use tags if we specified it.
    if [ -n "$GIT_TAG"  ] && [  "${APPSCALE_BRANCH}" = "master" ]; then
        if [ "$GIT_TAG" = "last" ]; then
            GIT_TAG="$(cd appscale; git tag | tail -n 1)"
        fi
        (cd appscale; git checkout "$GIT_TAG")
        (cd appscale-tools; git checkout "$GIT_TAG")
        (cd appscale-agents; git checkout "$GIT_TAG")
    fi
fi

# Since the last step in appscale_build.sh is to create the certs directory,
# its existence indicates that appscale has already been installed.
if [ -d /etc/appscale/certs ]; then
    UPDATE_REPO="Y"

    # For upgrade, we don't switch across branches.
    if [ "${FORCE_UPGRADE}" = "N" ] && [ "${APPSCALE_BRANCH}" != "master" ]; then
        echo "Cannot use --branch when upgrading"
        exit 1
    fi
    if [ "${FORCE_UPGRADE}" = "N"  ] && [  "${APPSCALE_TOOLS_BRANCH}" != "master" ]; then
        echo "Cannot use --tools-branch when upgrading"
        exit 1
    fi
    if [ "${FORCE_UPGRADE}" = "N"  ] && [  -z "$GIT_TAG" ]; then
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
    (cd appscale; git fetch ${APPSCALE_REPO} -t)
    (cd appscale-tools; git fetch ${APPSCALE_TOOLS_REPO} -t)
    (cd appscale-agents; git fetch ${AGENTS_REPO} -t)

    if [ "$GIT_TAG" = "last" ]; then
        GIT_TAG="$(cd appscale; git tag | tail -n 1)"
        # Make sure we have this tag in the official repo.
        if ! git ls-remote --tags ${APPSCALE_REPO} | grep -F $GIT_TAG > /dev/null ; then
            echo "\"$GIT_TAG\" not recognized: use --tag to specify tag to upgrade to."
            exit 1
        fi
    fi

    # We can pull a tag only if we are on the master branch.
    CURRENT_BRANCH="$(cd appscale; git branch --no-color | grep '^*' | cut -f 2 -d ' ')"
    if [ "${CURRENT_BRANCH}" != "master" ] && \
            (cd appscale; git tag -l | grep $(git describe)) ; then
        CURRENT_BRANCH="$(cd appscale; git tag -l | grep $(git describe))"
        if [ "${CURRENT_BRANCH}" = "${GIT_TAG}" ]; then
            echo "AppScale repository is already at the"\
                 "specified release. Building with current code."
            UPDATE_REPO="N"
        fi
    fi

    # If CURRENT_BRANCH is empty, then we are not on master, and we
    # are not on a released version: we don't upgrade then.
    if [ "${FORCE_UPGRADE}" = "N"  ] && [  -z "${CURRENT_BRANCH}" ]; then
        echo "Error: git repository is not 'master' or a released version."
        exit 1
    fi

    # Make sure AppScale is not running.
    MONIT=$(which monit)
    if $MONIT summary | grep controller > /dev/null ; then
        echo "AppScale is still running: please stop it"
        [ "${FORCE_UPGRADE}" = "Y" ] || exit 1
    elif echo $MONIT | grep local > /dev/null ; then
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


    if [ "${UPDATE_REPO}" = "Y" ]; then
        echo "Found AppScale version $APPSCALE_MAJOR.$APPSCALE_MINOR."\
             "An upgrade to the latest version available will be"\
             "attempted in 5 seconds."
        sleep 5

        # Upgrade the repository. If GIT_TAG is empty, we are on HEAD.
        if [ -n "${GIT_TAG}" ]; then
            if ! (cd appscale; git checkout "$GIT_TAG"); then
                echo "Please stash your local unsaved changes and checkout"\
                     "the version of AppScale you are currently using to fix"\
                     "this error."
                echo "e.g.: git stash; git checkout <AppScale-version>"
                exit 1
            fi

            if ! (cd appscale-tools; git checkout "$GIT_TAG"); then
                echo "Please stash your local unsaved changes and checkout"\
                     "the version of appscale-tools you are currently using"\
                     "to fix this error."
                echo "e.g.: git stash; git checkout <appscale-tools-version>"
                exit 1
            fi
        elif [ "${FORCE_UPGRADE}" = "N" ]; then
            (cd appscale; git pull)
            (cd appscale-tools; git pull)
        else
            RANDOM_KEY="$(echo $(date), $$|md5sum|head -c 6)-$(date +%s)"
            REMOTE_REPO_NAME="appscale-bootstrap-${RANDOM_KEY}"
            if ! (cd appscale;
                    git remote add -t "${APPSCALE_BRANCH}" -f "${REMOTE_REPO_NAME}" "${APPSCALE_REPO}";
                    git checkout "${REMOTE_REPO_NAME}"/"${APPSCALE_BRANCH}"); then
                echo "Please make sure the repository url is correct, the"\
                     "branch exists, and that you have stashed your local"\
                     "changes."
                echo "e.g.: git stash, git remote add -t {remote_branch} -f"\
                     "{repo_name} {repository_url}; git checkout"\
                     "{repo_name}/{remote_branch}"
                exit 1
            fi
            if ! (cd appscale-tools;
                    git remote add -t "${APPSCALE_TOOLS_BRANCH}" -f "${REMOTE_REPO_NAME}" "${APPSCALE_TOOLS_REPO}";
                    git checkout "${REMOTE_REPO_NAME}"/"${APPSCALE_TOOLS_BRANCH}"); then
                echo "Please make sure the repository url is correct, the"\
                     "branch exists, and that you have stashed your local"\
                     "changes."
                echo "e.g.: git stash, git remote add -t {remote_branch} -f"\
                     "{repo_name} {repository_url}; git checkout"\
                     "{repo_name}/{remote_branch}"
                exit 1
            fi
        fi
    fi
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

echo "*****************************************"
echo "AppScale and AppScale tools are installed"
echo "*****************************************"
exit 0
