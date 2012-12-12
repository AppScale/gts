#!/bin/bash
# Used by Jenkins to automatically build an EC2 image with changes pushed to
# Git.

set -e

source /etc/profile.d/appscale_config.sh

PYTHON=/var/lib/appscale/virtualenvs/appscale-tools/bin/python
APPSCALE_BOOTSTRAP=/var/lib/appscale/virtualenvs/appscale-tools/bin/appscale-bootstrap

# Jenkins takes the SHA1 from the commit and checks it out as a detached head
# rather than the branch that was pushed.  Because of this, use `git log
# --decorate` to associate the commit with a branch.  Use sed to rip off the
# prefix (using basename might work too).
current_branch=$(git log --decorate -n 1 | head -n 1 | sed -e 's/.*\(origin\/[^),]*\).*/\1/')

${PYTHON} ${APPSCALE_BOOTSTRAP} -t m1.large --ami='ami-d59818bc' --appscale-branch=${current_branch}
