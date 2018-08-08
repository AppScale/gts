#!/usr/bin/env bash
#
# - Starts and configures Postgres on remote machine;
# - Starts Taskqueue servers on remote machine;
# - Ensures python venv is installed with all needed packages;
# - Runs e2e tests.

set -e
set -u


usage() {
    echo "Usage: ${0} --key-location <KEY> --user-name <USER> --vm-addr <HOST> --vm-private-ip <IP> [--logs-dir <DIR>]"
    echo
    echo "Options:"
    echo "   --key-location <KEY>  Private key file for access to the machine"
    echo "   --user-name <USER>    User name to use for access to the machine"
    echo "   --vm-addr <HOST>      Hostname ot public IP of the machine"
    echo "                         to start TaskQueue on"
    echo "   --vm-private-ip <IP>  Private IP of the machine to start TaskQueue on"
    echo "   --logs-dir <DIR>      Directory to save logs to (default: ./logs)"
    exit 1
}

KEY_LOCATION=
USER=
VM_ADDR=
VM_PRIVATE_IP=
LOGS_DIR="$(realpath --strip ./logs)"

# Let's get the command line arguments.
while [ $# -gt 0 ]; do
    if [ "${1}" = "--key-location" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        KEY_LOCATION="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--user-name" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        USER="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--vm-addr" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        VM_ADDR="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--vm-private-ip" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        VM_PRIVATE_IP="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--logs-dir" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        LOGS_DIR="${1}"
        shift
        continue
    fi
    usage
done

if [ -z "${VM_ADDR}" ] || [ -z "${VM_PRIVATE_IP}" ] \
   || [ -z "${KEY_LOCATION}" ] || [ -z "${USER}" ]
then
    usage
fi

log() {
    local LEVEL=${2:-INFO}
    echo "$(date +'%Y-%m-%d %T'): $LEVEL $1"
}

mkdir -p "${LOGS_DIR}"

scp_logs() {
    log "Downloading AppScale logs from the machine to ${LOGS_DIR}"
    scp -o StrictHostKeyChecking=no \
        -i "${KEY_LOCATION}" -r \
        "${USER}@${VM_ADDR}:/var/log/appscale/*" \
        "${LOGS_DIR}"
}
trap scp_logs EXIT


# Determine absolute path to some dirs
SUITES_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"
TASKQUEUE_SRC_DIR="$( dirname "$( dirname "${SUITES_DIR}" )" )"
HELPERS_DIR="${TASKQUEUE_SRC_DIR}/test/helpers"
E2E_TEST_DIR="${TASKQUEUE_SRC_DIR}/test/e2e"

log "Copying scripts and TaskQueue sources to the machine"
scp -o StrictHostKeyChecking=no \
    -i "${KEY_LOCATION}" \
    "${HELPERS_DIR}/prepare-postgres.sh" \
    "${HELPERS_DIR}/prepare-zookeeper.sh" \
    "${HELPERS_DIR}/prepare-cassandra.sh" \
    "${HELPERS_DIR}/restart-taskqueue.sh" \
    "${USER}@${VM_ADDR}:/tmp/"
ssh -o StrictHostKeyChecking=no \
    -i ${KEY_LOCATION} ${USER}@${VM_ADDR} "mkdir -p /tmp/AppTaskQueue/"
scp -o StrictHostKeyChecking=no \
    -r -i "${KEY_LOCATION}" \
    "${TASKQUEUE_SRC_DIR}/appscale" \
    "${TASKQUEUE_SRC_DIR}/setup.py" \
    "${USER}@${VM_ADDR}:/tmp/AppTaskQueue/"

log "Initializing TaskQueue dependencies at ${USER}@${VM_ADDR}"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${VM_ADDR} << COMMANDS
set -e
set -u
sudo /tmp/prepare-postgres.sh --host "${VM_PRIVATE_IP}" \
                              --dbname "appscale-test-project" \
                              --username "appscale" \
                              --password "appscale-pwd"
sudo /tmp/prepare-zookeeper.sh
sudo /tmp/prepare-cassandra.sh --private-ip ${VM_PRIVATE_IP}
COMMANDS

log "Prepare virtualenv for running test script"
# aiohttp lib which is used in e2e test requires Python>=3.5.3
# test scripts uses new syntax for formatting strings (3.6+)
PYTHON=$(realpath --strip ./python-3.6.6-plus)
${HELPERS_DIR}/ensure-python-version.sh 3.6.6 --create-link "${PYTHON}"

cd "${E2E_TEST_DIR}"

# Configure virtualenvironment
${PYTHON} -m venv "venv"
venv/bin/pip install --upgrade pip
venv/bin/pip install ${HELPERS_DIR}
venv/bin/pip install pytest
venv/bin/pip install kazoo

export TEST_PROJECT="test-project"

STATUS=0

log "============================================"
log "Test Cassandra implementation of Pull Queues"

log "Upgrading TaskQueue package and starting servers at ${USER}@${VM_ADDR}"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${VM_ADDR} << COMMAND
sudo /tmp/restart-taskqueue.sh --ports 50001,50002 \
                               --db-ip "${VM_PRIVATE_IP}" \
                               --zk-ip "${VM_PRIVATE_IP}" \
                               --lb-ip "${VM_PRIVATE_IP}" \
                               --source-dir /tmp/AppTaskQueue
COMMAND

venv/bin/pytest -vv --tq-locations ${VM_ADDR}:50001 ${VM_ADDR}:50002 \
                --zk-location "${VM_ADDR}" \
                || STATUS=1


log "==========================================="
log "Test Postgres implementation of Pull Queues"

log "Creating postgres_dsn node in Zookeeper and restarting TaskQueue"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${VM_ADDR} << COMMANDS
set -e
set -u
sudo /usr/share/zookeeper/bin/zkCli.sh delete \
    /appscale/projects/${TEST_PROJECT}/postgres_dsn \
sudo /usr/share/zookeeper/bin/zkCli.sh create \
    /appscale/projects/${TEST_PROJECT}/postgres_dsn \
    "dbname=appscale-test-project user=appscale password=appscale-pwd host=${VM_PRIVATE_IP}"
sudo /tmp/restart-taskqueue.sh --ports 50001,50002 \
                               --db-ip "${VM_PRIVATE_IP}" \
                               --zk-ip "${VM_PRIVATE_IP}" \
                               --lb-ip "${VM_PRIVATE_IP}"
COMMANDS
venv/bin/pytest -vv --tq-locations ${VM_ADDR}:50001 ${VM_ADDR}:50002 \
                --zk-location "${VM_ADDR}" \
                || STATUS=1

exit ${STATUS}
