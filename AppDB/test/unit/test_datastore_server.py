#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

from google.appengine.ext import db
from google.appengine.datastore import entity_pb

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from appscale_datastore_batch import DatastoreFactory
from datastore_server import DatastoreDistributed
from datastore_server import BLOCK_SIZE
from dbconstants import *

class Item(db.Model):
  name = db.StringProperty(required = True)

class TestDatastoreServer(unittest.TestCase):
  """
  A set of test cases for the datastore server (datastore server v2)
  """
  def test_get_entity_kind(self):
    dd = DatastoreDistributed(None)
    item = Item(name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.get_entity_kind(key) =="Item"

  def test_kind_key(self):
    dd = DatastoreDistributed(None)
    item = Item(name="Dyan", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.get_kind_key("howdy", key.key().path()) == "howdy/Item:0000000000!"

    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item1)
    assert dd.get_kind_key("howdy", key.key().path()) == "howdy/Item:Bob!"
   
    item2 = Item(key_name="Frank", name="Frank", _app="hello", parent = item1)
    key = db.model_to_protobuf(item2)
    assert dd.get_kind_key("howdy", key.key().path()) == \
           "howdy/Item:Frank!Item:Bob!"

  def test_get_entity_key(self):
    dd = DatastoreDistributed(None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.get_entity_key("howdy", key.key().path()) == "howdy/Item:Bob!"

  def test_validate_key(self):
    dd = DatastoreDistributed(None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    dd.validate_key(key.key()) 

  def test_get_index_key(self):
    dd = DatastoreDistributed(None)
    dd.get_index_key("a","b","c","d")  == "a/b/c/d"

  def test_configure_namespace(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.configure_namespace("howdy", "hello", "ns")  == True

  def test_configure_namespace(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.get_table_prefix(key) == "hello/"

  def test_get_index_key_from_params(self):
    dd = DatastoreDistributed(None)
    params = ['a','b','c','d','e']
    assert dd.get_index_key_from_params(params) == "a/b/c/d/e"

  def test_get_index_kv_from_tuple(self):
    dd = DatastoreDistributed(None)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    tuples_list = [("a/b",key1),("a/b",key2)]
    assert dd.get_index_kv_from_tuple(tuples_list) == (['a/b/Item/name/Bob\x00/Item:Bob!', 'a/b/Item:Bob!'], ['a/b/Item/name/Sally\x00/Item:Sally!', 'a/b/Item:Sally!'])

  def test_delete_index_entries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.delete_index_entries([key1,key2])
 
  def test_insert_entities(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_entities([key1,key2])

  def test_insert_index_entries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_index_entries([key1,key2])

  def test_acquire_id_block_from_db(self):
    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    dd = DatastoreDistributed(db_batch)
    assert dd.acquire_id_block_from_db(PREFIX) == 1

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    dd = DatastoreDistributed(db_batch)
    assert dd.acquire_id_block_from_db(PREFIX) == 0

  def test_increment_id_in_db(self):
    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"0"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.increment_id_in_db(PREFIX) == BLOCK_SIZE

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.increment_id_in_db(PREFIX) == 2 * BLOCK_SIZE

  def test_allocate_ids(self):
    PREFIX = "x"
    BATCH_SIZE = 1000
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.allocate_ids(PREFIX, BATCH_SIZE) == (20000, 20999) 

  def test_put_entities(self):
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{},"key2":{}})
    dd = DatastoreDistributed(db_batch)
    dd.put_entities([key1, key2]) 

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{"entity":key1.Encode()},"key2":{"entity":key2.Encode()}})
    dd = DatastoreDistributed(db_batch)
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
    dd = DatastoreDistributed(db_batch)
    assert dd.fetch_keys([key1.key(), key2.key()]) == (['aaa'], ['hello//Item:Bob!', 'hello//Item:Sally!']) 

if __name__ == "__main__":
  unittest.main()    
