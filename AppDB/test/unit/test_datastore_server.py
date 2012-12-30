#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.ext import db
from google.appengine.datastore import entity_pb
from google.appengine.datastore import datastore_pb
from google.appengine.api import api_base_pb

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from appscale_datastore_batch import DatastoreFactory
from datastore_server import DatastoreDistributed
from datastore_server import BLOCK_SIZE
from dbconstants import *

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException

class Item(db.Model):
  name = db.StringProperty(required = True)

class TestDatastoreServer(unittest.TestCase):
  """
  A set of test cases for the datastore server (datastore server v2)
  """
  def get_zookeeper(self):
    zookeeper = flexmock()
    zookeeper.should_receive("acquireLock").and_return(True)
    zookeeper.should_receive("releaseLock").and_return(True)
    return zookeeper

  def test_get_entity_kind(self):
    dd = DatastoreDistributed(None, None)
    item = Item(name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_entity_kind(key), "Item")

  def test_kind_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(name="Dyan", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()), "howdy/Item:0000000000!")

    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item1)
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()), "howdy/Item:Bob!")
   
    item2 = Item(key_name="Frank", name="Frank", _app="hello", parent = item1)
    key = db.model_to_protobuf(item2)
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()),
           "howdy/Item:Frank!Item:Bob!")

  def test_get_entity_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_entity_key("howdy", key.key().path()), "howdy/Item:Bob!")

  def test_validate_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    dd.validate_key(key.key()) 

  def test_get_index_key(self):
    dd = DatastoreDistributed(None, None)
    dd.get_index_key("a","b","c","d")  == "a/b/c/d"

  def test_configure_namespace(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    zookeeper = flexmock()
    zookeeper.should_receive("acquireLock").and_return(True)
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    self.assertEquals(dd.configure_namespace("howdy", "hello", "ns"), True)

  def test_get_table_prefix(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    zookeeper = flexmock()
    zookeeper.should_receive("acquireLock").and_return(True)
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_table_prefix(key), "hello/")

  def test_get_index_key_from_params(self):
    dd = DatastoreDistributed(None, None)
    params = ['a','b','c','d','e']
    self.assertEquals(dd.get_index_key_from_params(params), "a/b/c/d/e")

  def test_get_index_kv_from_tuple(self):
    dd = DatastoreDistributed(None, None)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    tuples_list = [("a/b",key1),("a/b",key2)]
    self.assertEquals(dd.get_index_kv_from_tuple(tuples_list), (['a/b/Item/name/Bob\x00/Item:Bob!', 'a/b/Item:Bob!'], ['a/b/Item/name/Sally\x00/Item:Sally!', 'a/b/Item:Sally!']))

  def test_delete_index_entries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.delete_index_entries([key1,key2])
 
  def test_insert_entities(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_entities([key1,key2])

  def test_insert_index_entries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_index_entries([key1,key2])

  def test_acquire_next_id_from_db(self):
    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.acquire_next_id_from_db(PREFIX), 1)

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.acquire_next_id_from_db(PREFIX), 1)

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"2"}})
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.acquire_next_id_from_db(PREFIX), 2)

  def test_allocate_ids(self):
    PREFIX = "x"
    BATCH_SIZE = 1000
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.allocate_ids(PREFIX, BATCH_SIZE), (1, 1000))

    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.allocate_ids(PREFIX, None, max_id=10), (1, 10))

    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    try:
      # Unable to use self.assertRaises because of the optional argrument max_id
      dd = DatastoreDistributed(db_batch, self.get_zookeeper())
      dd.allocate_ids(PREFIX, BATCH_SIZE, max_id=10)
      raise "Allocate IDs should not let you set max_id and size"
    except ValueError:
      pass 

  def test_put_entities(self):
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{},"key2":{}})
    zookeeper = flexmock()
    zookeeper.should_receive("acquireLock").and_return(True)
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    dd.put_entities([key1, key2]) 

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{"entity":key1.Encode()},"key2":{"entity":key2.Encode()}})
    dd = DatastoreDistributed(db_batch, zookeeper)
    dd.put_entities([key1, key2]) 

  def testFetchKeys(self):
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(['aaa'])
    zookeeper = flexmock()
    zookeeper.should_receive("acquireLock").and_return(True)
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    self.assertEquals(dd.fetch_keys([key1.key(), key2.key()]), (['aaa'], ['hello//Item:Bob!', 'hello//Item:Sally!']))

  def test_commit_transaction(self):
    db_batch = flexmock()
    zookeeper = flexmock()
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    commit_request = datastore_pb.Transaction()
    commit_request.set_handle(123)
    commit_request.set_app("aaa")
    http_request = commit_request.Encode()
    self.assertEquals(dd.commit_transaction("app_id", http_request),
                      (datastore_pb.CommitResponse().Encode(), 0, ""))

  def test_rollback_transcation(self):
    db_batch = flexmock()
    zookeeper = flexmock()
    zookeeper.should_receive("releaseLock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    commit_request = datastore_pb.Transaction()
    commit_request.set_handle(123)
    commit_request.set_app("aaa")
    http_request = commit_request.Encode()
    self.assertEquals(dd.rollback_transaction("app_id", http_request),
                      (api_base_pb.VoidProto().Encode(), 0, ""))
   
 
if __name__ == "__main__":
  unittest.main()    
