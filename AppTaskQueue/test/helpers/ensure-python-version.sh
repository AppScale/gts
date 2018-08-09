#!/usr/bin/env bash
#
# Ensures that requested version of python is available at ./python-x.y.z,
# pip for the corresponding python will be available at ./pip-x.y.z
# The script either:
#  - Just create a symlink if needed version is already installed;
#  - Or downloads sources from python.org and compiles it.


set -e
set -u

usage() {
    echo "Usage: ${0} <python-version:X.Y.Z> [--create-link <symlink-name>]"
    echo
    echo "Options:"
    echo "   --create-link <symlink-name>   Scenario file to use (default ./python-<x.y.z>)"
    exit 1
}

# Let's get the command line arguments.
# Positional argument first
NEEDED_VERSION=$1
shift
if [ -z "${NEEDED_VERSION}" ]; then
    usage
fi
PYTHON_LINK=$(realpath --strip "./python-${NEEDED_VERSION}")
# Options
while [ $# -gt 0 ]; do
    if [ "${1}" = "--create-link" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        PYTHON_LINK="${1}"
        shift
        continue
    fi
    usage
done

log() {
    local LEVEL=${2:-INFO}
    echo "$(date +'%Y-%m-%d %T'): $LEVEL $1"
}


# Verifies if candidate version is greater or equal to minimal
verify_version() {
    CANDIDATE=$1
    MINIMAL=$2
    return $(python -c "
actual = [int(v) for v in '${CANDIDATE}'.split('.')]
minimal = [int(v) for v in '${MINIMAL}'.split('.')]
if actual and actual >= minimal:
    exit(0)
exit(1)" &> /dev/null)
}


# Loop through standard python aliases in order to find needed version
PYTHON=
PYTHON_OPTIONS="python python3 python3.5 python3.6 python3.7"
for PYTHON_EXECUTABLE in ${PYTHON_OPTIONS}
do
    # Check if executable is present
    if ! which ${PYTHON_EXECUTABLE} &> /dev/null; then continue; fi

    # Get exact version of python interpreter
    PYTHON_VERSION=$(${PYTHON_EXECUTABLE} --version 2> null | awk '{ print $2 }')

    # Stop if version is new enough
    if verify_version "${PYTHON_VERSION}" "${NEEDED_VERSION}"
    then
        log "Python ${PYTHON_VERSION} is already installed"
        PYTHON=$(which ${PYTHON_EXECUTABLE})
        break
    fi
done

# Install python if needed version is missing
if [ -z ${PYTHON} ]
then
    log "Fetching Python-${NEEDED_VERSION} from https://www.python.org ..."
    wget "https://www.python.org/ftp/python/${NEEDED_VERSION}/Python-${NEEDED_VERSION}.tar.xz"
    tar xf "Python-${NEEDED_VERSION}.tar.xz"
    rm "Python-${NEEDED_VERSION}.tar.xz"
    cd "Python-${NEEDED_VERSION}"

    log "Compiling Python-${NEEDED_VERSION} from sources"
    INSTALLATION_DIR=$(realpath --strip ../python-installtion)
    mkdir -p "${INSTALLATION_DIR}"
    ./configure --prefix="${INSTALLATION_DIR}"
    make
    make install
    PYTHON=$(realpath --strip "./python")
    cd ..
fi

log "Creating symbolic link to python executable"
rm -f "${PYTHON_LINK}"
ln -s "${PYTHON}" "${PYTHON_LINK}"

log "Python-${NEEDED_VERSION} is available at '${PYTHON_LINK}'"
