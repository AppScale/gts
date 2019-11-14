#!/usr/bin/env bash
#
# - Starts and configures Postgres on remote machine;
# - Starts Taskqueue servers on remote machines;
# - Configures loadbalancer for TaskQueue servers;
# - Ensures python venv is installed with all needed packages;
# - Runs load tests.
#
# See AppTaskQueue/test/load/README.md for more details.

set -e
set -u


usage() {
    echo "Usage: ${0} \\"
    echo "         --key-location <KEY> --user-name <USER> \\"
    echo "         --layout-file <FILE> --producers <NUM> --workers <NUM> \\"
    echo "         --run-time <DURATION> --tq-per-vm <NUM> \\"
    echo "         [--locust-timeout <SEC>] [--logs-dir <DIR>]"
    echo
    echo "Options:"
    echo "   --key-location <KEY>    Private key file for access to machines."
    echo "   --user-name <USER>      User name to use for access to machines."
    echo "   --layout-file <FILE>    File describing nodes role and location."
    echo "                           Sample can be found at:"
    echo "                           appscale/AppTaskQueue/test/suites/layout-example.txt "
    echo "   --producers <NUM>       Number of task producers to start."
    echo "   --workers <NUM>         Number of workers to start."
    echo "   --run-time <DURATION>   Stop producer after specified amount of time,"
    echo "                           e.g. 300s, 20m, 4h, 1h30m, etc."
    echo "   --tq-per-vm <NUM>       Number of TQ servers to start on taskqueue VMs."
    echo "   --locust-timeout <SEC>  Timeout for producers and workers (default: 1200)."
    echo "   --logs-dir <DIR>        Dir to save logs to (default: ./logs)."
    exit 1
}

