#!/usr/bin/env python

import logging
import os
import subprocess
import sys

from appscale.datastore.cassandra_env import cassandra_interface
from appscale.datastore.zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
from constants import APPSCALE_HOME
import monit_app_configuration
import monit_interface

import datastore_upgrade

# The location of the Cassandra binary on the local filesystem.
CASSANDRA_EXECUTABLE = cassandra_interface.CASSANDRA_INSTALL_DIR \
  + "/cassandra/bin/cassandra"

# The location on the local file system where we write the process ID
# that Cassandra runs on.
PID_FILE = "/tmp/appscale-cassandra.pid"

# The default port to connect to Cassandra.
CASSANDRA_PORT = 9999

def start_service(service_name):
  """ Creates a monit configuration file and prompts Monit to start service.
  Args:
    service_name: The name of the service to start.
  """
  logging.info("Starting " + service_name)
  watch_name = ""
  if service_name == datastore_upgrade.CASSANDRA_WATCH_NAME:
    cassandra_cmd = CASSANDRA_EXECUTABLE + " -p " + PID_FILE
    start_cmd = 'su -c "{0}" cassandra'.format(cassandra_cmd)
    stop_cmd = "/usr/bin/python2 " + APPSCALE_HOME + "/scripts/stop_service.py java cassandra"
    watch_name = datastore_upgrade.CASSANDRA_WATCH_NAME
    ports = [CASSANDRA_PORT]
    match_cmd = cassandra_interface.CASSANDRA_INSTALL_DIR

  if service_name == datastore_upgrade.ZK_WATCH_NAME:
    zk_server="zookeeper-server"
    command = 'service --status-all|grep zookeeper$'
    if subprocess.call(command, shell=True) == 0:
      zk_server = "zookeeper"

    start_cmd = "/usr/sbin/service " + zk_server + " start"
    stop_cmd = "/usr/sbin/service " + zk_server + " stop"
    watch_name = datastore_upgrade.ZK_WATCH_NAME
    match_cmd = "org.apache.zookeeper.server.quorum.QuorumPeerMain"
    ports = [zk.DEFAULT_PORT]

  monit_app_configuration.create_config_file(watch_name, start_cmd, stop_cmd,
    ports, upgrade_flag=True, match_cmd=match_cmd)

  if not monit_interface.start(watch_name):
    logging.error("Monit was unable to start " + service_name)
    return 1
  else:
    logging.info('Monit configured for {}'.format(service_name))
    return 0


if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 2:
    sys.exit(1)

  service_name = (str(sys.argv[1]))
  start_service(service_name)
