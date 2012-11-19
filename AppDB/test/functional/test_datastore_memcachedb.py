import os
import sys
import unittest
from test import test_support
import time
import test_datastore
import appscale_datastore
from dbconstants import *

class TestDatastoreMemcachedb(test_datastore.TestDatastoreFunctions):
  def setUp(self):
    self.db = appscale_datastore.DatastoreFactory.getDatastore("memcachedb")
    self.error_code = "DB_ERROR:"
    # create default schema
    self.db.create_table(USERS_TABLE, USERS_SCHEMA)
    self.db.create_table(APPS_TABLE, APPS_SCHEMA)

def test_main():
  # start memcachedb in single node
  os.system("pkill -9 memcached")
  os.system("pkill -9 memcachedb")
  os.system("memcached -d -m 32 -p 11211 -u root")
  os.system("memcachedb -p 30000 -u root -d -r -H /tmp/memcachedb -N -M -n 1")
  test_support.run_unittest(TestDatastoreMemcachedb)
  # stop memcachedb
  os.system("pkill -9 memcached")
  os.system("pkill -9 memcachedb")
  os.system("rm -rf /tmp/memcachedb")

if __name__ == "__main__":
  test_main()
