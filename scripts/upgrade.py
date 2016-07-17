""" This script checks and performs an upgrade (if any) is needed for this deployment. """

import argparse
import sys

import datastore_upgrade

from datastore_upgrade import is_data_upgrade_needed
from datastore_upgrade import write_to_json_file

# Data upgrade status key.
DATA_UPGRADE = 'Data-Upgrade'


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
  return parser


if __name__ == "__main__":

  parser = init_parser()
  args = parser.parse_args()

  try:
    if not is_data_upgrade_needed(args.database, args.db_master, args.keyname):
      status = {'Status': 'Not executed',
                'Message': 'AppScale is currently at its latest version'}
      write_to_json_file(status, args.log_postfix)
      sys.exit()
  except Exception as error:
    status = {'Status': 'Not executed', 'Message': error.message}
    write_to_json_file(status, args.log_postfix)
    sys.exit()

  data_upgrade_status = {}
  datastore_upgrade.run_datastore_upgrade(
    args.zookeeper, args.database, args.db_master, data_upgrade_status,
    args.keyname)

  # Write the upgrade status dictionary to the upgrade-status.json file.
  write_to_json_file({DATA_UPGRADE: data_upgrade_status}, args.log_postfix)
