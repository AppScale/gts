#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.ext import db

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import appscale_datastore_batch
import groomer
from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException

class FakeDatastore():
  def __init__(self):
    pass
  def range_query(self, table, schema, start, end, size):
    return []

class FakeEntity():
  def __init__(self):
    pass

class TestGroomer(unittest.TestCase):
  """
  A set of test cases for the datastore groomer thread.
  """
  def test_init(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "hypertable") 

  def test_get_groomer_lock(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_datastore_groomer_lock").and_return(True)
    dsg = groomer.DatastoreGroomer(zookeeper, "hypertable")
    self.assertEquals(True, dsg.get_groomer_lock())

  def test_run_groomer(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra")
    dsg = flexmock(dsg)
    dsg.should_receive("get_entity_batch").and_return([])
    dsg.should_receive("process_entity")
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    self.assertEquals(True, dsg.run_groomer())

  def test_process_entity(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra")
    dsg = flexmock(dsg)
    self.assertEquals(True, dsg.process_entity(FakeEntity()))
 
  def test_process_statics(self):
    pass
  
  def test_txn_blacklist_cleanup(self):
    pass
  
  def test_process_tombstone(self):
    pass

  def test_stop(self):
    pass

  def test_reset_statistics(self):
    pass

 
if __name__ == "__main__":
  unittest.main()    
