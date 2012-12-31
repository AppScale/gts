#!/usr/bin/env python
# Programmer: Navraj Chohan

import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../hbase/"))  
import hbase_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import file_io

class FakeHBaseClient():
  """ Fake hbase client class for mocking """
  def __init__(self):
    return
  def getRowsWithColumns(self, table_name, row_keys, column_list):
    return "NS"
  def mutateRows(self, table_name, all_mutations):
    return []
  def disableTable(self, table_name):
    return 
  def deleteTable(self, table_name):
    return
  def createTable(self, table_name):
    return
  def scannerOpenWithStop(self, table_name, start_key, end_key, col_names):
    return []
  def scannerGetList(self, scanner, rowcount):
    return []
  def scannerClose(self, scanner):
    return
 
class TestHBase(unittest.TestCase):
  def testConstructor(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()

  def testGet(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert {} == db.batch_get_entity('table', [], [])

  def testPut(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.batch_put_entity('table', [], [], {})

  def testDeleteTable(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.delete_table('table')

  def testDelete(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.batch_delete('table', [])

  def testRangeQuery(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(hbase_interface.DatastoreProxy).should_receive("create_connection") \
        .and_return(FakeHBaseClient())

    db = hbase_interface.DatastoreProxy()
    assert [] == db.range_query("table", [], "start", "end", 0)

if __name__ == "__main__":
  unittest.main()    
