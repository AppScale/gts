#!/usr/bin/env python
# Programmer: Navraj Chohan

import unittest
from flexmock import flexmock

from appscale_datastore_batch import DatastoreFactory
from datastore_server import DatastoreDistributed
from datastore_server import _BLOCK_SIZE
from dbconstants import *

from google.appengine.ext import db
from google.appengine.datastore import entity_pb


class Item(db.Model):
  name = db.StringProperty(required = True)

class TestDatastoreServer(unittest.TestCase):
  """
  A set of test cases for the datastore server (pbserver v2)
  """
  def testGetEntityKind(self):
    dd = DatastoreDistributed(None)
    item = Item(name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.GetEntityKind(key) =="Item"

  def testKindKey(self):
    dd = DatastoreDistributed(None)
    item = Item(name="Dyan", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.GetKindKey("howdy", key.key().path()) == "howdy/Item:0000000000!"

    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item1)
    assert dd.GetKindKey("howdy", key.key().path()) == "howdy/Item:Bob!"
   
    item2 = Item(key_name="Frank", name="Frank", _app="hello", parent = item1)
    key = db.model_to_protobuf(item2)
    assert dd.GetKindKey("howdy", key.key().path()) == \
           "howdy/Item:Frank!Item:Bob!"

  def testEntityKey(self):
    dd = DatastoreDistributed(None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.GetEntityKey("howdy", key.key().path()) == "howdy/Item:Bob!"

  def testValidateKey(self):
    dd = DatastoreDistributed(None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    dd.ValidateKey(key.key()) 

  def testGetIndexKey(self):
    dd = DatastoreDistributed(None)
    dd.GetIndexKey("a","b","c","d")  == "a/b/c/d"

  def testConfigureNameSpsace(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.ConfigureNamespace("howdy", "hello", "ns")  == True

  def testConfigureNameSpsace(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    assert dd.GetTablePrefix(key) == "hello/"

  def testGetIndexKeyFromParams(self):
    dd = DatastoreDistributed(None)
    params = ['a','b','c','d','e']
    assert dd.GetIndexKeyFromParams(params) == "a/b/c/d/e"

  def testGetIndexKVFromTuple(self):
    dd = DatastoreDistributed(None)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    tuples_list = [("a/b",key1),("a/b",key2)]
    assert dd.GetIndexKVFromTuple(tuples_list) == (['a/b/Item/name/Bob\x00/Item:Bob!', 'a/b/Item:Bob!'], ['a/b/Item/name/Sally\x00/Item:Sally!', 'a/b/Item:Sally!'])

  def testDeleteIndexEntries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.DeleteIndexEntries([key1,key2])
 
  def testInsertEntities(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.InsertEntities([key1,key2])

  def testInsertIndexEntries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.InsertIndexEntries([key1,key2])

  def testAcquireIdBlockFromDB(self):
    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    dd = DatastoreDistributed(db_batch)
    assert dd.AcquireIdBlockFromDB(PREFIX) == 1

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    dd = DatastoreDistributed(db_batch)
    assert dd.AcquireIdBlockFromDB(PREFIX) == 0

  def testIncrementIdInDB(self):
    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"0"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.IncrementIdInDB(PREFIX) == _BLOCK_SIZE

    PREFIX = "x"
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.IncrementIdInDB(PREFIX) == 2 * _BLOCK_SIZE

  def testAllocateIds(self):
    PREFIX = "x"
    BATCH_SIZE = 1000
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{APP_ID_SCHEMA[0]:"1"}})
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch)
    assert dd.AllocateIds(PREFIX, BATCH_SIZE) == (20000, 20999) 

  def testPutEntities(self):
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{},"key2":{}})
    dd = DatastoreDistributed(db_batch)
    dd.PutEntities([key1, key2]) 

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({"key1":{"entity":key1.Encode()},"key2":{"entity":key2.Encode()}})
    dd = DatastoreDistributed(db_batch)
    dd.PutEntities([key1, key2]) 

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
    assert dd.FetchKeys([key1.key(), key2.key()]) == (['aaa'], ['hello//Item:Bob!', 'hello//Item:Sally!']) 

if __name__ == "__main__":
  unittest.main()    
