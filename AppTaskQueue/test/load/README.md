# AppScale TaskQueue Load Test

The load test uses locustio to create configurable number of virtual 
TaskQueue users. There are two types of users:

 - Producers (defined in `./producer_locust.py` script).
 - Workers (defines in `./worker_locust.py` script).

Each producer and worker repeatedly sends request to TaskQueue
with delay about 1 second. Every action performed with a task is reported
to validation log. The log is used for further consistency validation
of TaskQueue activity.

This directory (`AppTaskQueue/test/load`) contains everything needed
for producing high load, measuring performance and validation of
TaskQueue behavior. But it requires existing TaskQueue servers
running behind a load balancer.

`AppTaskQueue/test/suits/run-load-test.sh` script can run entire
test automatically. It does number of things:
 1. Provisions TaskQueue service on VMs (started from appscale image).
 2. Initializes test project.
 3. Makes sure pull queue is defined and is empty.
 4. Starts specified number of users to produce high load.
 5. Analyses outcomes, reports result.


### Running load test manually

Assuming Python 3.6+ is installed on you local machine, 
Taskqueue and Zookeeper are available. Let's say TaskQueue address 
is 10.10.1.20:4000, Zookeeper is available at 10.10.1.25.

#### Step-by-step instruction
 1. Switch to `AppTaskQueue/test/load` directory.
 2. Install required packages:
    ```bash
    python3.6 -m venv "venv"
    venv/bin/pip install --upgrade pip
    venv/bin/pip install ../helpers
    venv/bin/pip install kazoo
    venv/bin/pip install locustio
    venv/bin/pip install requests
    venv/bin/pip install attr
    venv/bin/pip install psutil
    venv/bin/pip install tabulate
    ```
 3. Make sure pull queue is defined and empty:
    ```bash
    venv/bin/python ./prepare_queues.py --zookeeper-location 10.10.1.20:4000 \
                                        --taskqueue-location 10.10.1.25
    ```
 4. Prepare logs directory and export environmental variables:
    ```bash
    mkdir ./logs
    export VALIDATION_LOG=./logs
    export TEST_PROJECT=tq-test-proj
    ```
 5. Start producer and worker locusts, wait for processes to exit:
    ```bash
    timeout 1800 \
        venv/bin/locust --host 10.10.1.20:4000 --no-web \
                        --clients 2000 --hatch-rate 200 --num-request 10000 \
                        --csv-base-name "./logs/producers" \
                        --logfile "./logs/producers-log" \
                        --locustfile ./producer_locust.py \
                        > "./logs/producers-out" 2>&1 &
     
    PRODUCERS_PID=$!
    export PRODUCERS_PID    # let workers know when producers are terminated
    
    timeout 2100 \
        venv/bin/locust --host 10.10.1.20:4000 --no-web \
                        --clients 200 --hatch-rate 20 \
                        --csv-base-name "./logs/workers" \
                        --logfile "./logs/workers-log" \
                        --locustfile ./worker_locust.py \
                        > "./logs/workers-out" 2>&1 &
    WORKERS_PID=$!
    
    wait ${PRODUCERS_PID}
    wait ${WORKERS_PID}
    # It worth checking status 124 (timeout) and other non-zero codes
    ```
 6. Check outcomes:
    ```bash
    venv/bin/python ./check_consistency.py --validation-log ./logs \
                                           --taskqueue-location 10.10.1.20:4000 \
                                           --ignore-exceeded-retry-limit
    venv/bin/python ./check_performance.py --locust-log ./logs
    ```


### Running load test using test-suite

Let's say you have 6 VMs started from appscale image and connected 
to the same private network. Assuming your ssh key `~/.ssh/id_rsa` is
authorized for `ubuntu` user on all of those machines (and ubuntu user has sudo
privileges).

#### Step-by-step instruction
 1. Create layout.txt file containing wanted TaskQueue cluster layout:
    ```bash
    cat > ./layout.txt << CONTENT
    ROLE          PUBLIC_IP/HOST_NAME  PRIVATE_IP
    postgres      192.168.100.41       10.10.8.21
    zookeeper     192.168.100.42       10.10.8.22
    loadbalancer  192.168.100.43       10.10.8.23
    taskqueue     192.168.100.42       10.10.8.22
    taskqueue     192.168.100.43       10.10.8.23
    taskqueue     192.168.100.44       10.10.8.24
    taskqueue     192.168.100.45       10.10.8.25
    CONTENT
    ```
    Read `AppTaskQueue/test/suites/layout-example.txt` for more details on layout file.
 2. Start the load test:
    ```bash
    ${APP_TASK_QUEUE_DIR}/test/suites/run-load-test.sh \
                       --key-location ~/.ssh/id_rsa \
                       --user-name ubuntu \
                       --layout-file ./layout.txt \
                       --tq-per-vm 10 \
                       --producers 2000 \
                       --workers 200 \
                       --locust-timeout 3600 \
                       --logs-dir .logs/
    ```


### Notes about consistency validation

Every line in the validation log corresponds to a single task and describes
what action has been done with it (ADDED, LEASED or DELETED).
Here are examples of log entries:

```
1535025645514 ADDED b4ed57cb-4a5f-44f4-960d-9a1177159534 13950 37 8852
1535025922571 LEASED c4c49dea-fb75-4ec5-b50c-5ecc63e6e624 1535025952384
1535025925987 DELETED 34405b92-eafa-4d23-9afe-5e9536d5fc5e 5
```

Where items in line have a following meaning:
```
<TIMESTAMP_MS> ADDED <TASK_ID> <WORK_TIME_FOR_RETRIES>
<TIMESTAMP_MS> LEASED <TASK_ID> <LEASE_EXPIRES>
<TIMESTAMP_MS> DELETED <TASK_ID> <RETRY_COUNT_AT_DELETION_TIME>
```

`./check_consistency.py` script verifies that history of every task
matches the pattern:

`ADDED > LEASED (> LEASED)* (DELETED)?` Where:
 - Task is not leased before previous lease is expired.
 - Task is not leased more than retry_limit times
   (it's ignored for now as our implementation of TaskQueue allows more retries).
 - Task should be retried until it's deleted (succeeded) or run out of retries.
 - Task can't be deleted or leased before it's added.


### Future work

#### Comparing performance to previous builds

Currently, main goal of the load test is to prove that TaskQueue behaves
consistently under load. `./check_performance.py` script just parses locust
logs and prints some performance properties, it doesn't verify
if performance was improved or worsened comparing to master.
The test should fail if noticeable impairment is in place.

#### Add more performance metrics

As of now, the test collect information about behavior consistency,
service throughput, average response time response time distribution
and failures percent.

It would be useful to track CPU, memory and traffic usage on all of
machines in the cluster.

#### Test more load scenarios

Push Queue producer and worker should be implemented. Current Pull Queue
producer and worker should start using tags so more types of load will be
covered.

Helper scripts need to be implemented for easier testing of different
scenarios.

#### Configure .gitignore to ignore test artifacts

The test can be run outside particular folder, so it is currently problematic
to configure `.gitignore` to match `venv`, `Python3.6.6`, `null`, `logs`, etc.
files which are created by the test.

Probably we should force user to run the test from some particular folder
so we know where artifact files are located. 

#### Run locust cluster on (optionally) external machine

A single locust process can run limited number (~thousands) of virtual clients.
Simulation of higher load may require multiple locust processes, consequently,
one machine may not be enough.
Fortunately, locustio supports cluster mode. In this mode many locust processes
are connected to a single cluster managed from master process.

So at some point of time we will have to implement mechanisms for starting
locust cluster, optionally on multiple machines.
