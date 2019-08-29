#!/usr/bin/env bash

set -e
set -u

SEARCH_DIR="$( realpath --strip "$(dirname "$( dirname "${BASH_SOURCE[0]}" )" )" )"
COMMON_DIR="$( realpath --strip "$(dirname "${SEARCH_DIR}" )" )/common"

echo "Compiling Protobuf protocols.."
"${SEARCH_DIR}/build-scripts/compile_protocols.sh"

echo "Compiling antlr4 query paraser.."
"${SEARCH_DIR}/build-scripts/compile_query_parser.sh"

if [ "$1" == "" ]; then
    echo "Positional parameter 1 is required and should contain pip executable to use."
    exit 1
fi

PIP="$1"

if ! "${PIP}" --version | grep 'python 3\.' ; then
    echo "Positional parameter 1 should contain pip executable for python 3."
    exit 1
fi

echo "Upgrading appscale-common.."
"${PIP}" install --upgrade --no-deps "${COMMON_DIR}"
echo "Installing appscale-common dependencies if any missing.."
"${PIP}" install "${COMMON_DIR}"
echo "Upgrading appscale-search2.."
"${PIP}" install --upgrade --no-deps "${SEARCH_DIR}"
echo "Installing appscale-search2 dependencies if any missing.."
"${PIP}" install "${SEARCH_DIR}"

echo "appscale-search2 has been successfully installed."