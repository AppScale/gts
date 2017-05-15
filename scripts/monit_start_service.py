#!/usr/bin/env python

import argparse
import logging

from appscale.common import monit_app_configuration
from appscale.common import monit_interface
from appscale.datastore.cassandra_env import cassandra_interface
from distutils.spawn import find_executable
from subprocess import check_output

import datastore_upgrade

# The location of the Cassandra binary on the local filesystem.
CASSANDRA_EXECUTABLE = cassandra_interface.CASSANDRA_INSTALL_DIR \
  + "/cassandra/bin/cassandra"

# The location on the local file system where we write the process ID
# that Cassandra runs on.
PID_FILE = "/tmp/appscale-cassandra.pid"


def start_cassandra():
  logging.info('Starting Cassandra')

  bash = find_executable('bash')
  su = find_executable('su')

  cassandra_cmd = ' '.join([CASSANDRA_EXECUTABLE, '-p', PID_FILE])
  start_cmd = "{} -c '{}' cassandra".format(su, cassandra_cmd)
  stop_cmd = "{} -c 'kill $(cat {})'".format(bash, PID_FILE)

  watch = datastore_upgrade.CASSANDRA_WATCH_NAME
  monit_app_configuration.create_daemon_config(
    watch, start_cmd, stop_cmd, PID_FILE)

  if not monit_interface.start(watch):
    logging.error('Monit was unable to start Cassandra')
    return 1
  else:
    logging.info('Monit configured for Cassandra')
    return 0


def start_zookeeper():
  """ Creates a monit configuration file and prompts Monit to start service.
  Args:
    service_name: The name of the service to start.
  """
  logging.info('Starting ZooKeeper')

  service = find_executable('service')
  zk_service = 'zookeeper-server'
  if 'zookeeper\n' in check_output('service --status-all', shell=True):
    zk_service = 'zookeeper'

  start_cmd = ' '.join([service, zk_service, 'start'])
  stop_cmd = ' '.join([service, zk_service, 'stop'])

  watch = datastore_upgrade.ZK_WATCH_NAME
  match_cmd = 'org.apache.zookeeper.server.quorum.QuorumPeerMain'

  monit_app_configuration.create_custom_config(
    watch, start_cmd, stop_cmd, match_cmd)

  if not monit_interface.start(watch):
    logging.error('Monit was unable to start ZooKeeper')
    return 1
  else:
    logging.info('Monit configured for ZooKeeper')
    return 0


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('service', choices=['cassandra', 'zookeeper'])
  args = parser.parse_args()

  if args.service == 'cassandra':
    start_cassandra()
  elif args.service == 'zookeeper':
    start_zookeeper()
