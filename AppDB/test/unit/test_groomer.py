#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.ext import db
from google.appengine.datastore import entity_pb

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import dbconstants
import datastore_server
import appscale_datastore_batch
import groomer

from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException

class FakeQuery():
  def __init__():
    pass
  def run():
    return []



class FakeDatastore():
  def __init__(self):
    pass

class FakeDistributedDB():
  def __init__(self):
    pass
  def Query(model_class="kind", namespace=''):
    return FakeQuery()

class FakeReference():
  def __init__(self):
    pass
  def app(self):
    return "app_id"

class FakeEntity():
  def __init__(self):
    pass
  def ParseFromString(self, ent_str):
    pass
  def kind(self):
    return 'kind'
  def key(self):
    return FakeReference()

class TestGroomer(unittest.TestCase):
  """
  A set of test cases for the datastore groomer thread.
  """
  def test_init(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "hypertable", "localhost:8888") 

  def test_get_groomer_lock(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_datastore_groomer_lock").and_return(True)
    dsg = groomer.DatastoreGroomer(zookeeper, "hypertable", "localhost:8888")
    self.assertEquals(True, dsg.get_groomer_lock())

  def test_run_groomer(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.should_receive("get_entity_batch").and_return([])
    dsg.should_receive("process_entity")
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    self.assertEquals(True, dsg.run_groomer())

  def test_process_entity(self):
    zookeeper = flexmock()
    flexmock(entity_pb).should_receive('EntityProto').and_return(FakeEntity())

    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.should_receive('process_statistics')
    self.assertEquals(True, dsg.process_entity({'key':{dbconstants.APP_ENTITY_SCHEMA[0]:'ent',
      dbconstants.APP_ENTITY_SCHEMA[1]:'version'}}))
 
  def test_process_statistics(self):
    zookeeper = flexmock()
    flexmock(entity_pb).should_receive('EntityProto').and_return(FakeEntity())
    flexmock(datastore_server.DatastoreDistributed)\
      .should_receive("get_entity_kind").and_return("kind")
    
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.stats['app_id'] = {'kind': {'size': 0, 'number': 0}}
     
    # This one gets ignored 
    dsg.should_receive("initialize_kind")
    self.assertEquals(True, dsg.process_statistics("key", "ent", "2"))
    self.assertEquals(dsg.stats, {'app_id':{'kind':{'size':3, 'number':1}}})
    self.assertEquals(True, dsg.process_statistics("key", "ent", "2"))
    self.assertEquals(dsg.stats, {'app_id':{'kind':{'size':6, 'number':2}}})
 
  def test_initialize_kind(self):
    zookeeper = flexmock()
    flexmock(entity_pb).should_receive('EntityProto').and_return(FakeEntity())
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.initialize_kind('app_id', 'kind')
    self.assertEquals(dsg.stats, {'app_id': {'kind': {'size': 0, 'number': 0}}}) 
 
  def test_txn_blacklist_cleanup(self):
    pass
  
  def test_process_tombstone(self):
    pass

  def test_stop(self):
    pass

  def test_remove_old_statistics(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.should_receive("get_db_accessor").and_return(FakeDatastore())
    dsg.stats['app_id'] = {'kind': {'size': 0, 'number': 0}}
    dsg.stats['app_id1'] = {'kind': {'size': 0, 'number': 0}}
    dsg.remove_old_statistics()

  def test_update_statistics(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.should_receive("remove_old_statistics")
    dsg.should_receive("create_kind_ds_entry").and_return().and_raise(Exception)
    dsg.stats['app_id'] = {'kind': {'size': 0, 'number': 0}}
    dsg.stats['app_id1'] = {'kind': {'size': 0, 'number': 0}}
    # Should loop twice and on the second raise an exception.
    self.assertRaises(Exception, dsg.update_statistics)

  def test_reset_statistics(self):
    zookeeper = flexmock()
    flexmock(entity_pb).should_receive('EntityProto').and_return(FakeEntity())
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg.reset_statistics()
    self.assertEquals(dsg.stats, {})

  def get_db_accessor(self):
    zookeeper = flexmock()
    fake_ds = FakeDatastore()
    flexmock(datatore_distributed).should_receive('DatastoreDistributed').\
      and_return(fake_ds)
    flexmock(apiproxy_stub_map.apiproxy).should_receive('RegisterStub')
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    self.assertEquals(fake_ds, dsg.get_db_accessor("app_id"))

if __name__ == "__main__":
  unittest.main()    