KEY_LOCATION=
USER=
LAYOUT_FILE=
PRODUCERS=
WORKERS=
RUN_TIME=
TQ_PER_VM=
LOCUST_TIMEOUT=1200  # 20 minutes
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
    if [ "${1}" = "--layout-file" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        LAYOUT_FILE="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--producers" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        PRODUCERS="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--workers" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        WORKERS="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--run-time" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        RUN_TIME="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--tq-per-vm" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        TQ_PER_VM="${1}"
        shift
        continue
    fi
    if [ "${1}" = "--locust-timeout" ]; then
        shift
        if [ -z "${1}" ]; then
            usage
        fi
        LOCUST_TIMEOUT="${1}"
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

if [ -z "${KEY_LOCATION}" ] || [ -z "${USER}" ] || [ -z "${LAYOUT_FILE}" ] || \
   [ -z "${PRODUCERS}" ] || [ -z "${WORKERS}" ] || [ -z "${RUN_TIME}" ] || \
   [ -z "${TQ_PER_VM}" ]
then
    usage
fi

log() {
    local LEVEL=${2:-INFO}
    echo "$(date +'%Y-%m-%d %T'): $LEVEL $1"
}

log "Parsing layout file at ${LAYOUT_FILE}"
POSTGRES_VM=$(grep -E "^postgres" "${LAYOUT_FILE}" | awk '{ print $2 }')
POSTGRES_VM_PRIVATE_IP=$(grep -E "^postgres" "${LAYOUT_FILE}" | awk '{ print $3 }')
ZOOKEEPER_VM=$(grep -E "^zookeeper" "${LAYOUT_FILE}" | awk '{ print $2 }')
LOADBALANCER_VM=$(grep -E "^loadbalancer" "${LAYOUT_FILE}" | awk '{ print $2 }')
TASKQUEUE_VMS=$(grep -E "^taskqueue" "${LAYOUT_FILE}" | awk '{ print $2 }')


mkdir -p "${LOGS_DIR}"

kill_jobs_and_scp_logs() {
    set +e

    jobs -p | xargs kill

    for tq_vm in ${TASKQUEUE_VMS}
    do
        log "Downloading AppScale logs from ${tq_vm} to ${LOGS_DIR}/${tq_vm}"
        mkdir -p "${LOGS_DIR}/${tq_vm}"
        scp -o StrictHostKeyChecking=no \
            -i "${KEY_LOCATION}" -r \
            "${USER}@${tq_vm}:/var/log/appscale/*" \
            "${LOGS_DIR}/${tq_vm}"
    done
}
trap kill_jobs_and_scp_logs EXIT


# Determine absolute path to some dirs
SUITES_DIR="$( realpath --strip "$( dirname "${BASH_SOURCE[0]}" )" )"
TASKQUEUE_SRC_DIR="$( dirname "$( dirname "${SUITES_DIR}" )" )"
COMMON_SRC_DIR="$( dirname "${TASKQUEUE_SRC_DIR}" )"/common
HELPERS_DIR="${TASKQUEUE_SRC_DIR}/test/helpers"
LOAD_TEST_DIR="${TASKQUEUE_SRC_DIR}/test/load"

# We know where TaskQueue servers will be running. Let's save locations to file.
TQ_LOCATIONS_FILE=$(realpath --strip ./tq-locations.txt)
> "${TQ_LOCATIONS_FILE}"    # Clear the file before filling it
for host in ${TASKQUEUE_VMS}; do
    for port in $(seq 50000 $((50000 + TQ_PER_VM))); do
        echo "${host}:${port}" >> "${TQ_LOCATIONS_FILE}"
    done
done


log ""
log "===================================================================="
log "=== Sending provisioning scripts, sources and other files to VMs ==="
log "===================================================================="

log "### Copying postgres initialisation script to Postgres machine ###"
scp -o StrictHostKeyChecking=no \
    -i "${KEY_LOCATION}" \
    "${HELPERS_DIR}/prepare-postgres.sh" \
    "${USER}@${POSTGRES_VM}:/tmp/prepare-postgres.sh"

log "### Copying zookeeper initialisation script to Zookeeper machine ###"
scp -o StrictHostKeyChecking=no \
    -i "${KEY_LOCATION}" \
    "${HELPERS_DIR}/prepare-zookeeper.sh" \
    "${USER}@${ZOOKEEPER_VM}:/tmp/prepare-zookeeper.sh"

log "### Copying LB initialisation script and layout file to LB machine ###"
scp -o StrictHostKeyChecking=no \
    -i "${KEY_LOCATION}" \
    "${HELPERS_DIR}/configure-loadbalancer.sh" \
    "${TQ_LOCATIONS_FILE}" \
    "${USER}@${LOADBALANCER_VM}:/tmp/"

log "### Copying scripts and TaskQueue sources to TaskQueue machines ###"
for tq_vm_ip in ${TASKQUEUE_VMS}
do
    scp -o StrictHostKeyChecking=no \
        -i "${KEY_LOCATION}" \
        "${HELPERS_DIR}/restart-taskqueue.sh" \
        "${USER}@${tq_vm_ip}:/tmp/restart-taskqueue.sh"
    ssh -o StrictHostKeyChecking=no \
        -i ${KEY_LOCATION} ${USER}@${tq_vm_ip} "mkdir -p /tmp/AppTaskQueue/"
    scp -o StrictHostKeyChecking=no \
        -r -i "${KEY_LOCATION}" \
        "${TASKQUEUE_SRC_DIR}/appscale" \
        "${TASKQUEUE_SRC_DIR}/setup.py" \
        "${USER}@${tq_vm_ip}:/tmp/AppTaskQueue/"
    scp -o StrictHostKeyChecking=no \
        -r -i "${KEY_LOCATION}" \
        "${COMMON_SRC_DIR}" \
        "${USER}@${tq_vm_ip}:/tmp/common"
done


log ""
log "=================================================================="
log "=== Provisioning TaskQueue servers and its dependencies on VMs ==="
log "=================================================================="

log "### Initializing Postgres Database at ${USER}@${POSTGRES_VM} ###"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${POSTGRES_VM} << COMMAND
    set -e
    sudo bash /tmp/prepare-postgres.sh --host "${POSTGRES_VM_PRIVATE_IP}" \
                                       --dbname "appscale-test-project" \
                                       --username "appscale" \
                                       --password "appscale-pwd"
COMMAND

# Save DSN string and projects config to variables
PG_DSN="dbname=appscale-test-project user=appscale password=appscale-pwd host=${POSTGRES_VM_PRIVATE_IP}"
TEST_PROJECT='test-project'

log "### Initializing Zookeeper at ${USER}@${ZOOKEEPER_VM} ###"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${ZOOKEEPER_VM} << COMMANDS
    set -e
    # Run general zookeeper provisioning script
    sudo /tmp/prepare-zookeeper.sh

    # Configure project with Postgres as a backend for Pull Queues
    sudo /usr/share/zookeeper/bin/zkCli.sh create \
        /appscale/projects/${TEST_PROJECT} ""
    sudo /usr/share/zookeeper/bin/zkCli.sh create \
        /appscale/tasks ""
    sudo /usr/share/zookeeper/bin/zkCli.sh create \
        /appscale/tasks/postgres_dsn "${PG_DSN}"
COMMANDS

# Generate comma-separated list of ports from (50000) to (50000 + TQ_PER_VM)
TQ_PORTS=$(echo $(seq 50000 $((50000 + TQ_PER_VM - 1))))
# Start all TaskQueue servers
for tq_vm in ${TASKQUEUE_VMS}
do
    log "### Starting ${TQ_PER_VM} Taskqueue servers at ${USER}@${tq_vm} ###"
    ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${tq_vm} << COMMAND
        set -e
        sudo /tmp/restart-taskqueue.sh --ports "${TQ_PORTS// /,}" \
                                       --zk-ip "${ZOOKEEPER_VM}" \
                                       --lb-ip "${LOADBALANCER_VM}" \
                                       --source-dir /tmp/AppTaskQueue
COMMAND
done

log "### Configuring loadbalancer at ${USER}@${LOADBALANCER_VM} ###"
ssh -o StrictHostKeyChecking=no -i ${KEY_LOCATION} ${USER}@${LOADBALANCER_VM} << CMD
    set -e
    sudo /tmp/configure-loadbalancer.sh \
        --tq-locations-file /tmp/tq-locations.txt \
        --listen-tcp ${LOADBALANCER_VM}:4000
CMD

TQ_LOCATION="${LOADBALANCER_VM}:4000"


log ""
log "=============================================="
log "=== Preparing Virtualenv for the load test ==="
log "=============================================="
# aiohttp lib which is used in e2e test requires Python>=3.5.3
# test scripts uses new syntax for formatting strings (3.6+)

# Loop through standard python aliases in order to find needed version
PYTHON=
for PYTHON_EXECUTABLE in python python3 python3.6 python3.7
do
    # Skip python executables that don't exist in PATH
    if ! which ${PYTHON_EXECUTABLE} &> /dev/null; then
        continue
    fi

    possible_python=$(which ${PYTHON_EXECUTABLE})
    HAVE=$(${possible_python} --version 2>&1 | awk '{ print $2 }')
    # Stop if version is new enough
    if echo -e "${HAVE}\n3.6" | sort -V | head -1 | grep -q "^3.6$"
    then
        PYTHON=${possible_python}
        break
    fi
done
if [ -z "${PYTHON}" ]
then
    log "Python 3.6 or greater was not found." "ERROR"
    log "Please install it and try again."
    exit 1
else
    log "Using python: ${PYTHON} version: ${HAVE}"
fi

cd "${LOAD_TEST_DIR}"

# Configure virtualenvironment
${PYTHON} -m venv "venv"
venv/bin/pip install --upgrade pip
venv/bin/pip install "${HELPERS_DIR}"
venv/bin/pip install kazoo
venv/bin/pip install locustio==0.9
venv/bin/pip install requests
venv/bin/pip install attr
venv/bin/pip install psutil
venv/bin/pip install tabulate


status=0


log ""
log "==============================="
log "=== Run TaskQueue load test ==="
log "==============================="
LOCUST_LOGS="${LOGS_DIR}/locust"
mkdir "${LOCUST_LOGS}"
VALIDATION_LOG="${LOGS_DIR}/validation"
mkdir "${VALIDATION_LOG}"
export VALIDATION_LOG
export TEST_PROJECT
export RUN_TIME

log "Ensuring queues are configured and empty"
venv/bin/python ./prepare_queues.py --zookeeper-location ${ZOOKEEPER_VM} \
                                    --taskqueue-location ${TQ_LOCATION}

log "Starting task producers with timeout ${LOCUST_TIMEOUT}s"
timeout "${LOCUST_TIMEOUT}" \
    venv/bin/locust --host "${TQ_LOCATION}" --no-web \
                    --clients ${PRODUCERS} \
                    --hatch-rate $((PRODUCERS/3 + 1)) \
                    --csv-base-name "${LOCUST_LOGS}/producers" \
                    --logfile "${LOCUST_LOGS}/producers-log" \
                    --locustfile ./producer_locust.py \
                    > "${LOCUST_LOGS}/producers-out" 2>&1 &
PRODUCERS_PID=$!
export PRODUCERS_PID  # let workers know when producers are terminated

log "Starting workers with timeout ${LOCUST_TIMEOUT}s"
timeout "${LOCUST_TIMEOUT}" \
    venv/bin/locust --host "${TQ_LOCATION}" --no-web \
                    --clients ${WORKERS} \
                    --hatch-rate $((WORKERS/10 + 1)) \
                    --csv-base-name "${LOCUST_LOGS}/workers" \
                    --logfile "${LOCUST_LOGS}/workers-log" \
                    --locustfile ./worker_locust.py \
                    > "${LOCUST_LOGS}/workers-out" 2>&1 &
WORKERS_PID=$!

set +e

log "Waiting for producers to finish work or timeout..."
wait ${PRODUCERS_PID}
PRODUCERS_STATUS=$?
if [ ${PRODUCERS_STATUS} == 124 ]; then
  log "Producers timed out to finish work in ${LOCUST_TIMEOUT}s" "ERROR"
  status=1
elif [ ${PRODUCERS_STATUS} != 0 ]; then
  log "Producers exited with non-zero status (${PRODUCERS_STATUS})" "WARNING"
  log "It's probably because some requests were failed. Ignoring it."
fi

log "Waiting for workers to finish work or timeout..."
wait ${WORKERS_PID}
WORKERS_STATUS=$?
if [ ${WORKERS_STATUS} == 124 ]; then
  log "Workers timed out to finish work in ${LOCUST_TIMEOUT}s" "ERROR"
  status=1
elif [ ${WORKERS_STATUS} != 0 ]; then
  log "Workers exited with non-zero status (${WORKERS_STATUS})" "WARNING"
  log "It's probably because some requests were failed. Ignoring it."
fi

set -e

log "Verifying consistency of taskqueue activity log"
venv/bin/python ./check_consistency.py --validation-log ${VALIDATION_LOG} \
                                       --taskqueue-location ${TQ_LOCATION} \
                                       --ignore-exceeded-retry-limit \
                                       || status=1

log "Verifying performance reported by locust"
venv/bin/python ./check_performance.py --locust-log ${LOCUST_LOGS} || status=1

exit ${status}
