import json
import os
import sys

import datastore_upgrade

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
from dbconstants import *

# Version for which Datastore upgrade is needed.
UPGRADE_NEEDED_VERSION = "3.0.0"

# JSON file location to record the status of the processes.
UPGRADE_JSON_FILE = '/etc/appscale/upgrade-status.json'

# Data upgrade status key
DATA_UPGRADE = 'Data Upgrade'

def is_data_upgrade_needed(version):
  """ """
  if version == UPGRADE_NEEDED_VERSION:
    return True
  return False

def write_to_json_file(data):
  with open(UPGRADE_JSON_FILE, 'w') as file:
    json.dump(data, file)

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 3:
    sys.exit(1)

  zk_location_ips = []
  available_version = ""
  for index in range(args_length):
    if index == 0:
      continue
    if index == 1:
      available_version = str(sys.argv[index])
      continue
  zk_location_ips.append(str(sys.argv[index]))

  upgrade_status_dict = {}
  # Run datastore upgrade script if required.
  if is_data_upgrade_needed(available_version):
    data_upgrade_status = {}
    datastore_upgrade.run_datastore_upgrade(zk_location_ips, data_upgrade_status)
    upgrade_status_dict[DATA_UPGRADE] = data_upgrade_status

  # Write the upgrade status dictionary to the upgrade-status.json file.
  write_to_json_file(upgrade_status_dict)



