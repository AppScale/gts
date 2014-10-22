""" Deletes all logs for the system and applications. """
import os
import sys

import groomer
from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info


def main():
  """ This main function allows you to run the groomer manually. """
  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  datastore_path = "localhost:8888"
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  ds_groomer = groomer.DatastoreGroomer(zookeeper, table, datastore_path)
  try:
    ds_groomer.remove_old_logs(None)
  finally:
    zookeeper.close()

if __name__ == "__main__":
  main()
