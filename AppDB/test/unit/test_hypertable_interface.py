#!/usr/bin/env python
# Programmer: Navraj Chohan

import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../hypertable/"))  
from hypertable import thriftclient
import hypertable_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import helper_functions

class FakeHypertableClient():
  """ Fake hypertable client class for mocking """
  def __init__(self):
    return
  def namespace_open(self, NS):
    return "NS"
  def get_cells(self, ns, table_name, scane_spec):
    return []
  def drop_table(self, ns, table_name, x):
    return None
  def mutator_open(self, ns, table_name, x, y):
    return None
  def mutator_set_cells(self, mutator, cell_list):
    return None
  def mutator_close(self, mutator):
    return None
 
class TestHypertable(unittest.TestCase):
  def testConstructor(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()

  def testGet(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert {} == db.batch_get_entity('table', [], [])

  def testPut(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.batch_put_entity('table', [], [], {})

  def testDeleteTable(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.delete_table('table')

  def testDelete(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()
    
    # Make sure no exception is thrown
    assert None == db.batch_delete('table', [])

  def testRangeQuery(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(thriftclient).should_receive("ThriftClient") \
        .and_return(FakeHypertableClient())

    db = hypertable_interface.DatastoreProxy()
    assert [] == db.range_query("table", [], "start", "end", 0)

if __name__ == "__main__":
  unittest.main()    
