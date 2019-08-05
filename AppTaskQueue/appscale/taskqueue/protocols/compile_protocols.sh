#!/usr/bin/env bash

# Compiles protocols and prepares venv for tq

set -e
set -x

PROTOCOLS_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"

if ! protoc --version | grep -E ' (3\.)|(2\.)' ; then
    echo "Couldn't compile *.proto files because protoc version 3 was not found."
    exit 1
fi

echo "Compiling Protocol buffer *.proto files.."
#(cd "${TQ_DIR}"/appscale/taskqueue/protocols && protoc --python_out=./ *.proto)
protoc --proto_path=$PROTOCOLS_DIR --python_out=$PROTOCOLS_DIR \
  $PROTOCOLS_DIR/*.proto
echo "Protocols have been successfully compiled."
