import os
import sys
import unittest
from test import test_support
import time

sys.path.append("/root/appscale/AppDB")

import test_datastore
import appscale_datastore

ERROR_CODE = "DB_ERROR:"

class TestDatastoreScalaris(test_datastore.TestDatastoreFunctions):
  def setUp(self):
    self.db = appscale_datastore.DatastoreFactory.getDatastore("scalaris")
    self.error_code = ERROR_CODE

  def test_get_interval(self):
    table = "intervaltest"
    key = "value"
    value = "intervaltestvalue"
    ret = self.db.put_entity(table, table, [key], [value])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(table, table, [key])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(value, ret[1])
    for i in range(1,10):
      time.sleep(0.5)
      ret = self.db.get_entity(table, table, [key])
      self.assertEqual(self.error_code, ret[0])
      self.assertEqual(value, ret[1])
    ret = self.db.delete_row(table, table)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

def test_main():
  test_support.run_unittest(TestDatastoreScalaris)

if __name__ == "__main__":
  test_main()
