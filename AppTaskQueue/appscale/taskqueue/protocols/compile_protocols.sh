#!/usr/bin/env bash

# Compiles protocols and prepares venv for tq

set -e

PROTOCOLS_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"
TASKQUEUE_DIR="$( dirname "$( dirname "$( dirname "${PROTOCOLS_DIR}" )" )" )"

if ! protoc --version | grep -E ' (3\.)|(2\.)' ; then
    echo "Couldn't compile *.proto files because protoc version 3 was not found."
    exit 1
fi

echo "Compiling Protocol buffer *.proto files.."

(cd "${TASKQUEUE_DIR}" && \
 protoc --python_out=. appscale/taskqueue/protocols/*.proto)

echo "Protocols have been successfully compiled."
