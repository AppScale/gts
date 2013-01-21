#!/usr/bin/env python
# Datastore testing abstract class
#
# NOMURA Yoshihide <nomura@pobox.com>

import sys
import time
import unittest
import base64
from threading import Thread
from test import test_support
import appscale_datastore
import helper_functions as hf
from dbconstants import *

USERS_VALUES = ["suwanny@gmail.com", "11", "2009", "2009", "2009", 
    "bbs", "xxx", "xxx", "1", "yyy", 
    "0.0.0.0", "2009", "zzz", "yes"]

APPS_VALUES = ["name",  "python", "version","owner","admins_list","host",
    "port","creation_date", "last_time_updated_date", "yaml_file", "cksum", 
    "num_entries", "xxxx", "yes", "class", "index"]

ERROR_CODE = "DB_ERROR:"

datastore_name = None

def createRandomList(number_of_columns, column_name_len):
  columns = [] 
  for ii in range(0, number_of_columns):
    columns += [hf.random_string(column_name_len)]
  return columns

class TestDatastoreFunctions(unittest.TestCase):

  def test_getput(self):
    ret = self.db.put_entity(USERS_TABLE, "1", USERS_SCHEMA, USERS_VALUES)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.put_entity(APPS_TABLE, "1", APPS_SCHEMA, APPS_VALUES)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(USERS_TABLE, "1", USERS_SCHEMA)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(USERS_VALUES[0], ret[1])
    self.assertEqual(USERS_VALUES[1], ret[2])
    ret = self.db.get_entity(APPS_TABLE, "1", APPS_SCHEMA)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(APPS_VALUES[0], ret[1])
    self.assertEqual(APPS_VALUES[1], ret[2])
    ret = self.db.delete_row(USERS_TABLE, "1")
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_row(APPS_TABLE, "1")
    self.assertEqual(self.error_code, ret[0])

  def test_getput_longkey(self):
    longKey = "1111111111111111111111111111111111111111111111111111111111111111111111"
    ret = self.db.put_entity(USERS_TABLE, longKey, USERS_SCHEMA, USERS_VALUES)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(USERS_TABLE, longKey, USERS_SCHEMA)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(USERS_VALUES[0], ret[1])
    self.assertEqual(USERS_VALUES[1], ret[2])
    ret = self.db.delete_row(USERS_TABLE, longKey)
    self.assertEqual(self.error_code, ret[0])

  def test_getput_longkey2(self):
    longKey = "1111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111"
    ret = self.db.put_entity(USERS_TABLE, longKey, USERS_SCHEMA, USERS_VALUES)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(USERS_TABLE, longKey, USERS_SCHEMA)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(USERS_VALUES[0], ret[1])
    self.assertEqual(USERS_VALUES[1], ret[2])
    ret = self.db.delete_row(USERS_TABLE, longKey)
    self.assertEqual(self.error_code, ret[0])

  def test_get_each_column(self):
    table = "eachcolumntest"
    key = "eachcolumntest"
    columns = ["1", "2", "3", "4", "5"]
    values = ["1", "2", "3", "4", "5"]
    ret = self.db.put_entity(table, key, columns, values)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(table, key, columns)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("1", ret[1])
    self.assertEqual("5", ret[5])
    ret = self.db.get_entity(table, key, ["3"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("3", ret[1])
    ret = self.db.get_entity(table, key, ["5"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("5", ret[1])
    ret = self.db.get_entity(table, key, ["1", "2"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("1", ret[1])
    self.assertEqual("2", ret[2])
    ret = self.db.get_entity(table, key, ["4", "5"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("4", ret[1])
    self.assertEqual("5", ret[2])
    ret = self.db.delete_row(table, key)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def notest_get_nonexisting_key(self):
    ret = self.db.get_entity(APPS_TABLE, "dummyappname", ["enabled"])
    self.assertNotEqual(self.error_code, ret[0])

  def notest_delete_nonexisting_key(self):
    ret = self.db.delete_row(APPS_TABLE, "dummyappname")
    self.assertNotEqual(self.error_code, ret[0])

  def notest_delete_row_nonexisting_table(self):
    ret = self.db.delete_row("dummytable", "dummyappname")
    self.assertNotEqual(self.error_code, ret[0])

  def notest_delete_table_nonexisting_table(self):
    ret = self.db.delete_table("dummytable")
    self.assertNotEqual(self.error_code, ret[0])

  def notest_delete_row_twice(self):
    table = "deletetest"
    key = "deletetest"
    ret = self.db.put_entity(table, key, ["value"], ["value"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_row(table, key)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_row(table, key)
    self.assertNotEqual(self.error_code, ret[0])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def test_update_column(self):
    table = "updatecolumntest"
    key = "updatecolumntest"
    columns = ["1", "2", "3", "4", "5"]
    values = ["1", "2", "3", "4", "5"]
    ret = self.db.put_entity(table, key, columns, values)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(table, key, columns)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("1", ret[1])
    ret = self.db.put_entity(table, key, ["1"], ["one"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(table, key, columns)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("one", ret[1])
    ret = self.db.delete_row(table, key)
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def test_enabled(self):
    ret = self.db.put_entity(APPS_TABLE, "enabledtest", ["enabled"], ["true"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "enabledtest", ["enabled"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("true", ret[1])
    ret = self.db.put_entity(APPS_TABLE, "enabledtest", ["enabled"], ["false"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "enabledtest", ["enabled"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("false", ret[1])
    ret = self.db.delete_row(APPS_TABLE, "enabledtest")
    self.assertEqual(self.error_code, ret[0])

  def test_language(self):
    ret = self.db.put_entity(APPS_TABLE, "languagetest", ["language"], ["python"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "languagetest", ["language"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("python", ret[1])
    ret = self.db.delete_row(APPS_TABLE, "languagetest")
    self.assertEqual(self.error_code, ret[0])

  def test_genid(self):
    ret = self.db.put_entity(APPS_TABLE, "genidtest", ["num_entries"], ["1"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "genidtest", ["num_entries"])
    self.assertEqual(self.error_code, ret[0])
    err, value = ret
    value = int(value)
    self.assertEqual(1, value)
    ret = self.db.put_entity(APPS_TABLE, "genidtest", ["num_entries"], [str(value + 1)])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "genidtest", ["num_entries"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("2", ret[1])
    ret = self.db.delete_row(APPS_TABLE, "genidtest")
    self.assertEqual(self.error_code, ret[0])

  def test_getschema(self):
    user_schema = self.db.get_schema(USERS_TABLE)
    self.assertEqual(self.error_code, user_schema[0])
    self.assertEqual(1, user_schema.count("email"))
    self.assertEqual(1, user_schema.count("pw"))
    self.assertEqual(1, user_schema.count("enabled"))
    app_schema = self.db.get_schema(APPS_TABLE)
    self.assertEqual(self.error_code, app_schema[0])
    self.assertEqual(1, app_schema.count("name"))
    self.assertEqual(1, app_schema.count("version"))
    self.assertEqual(1, app_schema.count("enabled"))

  def test_getschema_nonexisting_table(self):
    ret = self.db.get_schema("dummytable")
    self.assertNotEqual(self.error_code, ret[0])

  def test_getput_tar(self):
    f = open('%s/AppDB/test/guestbook.tar.gz' % APPSCALE_HOME, 'r')
    data = f.read()
    encdata = base64.b64encode(data)
    ret = self.db.put_entity(APPS_TABLE, "tartest", ["tar_ball"], [encdata])  
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity(APPS_TABLE, "tartest", ["tar_ball"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(encdata, ret[1])
    ret = self.db.delete_row(APPS_TABLE, "tartest")
    self.assertEqual(self.error_code, ret[0])

  def test_getput_binary(self):
    f = open('%s/AppDB/test/guestbook.tar.gz' % APPSCALE_HOME, 'r')
    data = f.read()
    ret = self.db.put_entity("binarytest", "binarytest", ["Encoded_Entity"], [data])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity("binarytest", "binarytest", ["Encoded_Entity"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(data, ret[1])
    ret = self.db.delete_row("binarytest", "binarytest")
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table("binarytest")
    self.assertEqual(self.error_code, ret[0])

  def test_getput_bigbinary(self):
    f = open('%s/AppDB/test/bigbinary' % APPSCALE_HOME, 'r')
    data = f.read()
    ret = self.db.put_entity("binarytest", "binarytest", ["Encoded_Entity"], [data])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity("binarytest", "binarytest", ["Encoded_Entity"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual(data, ret[1])
    ret = self.db.delete_row("binarytest", "binarytest")
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table("binarytest")
    self.assertEqual(self.error_code, ret[0])

  def test_gettable(self):
    table = "dummytable"
    schema = ["value1", "value2"]
    ret = self.db.put_entity(table, "1", schema, ["1", "2"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.put_entity(table, "2", schema, ["3", "4"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_table(table, schema)
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("1", ret[1])
    self.assertEqual("2", ret[2])
    self.assertEqual("3", ret[3])
    self.assertEqual("4", ret[4])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def test_delete_table(self):
    key = "11111111111111111111111111111"
    ret = self.db.put_entity("deletetest", key, ["value"], ["value"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity("deletetest", key, ["value"])
    self.assertEqual(self.error_code, ret[0])
    self.assertEqual("value", ret[1])
    ret = self.db.delete_table("deletetest")
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.get_entity("deletetest", key, ["value"])
    self.assertNotEqual(self.error_code, ret[0])

  def notest_delete_table_twice(self):
    key = "11111111111111111111111111111"
    ret = self.db.put_entity("deletetest", key, ["value"], ["value"])
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table("deletetest")
    self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table("deletetest")
    self.assertNotEqual(self.error_code, ret[0])

  def test_200requests(self):
    table = "testmulti"
    prekey = "value"
    valuename = "value"
    value = "intervaltestvalue"
    for i in range(200):
      key = prekey + str(i)
      ret = self.db.put_entity(table, key, [valuename], [value])
      self.assertEqual(self.error_code, ret[0])
    for i in range(200):
      key = prekey + str(i)
      ret = self.db.get_entity(table, key, [valuename])
      if len(ret) < 2:
        ret[1] = ""
      self.assertEqual(value, ret[1])
      self.assertEqual(self.error_code, ret[0])
      ret = self.db.delete_row(table, key)
      self.assertEqual(self.error_code, ret[0])
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  # 10 threads get/put/delete 100 requests

  def test_10multi_requests(self):
    table = "testmulti"
    valuename = "value"
    value = "intervaltestvalue"
    # create table before testing
    ret = self.db.put_entity(table, "dummykey", [valuename], [value])
    self.assertEqual(self.error_code, ret[0])

    tlist = []
    for tnum in range(10):
      key = "key" + str(tnum) + "num"
      thread = Thread(target = self._multi50requests, args = [key])
      thread.start()
      tlist.append(thread)

    for t in tlist:
      t.join()
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def test_20multi_requests(self):
    table = "testmulti"
    valuename = "value"
    value = "intervaltestvalue"
    # create table before testing
    ret = self.db.put_entity(table, "dummykey", [valuename], [value])
    self.assertEqual(self.error_code, ret[0])

    tlist = []
    for tnum in range(20):
      key = "key" + str(tnum) + "num"
      thread = Thread(target = self._multi50requests, args = [key])
      thread.start()
      tlist.append(thread)

    for t in tlist:
      t.join()
    ret = self.db.delete_table(table)
    self.assertEqual(self.error_code, ret[0])

  def _multi50requests(self, prekey):
    table = "testmulti"
    valuename = "value"
    value = "intervaltestvalue"
    for i in range(50):
      key = prekey + str(i)
      ret = self.db.put_entity(table, key, [valuename], [value])
      self.assertEqual(self.error_code, ret[0])
    for i in range(50):
      key = prekey + str(i)
      ret = self.db.get_entity(table, key, [valuename])
      if len(ret) < 2:
        ret[1] = ""
      self.assertEqual(value, ret[1])
      self.assertEqual(self.error_code, ret[0])
    for i in range(50):
      key = prekey + str(i)
      ret = self.db.delete_row(table, key)
      self.assertEqual(self.error_code, ret[0])

  def setUp(self):
    global datastore_name
    self.db = appscale_datastore.DatastoreFactory.getDatastore(datastore_name)
    self.error_code = ERROR_CODE

def test_main():
  # prepare bigbinary
  filename = "%s/AppDB/test/bigbinary" % APPSCALE_HOME
  os.system("dd if=/dev/zero of=%s bs=1M count=20" % filename)

  # do test
  global datastore_name
  datastore_name = sys.argv[1]
  test_support.run_unittest(TestDatastoreFunctions)

if __name__ == "__main__":
  test_main()
