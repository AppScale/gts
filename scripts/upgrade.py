""" This script checks and performs an upgrade (if any) is needed for this deployment. """

import argparse
import json

import datastore_upgrade

# JSON file location to record the status of the processes.
UPGRADE_JSON_FILE = '/var/log/appscale/upgrade-status-'

# Data upgrade status key.
DATA_UPGRADE = 'Data-Upgrade'

# .JSON file extention.
JSON_FILE_EXTENTION = ".json"

def is_data_upgrade_needed():
  """Checks if for this version of AppScale datastore upgrade is needed.

  Returns:
    A boolean indicating whether or not a data upgrade is required.
  """
  return False

def write_to_json_file(data, timestamp):
  """ Writes the dictionary containing the status of operations performed
  during the upgrade process into a JSON file.
  Args:
    data: A dictionary containing status of upgrade operations performed.
    timestamp: The timestamp passed from the tools to append to the upgrade
    status log file.
  """
  upgrade_status_file = UPGRADE_JSON_FILE + timestamp + JSON_FILE_EXTENTION
  with open(upgrade_status_file, 'w') as file:
    json.dump(data, file)

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

  upgrade_status_dict = {}
  # Run datastore upgrade script if required.
  if is_data_upgrade_needed():
    data_upgrade_status = {}
    datastore_upgrade.run_datastore_upgrade(
      args.zookeeper, args.database, args.db_master, data_upgrade_status,
      args.keyname)
    upgrade_status_dict[DATA_UPGRADE] = data_upgrade_status

  if not upgrade_status_dict.keys():
    upgrade_status_dict = {'Status': 'Not executed', 'Message':'AppScale is currently at its latest version'}

  # Write the upgrade status dictionary to the upgrade-status.json file.
  write_to_json_file(upgrade_status_dict, args.log_postfix)
