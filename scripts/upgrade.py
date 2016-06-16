""" This script checks and performs an upgrade (if any) is needed for this deployment. """

import argparse
import json
import os
import sys
import yaml

import datastore_upgrade

LATEST_VERSION = 'Latest-version'

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
from dbconstants import *

# Version for which Datastore upgrade is needed.
UPGRADE_NEEDED_VERSION = "3.0.0"

# JSON file location to record the status of the processes.
UPGRADE_JSON_FILE = '/var/log/appscale/upgrade-status-'

# Data upgrade status key.
DATA_UPGRADE = 'Data-Upgrade'

# .JSON file extention.
JSON_FILE_EXTENTION = ".json"

def is_data_upgrade_needed(version):
  """Checks if for this version of AppScale datastore upgrade is needed.
  Args:
    version: The latest version available to upgrade to.
  Returns: True, if given version matches the one for which data upgrade is needed.
    False, otherwise.
  """
  if version == UPGRADE_NEEDED_VERSION:
    return True
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
  parser.add_argument('version', type=str, help='available upgrade version')
  parser.add_argument('keyname', type=str, help='keyname')
  parser.add_argument('timestamp', type=str, help='timestamp to attach to the status file')
  parser.add_argument('--master', required=True, help='master node IP')
  parser.add_argument('--zookeeper', required=True, help='zookeeper node IPs')
  parser.add_argument('--database', required=True, help='database node IPs')
  return parser

if __name__ == "__main__":

  parser = init_parser()
  args = parser.parse_args()

  zk_ips = yaml.load(args.zookeeper)
  db_ips = yaml.load(args.database)
  master_ip = yaml.load(args.master)

  upgrade_status_dict = {}
  # Run datastore upgrade script if required.
  if is_data_upgrade_needed(args.version):
    data_upgrade_status = {}
    datastore_upgrade.run_datastore_upgrade(zk_ips, db_ips, master_ip,
      data_upgrade_status, args.keyname)
    upgrade_status_dict[DATA_UPGRADE] = data_upgrade_status

  if not upgrade_status_dict.keys():
    upgrade_status_dict = {'Status': 'Not executed', 'Message':'AppScale is currently at its latest version'}

  # Write the upgrade status dictionary to the upgrade-status.json file.
  write_to_json_file(upgrade_status_dict, args.timestamp)
