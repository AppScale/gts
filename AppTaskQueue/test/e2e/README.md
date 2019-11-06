# AppScale TaskQueue Tests

Most end-to-end tests are in the [Hawkeye repository](https://github.com/AppScale/hawkeye/).
They test the behavior through a runtime process.
These tests are for making calls directly to the taskqueue.


## Test existing Taskqueue servers


### Prerequisites

 - Python 3.6+
 - helpers package (can be found at appscale/AppTaskQueue/test/helpers)
 - pytest package
 - kazoo package
 - reachable TaskQueue servers
 - reachable Zookeeper server used by TaskQueue


### Inputs

 - `TEST_PROJECT` environmental variable which determines project name to use.
   You don't need to define queues for this project or do any preparations
   regarding the project. Test will do it on its own.
 - `--tq-locations <IP:PORT> <IP:PORT> ...` repeated parameter passed to pytest.
 - `--zk-location <IP:PORT>` parameter passed to pytest.


### Example

Let's say you have Vagrant VM with public IP 172.28.128.12 and private IP
10.0.2.15. TaskQueue is listening on 172.28.128.12:8080 and
172.28.128.12:8081. Zookeeper is running on default port on the same machine.

```
cd appscale/AppTaskQueue/test/e2e
python3.6 -m venv "venv"
venv/bin/pip install --upgrade pip
venv/bin/pip install ../helpers
venv/bin/pip install pytest
venv/bin/pip install kazoo

export TEST_PROJECT="test-project"

venv/bin/pytest --tq-locations 172.28.128.12:8080 172.28.128.12:8081 \
                --zk-location 172.28.128.12
```


## Starting TQ and running tests on bare AppScale machine

You can use prepared provisioning script at
`appscale/AppTaskQueue/test/suites/run-e2e-tests.sh`
if you have a VM started from AppScale image with SSH access to it.

The script:
 - Ensures that needed version of python is installed on the local machine;
 - Creates virtualenv on the local machine and installs needed python packages;
 - Starts Zookeeper on the VM and creates needed nodes there;
 - Installs, starts and configures Postgres on the VM;
 - Starts TaskQueue on the VM using Postgres as a backend for pull queues;
 - Runs e2e tests;


### Prerequisites

 - Machine started from AppScale image or Ubuntu machine
   with appscale manually built on it.
 - SSH access to the machine.


### Inputs

```
[user@host]$ appscale/AppTaskQueue/test/suites/run-e2e-tests.sh --help
Usage: run-e2e-tests.sh --key-location <KEY> --user-name <USER> --vm-addr <HOST> --vm-private-ip <IP> [--logs-dir <DIR>]

Options:
   --key-location <KEY>  Private key file for access to the machine
   --user-name <USER>    User name to use for access to the machine
   --vm-addr <HOST>      Hostname ot public IP of the machine
                         to start TaskQueue on
   --vm-private-ip <IP>  Private IP of the machine to start TaskQueue on
   --logs-dir <DIR>      Directory to save logs to (default: ./logs)
```


### Example

Let's say you have Vagrant VM with public IP 172.28.128.12 and private IP
10.0.2.15 and your ssh key (`~/.ssh/id_rsa`) is added to
`vm:/home/vagrant/.ssh/authorized_keys`

```
mkdir ./taskqueue-e2e-test-logs

appscale/AppTaskQueue/test/suites/run-e2e-tests.sh \
    --key-location ~/.ssh/id_rsa \
    --user-name vagrant \
    --vm-addr 172.28.128.12 \
    --vm-private-ip 10.0.2.15 \
    --logs-dir ./taskqueue-e2e-test-logs \
    | tee ./taskqueue-e2e-test-logs/console
```
