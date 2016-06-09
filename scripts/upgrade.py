""" This script checks and performs an upgrade (if any) is needed for this deployment. """

import json
import os
import sys
import yaml

import datastore_upgrade

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
from dbconstants import *

# Version for which Datastore upgrade is needed.
UPGRADE_NEEDED_VERSION = "3.0.0"

# JSON file location to record the status of the processes.
UPGRADE_JSON_FILE = '/var/log/appscale/upgrade-status-'

# Data upgrade status key.
DATA_UPGRADE = 'Data Upgrade'

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

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length != 10:
    sys.exit(1)

  available_version = ""
  timestamp = ""
  for index in range(args_length):
    if index == 0:
      continue
    if index == 1:
      available_version = str(sys.argv[index])
      continue
    if index == 2:
      keyname = str(sys.argv[index])
      continue
    if index == 3:
      timestamp = str(sys.argv[index])
      continue
    if (str(sys.argv[index]) == ("--master")):
      master_ip_arg = str(sys.argv[index+1])
    if (str(sys.argv[index]) == ("--zookeeper")):
      zk_ips_arg = str(sys.argv[index+1])
    if (str(sys.argv[index]) == ("--database")):
      db_ips_arg = str(sys.argv[index+1])

  zk_ips = yaml.load(zk_ips_arg)
  db_ips = yaml.load(db_ips_arg)
  master_ip = yaml.load(master_ip_arg)

  upgrade_status_dict = {}
  # Run datastore upgrade script if required.
  if is_data_upgrade_needed(available_version):
    data_upgrade_status = {}
    datastore_upgrade.run_datastore_upgrade(zk_ips, db_ips, master_ip,
      data_upgrade_status, keyname)
    upgrade_status_dict[DATA_UPGRADE] = data_upgrade_status

  # Write the upgrade status dictionary to the upgrade-status.json file.
  write_to_json_file(upgrade_status_dict, timestamp)
