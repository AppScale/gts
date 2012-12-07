#!/bin/bash

set -e

PYTHON=/var/lib/appscale/virtualenvs/appscale-tools/bin/python
APPSCALE_BOOTSTRAP=/var/lib/appscale/virtualenvs/appscale-tools/bin/appscale-bootstrap

current_branch=$(basename $(git symbolic-ref HEAD))

${PYTHON} ${APPSCALE_BOOTSTRAP} --appscale-branch=${current_branch}
