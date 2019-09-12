#!/usr/bin/env bash

set -e    # Exit on error
set -u    # Fail on undefined variable
set -x    # Print executed command to stdout

SEARCH_DIR="$( realpath --strip "$(dirname "$( dirname "${BASH_SOURCE[0]}" )" )" )"

if ! protoc --version | grep -E ' (3\.)|(2\.)' ; then
    echo "Couldn't compile *.proto files because protoc version 3 was not found."
    exit 1
fi

echo "Compiling Protocol buffer *.proto files.."
(cd "${SEARCH_DIR}"/appscale/search/protocols && protoc --python_out=./ *.proto)

echo "Protocols have been successfully compiled."
