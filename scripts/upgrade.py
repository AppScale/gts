""" This script checks and performs an upgrade (if any) is needed for this deployment. """

import argparse
import logging
import os
import sys

import datastore_upgrade

from datastore_upgrade import run_datastore_upgrade
from datastore_upgrade import start_cassandra
from datastore_upgrade import start_zookeeper
from datastore_upgrade import write_to_json_file

from appscale.datastore.dbconstants import AppScaleDBError

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
from constants import LOG_FORMAT

sys.path.append\
  (os.path.join(os.path.dirname(__file__), '../InfrastructureManager'))
from utils import utils


def init_parser():
  """ Initializes the command line argument parser.
    Returns:
      A parser object.
  """
  parser = argparse.ArgumentParser(
    description='Checks if any upgrade is required and runs the script for the process.')
  parser.add_argument('--keyname', help='The deployment keyname')
  parser.add_argument('--log-postfix', help='An identifier for the status log')
  parser.add_argument('--db-master', required=True,
                      help='The IP address of the DB master')
  parser.add_argument('--zookeeper', nargs='+',
                      help='A list of ZooKeeper IP addresses')
  parser.add_argument('--database', nargs='+',
                      help='A list of DB IP addresses')
  parser.add_argument('--replication', type=int,
                      help='The keyspace replication factor')
  return parser


if __name__ == "__main__":
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  parser = init_parser()
  args = parser.parse_args()
  status = {'status': 'inProgress', 'message': 'Starting services'}
  write_to_json_file(status, args.log_postfix)

  db_access = None
  zookeeper = None
  try:
    # Ensure monit is running.
    relevant_ips = set(args.zookeeper) | set(args.database)
    for ip in relevant_ips:
      utils.ssh(ip, args.keyname, 'service monit start')

    start_zookeeper(args.zookeeper, args.keyname)
    start_cassandra(args.database, args.db_master, args.keyname)
    datastore_upgrade.wait_for_quorum(
      args.keyname, len(args.database), args.replication)
    db_access = datastore_upgrade.get_datastore()

    # Exit early if a data layout upgrade is not needed.
    if db_access.valid_data_version():
      status = {'status': 'complete', 'message': 'The data layout is valid'}
      sys.exit()

    zookeeper = datastore_upgrade.get_zookeeper(args.zookeeper)
    try:
      total_entities = datastore_upgrade.estimate_total_entities(
        db_access.session, args.db_master, args.keyname)
    except AppScaleDBError:
      total_entities = None
    run_datastore_upgrade(db_access, zookeeper, args.log_postfix,
                          total_entities)
    status = {'status': 'complete', 'message': 'Data layout upgrade complete'}
  except Exception as error:
    status = {'status': 'error', 'message': error.message}
    sys.exit()
  finally:
    # Always write the result of the upgrade and clean up.
    write_to_json_file(status, args.log_postfix)

    if zookeeper is not None:
      zookeeper.close()
    if db_access is not None:
      db_access.close()

    datastore_upgrade.stop_cassandra(args.database, args.keyname)
    datastore_upgrade.stop_zookeeper(args.zookeeper, args.keyname)
