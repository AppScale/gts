#!/usr/bin/env python
# Programmer: Navraj Chohan

import pycassa
import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../cassandra"))  
import cassandra_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import helper_functions 

class FakeCassClient():
  """ Fake cassandra client class for mocking """
  def __init__(self):
    return
  def multiget_slice(self, rk, path, slice_predicate, consistency):
    return {}

class FakePool():
  """ Fake cassandra connection pool for mocking """
  def get(self):
    return FakeCassClient()
  def return_conn(self, client):
    return 

class FakeColumnFamily():
  """ Fake column family class for mocking """
  def __init__(self):
    return
  def batch_insert(self, multi_map):
    return
  def get_range(self, start='', finish='', columns='', row_count='', 
                read_consistency_level=''):
    return {}

class FakeSystemManager():
  """ Fake system manager class for mocking """
  def __init__(self):
    return
  def drop_column_family(self, keyspace, table_name):
    return

class TestCassandra(unittest.TestCase):
  def testConstructor(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa).should_receive("ConnectionPool") \
        .and_return(FakePool())

    db = cassandra_interface.DatastoreProxy()

  def testGet(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa).should_receive("ConnectionPool") \
        .and_return(FakePool())

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    assert {} == db.batch_get_entity('table', [], [])

  def testPut(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa) \
        .should_receive("ColumnFamily") \
        .and_return(FakeColumnFamily())

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    assert None == db.batch_put_entity('table', [], [], {})

  def testDeleteTable(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa.system_manager) \
        .should_receive("SystemManager") \
        .and_return(FakeSystemManager())

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    db.delete_table('table')    

  def testRangeQuery(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa) \
        .should_receive("ColumnFamily") \
        .and_return(FakeColumnFamily())

    db = cassandra_interface.DatastoreProxy()

    assert [] == db.range_query("table", [], "start", "end", 0)

if __name__ == "__main__":
  unittest.main()    
