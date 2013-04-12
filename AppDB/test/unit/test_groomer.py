#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_distributed
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
  def __init__(self):
    pass
  def run(self):
    return [FakeEntity()]

class FakeDatastore():
  def __init__(self):
    pass

class FakeDistributedDB():
  def __init__(self):
    pass
  def Query(self, model_class="kind", namespace=''):
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
  def delete(self):
    raise Exception()
  def put(self):
    raise Exception()

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
    dsg.should_receive("update_statistics").and_raise(Exception)
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    self.assertRaises(Exception, dsg.run_groomer)

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
    dsg.should_receive("register_db_accessor").and_return(FakeDistributedDB())
    dsg.stats['app_id'] = {'kind': {'size': 0, 'number': 0}}
    dsg.stats['app_id1'] = {'kind': {'size': 0, 'number': 0}}
    self.assertRaises(Exception, dsg.remove_old_statistics)

  def test_update_statistics(self):
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg = flexmock(dsg)
    dsg.should_receive("register_db_accessor").and_return(FakeDistributedDB())
    dsg.should_receive("create_global_stat_entry").and_return(True)
    dsg.should_receive("create_kind_stat_entry").and_return(True)
    dsg.stats['app_id'] = {'kind': {'size': 0, 'number': 0}}
    dsg.stats['app_id1'] = {'kind': {'size': 0, 'number': 0}}
    # Should loop twice and on the second raise an exception.
    self.assertEquals(True, dsg.update_statistics())
    dsg.should_receive("create_kind_stat_entry").and_return(False)
    self.assertEquals(False, dsg.update_statistics())

  def test_reset_statistics(self):
    zookeeper = flexmock()
    flexmock(entity_pb).should_receive('EntityProto').and_return(FakeEntity())
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    dsg.reset_statistics()
    self.assertEquals(dsg.stats, {})

  def test_register_db_accessor(self):
    zookeeper = flexmock()
    fake_ds = FakeDatastore()
    flexmock(datastore_distributed).should_receive('DatastoreDistributed').\
      and_return(fake_ds)
    flexmock(apiproxy_stub_map.apiproxy).should_receive('RegisterStub')
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    self.assertEquals(fake_ds, dsg.register_db_accessor("app_id"))

  def test_create_kind_stat_entry(self):
    zookeeper = flexmock()
    stats = flexmock(db.stats)    
    stats.should_receive("GlobalStat").and_return(FakeEntity())
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    self.assertRaises(Exception, dsg.create_kind_stat_entry, "kind", 0, 0, 0)
     
  def test_create_global_stat_entry(self):
    zookeeper = flexmock()
    stats = flexmock(db.stats)
    stats.should_receive("KindStat").and_return(FakeEntity())
    dsg = groomer.DatastoreGroomer(zookeeper, "cassandra", "localhost:8888")
    self.assertRaises(Exception, dsg.create_kind_stat_entry, 0, 0, 0)
     
if __name__ == "__main__":
  unittest.main()    
