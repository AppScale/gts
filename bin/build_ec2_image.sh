#!/bin/bash

set -e

source /etc/profile.d/appscale_config.sh

PYTHON=/var/lib/appscale/virtualenvs/appscale-tools/bin/python
APPSCALE_BOOTSTRAP=/var/lib/appscale/virtualenvs/appscale-tools/bin/appscale-bootstrap

current_branch=$(git log --decorate -n 1 | head -n 1 | sed -e 's/.*\(origin\/[^),]*\).*/\1/')

${PYTHON} ${APPSCALE_BOOTSTRAP} -t m1.large --ami='ami-d59818bc' --appscale-branch=${current_branch}
