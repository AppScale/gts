#!/usr/bin/env bash

# Compiles protocols and prepares venv for tq

set -e
set -x

PROTOCOLS_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"
TQ_DIR="$( dirname "$( dirname "$( dirname "${PROTOCOLS_DIR}" )" )" )"
COMMON_DIR="$( dirname "${TQ_DIR}" )"/common

if ! protoc --version | grep -E ' (3\.)|(2\.)' ; then
    echo "Couldn't compile *.proto files because protoc version 3 was not found."
    exit 1
fi

echo "Compiling Protocol buffer *.proto files.."
(cd "${TQ_DIR}"/appscale/taskqueue/protocols && protoc --python_out=./ *.proto)

if [ "$1" == "" ]; then
    echo "Positional parameter 1 is required and should contain pip executable to use."
    exit 1
fi

PIP="$1"

echo "Upgrading appscale-common.."
"${PIP}" install --upgrade --no-deps "${COMMON_DIR}"
echo "Installing appscale-common dependencies if any missing.."
"${PIP}" install "${COMMON_DIR}"
echo "Upgrading appscale-taskqueue.."
"${PIP}" install --upgrade --no-deps "${TQ_DIR}[celery_gui]"
echo "Installing appscale-taskqueue dependencies if any missing.."
"${PIP}" install "${TQ_DIR}[celery_gui]"

echo "appscale-taskqueue has been successfully installed."
