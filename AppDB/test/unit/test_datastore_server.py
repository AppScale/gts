#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.datastore import entity_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.api import api_base_pb
from google.appengine.api import datastore
from google.appengine.ext import db

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from appscale_datastore_batch import DatastoreFactory
from datastore_server import DatastoreDistributed
from datastore_server import BLOCK_SIZE
from datastore_server import TOMBSTONE
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
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("get_transaction_id").and_return(1)
    zookeeper.should_receive("increment_and_get_counter").and_return(0,1000)
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
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()), "howdy\x00Item!Item:0000000000!")

    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item1)
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()), "howdy\x00Item!Item:Bob!")
   
    item2 = Item(key_name="Frank", name="Frank", _app="hello", parent = item1)
    key = db.model_to_protobuf(item2)
    self.assertEquals(dd.get_kind_key("howdy", key.key().path()),
           "howdy\x00Item!Item:Bob!Item:Frank!")

  def test_get_entity_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(str(dd.get_entity_key("howdy", key.key().path())), "howdy\x00Item:Bob!")

  def test_validate_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    dd.validate_key(key.key()) 

  def test_get_index_key(self):
    dd = DatastoreDistributed(None, None)
    dd.get_index_key("a","b","c","d")  == "a\x00b\x00c\x00d"

  def test_get_table_prefix(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_table_prefix(key), "hello\x00")

  def test_get_index_key_from_params(self):
    dd = DatastoreDistributed(None, None)
    params = ['a','b','c','d','e']
    self.assertEquals(dd.get_index_key_from_params(params), "a\x00b\x00c\x00d\x00e")

  def test_get_index_kv_from_tuple(self):
    dd = DatastoreDistributed(None, None)
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    tuples_list = [("a\x00b",key1),("a\x00b",key2)]
    self.assertEquals(dd.get_index_kv_from_tuple(
      tuples_list), (['a\x00b\x00Item\x00name\x00\x9aBob\x00\x00Item:Bob!', 'a\x00b\x00Item:Bob!'], 
      ['a\x00b\x00Item\x00name\x00\x9aSally\x00\x00Item:Sally!', 'a\x00b\x00Item:Sally!']))

  def test_delete_composite_indexes(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd = flexmock(dd)
    dd.should_receive("get_composite_index_key").and_return("somekey")
    dd.should_receive("get_entity_kind").and_return("kind")
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id("appid")

    definition = composite_index.mutable_definition()
    definition.set_entity_type("kind")

    dd.delete_composite_indexes([item1, item2], [composite_index])

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

  def test_get_composite_index_key(self):
    db_batch = flexmock()
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd = flexmock(dd)

    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id("appid")

    definition = composite_index.mutable_definition()
    definition.set_entity_type("kind")

    prop1 = definition.add_property()
    prop1.set_name("prop1")
    prop1.set_direction(1) # ascending
    prop2 = definition.add_property()
    prop2.set_name("prop2")
    prop1.set_direction(1) # ascending

    ent = self.get_new_entity_proto("appid", "kind", "entity_name", "prop1", "value", ns="")
     
    self.assertEquals(dd.get_composite_index_key(composite_index, ent), 
      "appid\x00\x00123\x00\x9avalue\x00\x00kind:entity_name!")

  def test_get_indicies(self):
    db_batch = flexmock()
    db_batch.should_receive("range_query").and_return({})
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd = flexmock(dd)
    dd.should_receive("get_meta_data_key").and_return("somekey").twice()
    
    self.assertEquals(dd.get_indices("appid"), [])

  def test_delete_composite_index_metadata(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd = flexmock(dd)
    dd.should_receive("get_meta_data_key").and_return("somekey")
    composite_indexes = datastore_pb.CompositeIndices() 
    dd.delete_composite_index_metadata("appid", composite_indexes)

  def test_create_composite_index(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd = flexmock(dd)
    dd.should_receive("get_meta_data_key").and_return("somekey")
    index = entity_pb.CompositeIndex()
    index.set_app_id("appid")
    index.set_state(2)
    definition = index.mutable_definition()
    definition.set_entity_type("kind")
    definition.set_ancestor(0)
    prop1 = definition.add_property()
    prop1.set_name("prop1")
    prop1.set_direction(1) # ascending
    prop2 = definition.add_property()
    prop2.set_name("prop2")
    prop1.set_direction(1) # ascending

    dd.create_composite_index("appid", index)
    assert index.id() > 0 

  def test_insert_composite_indexes(self):
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id("appid")

    definition = composite_index.mutable_definition()
    definition.set_entity_type("kind")

    prop1 = definition.add_property()
    prop1.set_name("prop1")
    prop1.set_direction(1) # ascending
    prop2 = definition.add_property()
    prop2.set_name("prop2")
    prop1.set_direction(1) # ascending

    ent = self.get_new_entity_proto("appid", "kind", "entity_name", "prop1", "value", ns="")

    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None).once()
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    dd.insert_composite_indexes([ent], [composite_index])

  def test_insert_entities(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_entities([key1,key2], {"hello\x00\x00Item:Sally!": 1, "hello\x00\x00Item:Bob!":1})

  def test_insert_index_entries(self):
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    dd.insert_index_entries([key1,key2])

  def test_allocate_ids(self):
    PREFIX = "x"
    BATCH_SIZE = 1000
    db_batch = flexmock()
    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.allocate_ids(PREFIX, BATCH_SIZE), (1, 1000))

    dd = DatastoreDistributed(db_batch, self.get_zookeeper())
    self.assertEquals(dd.allocate_ids(PREFIX, None, max_id=1000), (1, 1000))

    try:
      # Unable to use self.assertRaises because of the optional argrument max_id
      ed = DatastoreDistributed(db_batch, self.get_zookeeper())
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
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    dd.put_entities("hello", [key1, key2], {}) 

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(
      {"key1":{"entity":key1.Encode()},"key2":{"entity":key2.Encode()}})
    dd = DatastoreDistributed(db_batch, zookeeper)
    dd.put_entities("hello", [key1, key2], {}) 

  def testFetchKeys(self):
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")

    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({'test\x00blah\x00test_kind:bob!':
                {APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(), 
                 APP_ENTITY_SCHEMA[1]: 1}}).and_return({'test\x00blah\x00test_kind:bob!\x000000000002':
                {JOURNAL_SCHEMA[0]: entity_proto1.Encode()}})

    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("get_valid_transaction_id").and_return(2)
    dd = DatastoreDistributed(db_batch, zookeeper)

    self.assertEquals(({'test\x00blah\x00test_kind:bob!': 
                         {'txnID': "2", 'entity': entity_proto1.Encode()}
                       }, 
                       ['test\x00blah\x00test_kind:bob!']), 
                       dd.fetch_keys([entity_proto1.key()]))

  def test_commit_transaction(self):
    db_batch = flexmock()
    zookeeper = flexmock()
    zookeeper.should_receive("release_lock").and_return(True)
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
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("notify_failed_transaction").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    commit_request = datastore_pb.Transaction()
    commit_request.set_handle(123)
    commit_request.set_app("aaa")
    http_request = commit_request.Encode()
    self.assertEquals(dd.rollback_transaction("app_id", http_request),
                      (api_base_pb.VoidProto().Encode(), 0, ""))

  def get_new_entity_proto(self, app_id, kind, entity_name, prop_name, prop_value, ns=""):
    entity_proto = datastore_pb.EntityProto()

    reference = entity_proto.mutable_key()
    reference.set_app(app_id)
    reference.set_name_space(ns)

    path = reference.mutable_path()
    element = path.add_element() 
    element.set_type(kind)
    element.set_name(entity_name)

    ent_group = entity_proto.mutable_entity_group()
    eg_element = ent_group.add_element() 
    eg_element.set_type(kind)
    eg_element.set_name(entity_name)

    prop = entity_proto.add_property()
    prop.set_meaning(datastore_pb.Property.BYTESTRING)
    prop.set_name(prop_name)
    prop.set_multiple(1)
    val = prop.mutable_value()
    val.set_stringvalue(prop_value)
    return entity_proto

  def test_dynamic_put(self):
    PREFIX = "x!"
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    db_batch.should_receive("batch_delete").and_return(None)

    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("get_transaction_id").and_return(1)

    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")

    dd = DatastoreDistributed(db_batch, zookeeper)
    putreq_pb = datastore_pb.PutRequest()
    putreq_pb.add_entity()
    putreq_pb.mutable_entity(0).MergeFrom(entity_proto1)
    putreq_pb.add_entity()
    putreq_pb.mutable_entity(1).MergeFrom(entity_proto2)
    
    putresp_pb = datastore_pb.PutResponse()
    dd.dynamic_put('test', putreq_pb, putresp_pb)
    self.assertEquals(len(putresp_pb.key_list()), 2)

  def test_put_entities(self):
    PREFIX = "x!"
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    db_batch.should_receive("batch_delete").and_return(None)

    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").and_return(True)

    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")
    entity_list = [entity_proto1, entity_proto2]
    dd = DatastoreDistributed(db_batch, zookeeper)

    # Make sure it does not throw an exception
    dd.put_entities("hello", entity_list, {"test\x00blah\x00test_kind:bob!":1, 
      "test\x00blah\x00test_kind:nancy!":1}) 

  def test_acquire_locks_for_trans(self):
    dd = DatastoreDistributed(None, None) 
    flexmock(dd).should_receive("is_instance_wrapper").and_return(False).once()
    self.assertRaises(TypeError, dd.acquire_locks_for_trans, [1], 1)

    dd = DatastoreDistributed(None, None) 
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(False).and_return(False)
    self.assertRaises(TypeError, dd.acquire_locks_for_trans, [1], 1)

    dd = DatastoreDistributed(None, None) 
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True)

    dd = DatastoreDistributed(None, None) 
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(False)
    flexmock(dd).should_receive("get_table_prefix").and_return("prefix").never()
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").never()
    self.assertEquals({}, dd.acquire_locks_for_trans([], 1))

    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").once()
    dd = DatastoreDistributed(None, zookeeper) 
    entity = flexmock()
    entity.should_receive("app").and_return("appid")
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(True)
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").once()
    self.assertEquals({'rootkey':1}, dd.acquire_locks_for_trans([entity], 1))

    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").once().and_raise(ZKTransactionException)
    zookeeper.should_receive("notify_failed_transaction").once()
    dd = DatastoreDistributed(None, zookeeper) 
    entity = flexmock()
    entity.should_receive("app").and_return("appid")
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(True)
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").once()
    self.assertRaises(ZKTransactionException, dd.acquire_locks_for_trans, [entity], 1)
         
  def test_acquire_locks_for_nontrans(self):
    PREFIX = 'x!'
    zookeeper = flexmock()
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("get_transaction_id").and_return(1).and_return(2)
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    db_batch.should_receive("batch_delete").and_return(None)
    dd = DatastoreDistributed(db_batch, zookeeper) 
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")
    entity_list = [entity_proto1, entity_proto2]
    self.assertEquals({'test\x00blah\x00test_kind:bob!': 2, 'test\x00blah\x00test_kind:nancy!': 1}, 
                      dd.acquire_locks_for_nontrans("test", entity_list))

  def test_register_old_entities(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(True)
    db_batch = flexmock()
    dd = DatastoreDistributed(db_batch, zookeeper) 
    dd.register_old_entities({'x!x!':{APP_ENTITY_SCHEMA[0]: 'entity_string',
                                     APP_ENTITY_SCHEMA[1]: '1'}}, 
                             {'x!': 1}, 'test')

  def test_update_journal(self):
    PREFIX = 'x!'
    zookeeper = flexmock()
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return({PREFIX:{}})
    db_batch.should_receive("batch_delete").and_return(None)

    dd = DatastoreDistributed(db_batch, zookeeper) 
    row_keys = ['a!a!']
    row_values = {'a!a!':{APP_ENTITY_SCHEMA[0]: 'entity_string',
                         APP_ENTITY_SCHEMA[1]: '1'}}
    txn_hash = {'a!': 1}
    dd.update_journal(row_keys, row_values, txn_hash)

  def test_delete_entities(self):
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    row_key = "test\x00blah\x00test_kind:bob!"
    row_values = {row_key:{APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                         APP_ENTITY_SCHEMA[1]: '1'}}

    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(row_values)
    db_batch.should_receive("batch_delete").and_return(None)

    dd = DatastoreDistributed(db_batch, zookeeper) 

    row_keys = [entity_proto1.key()]
    txn_hash = {row_key: 2}
    dd.delete_entities('test', row_keys, txn_hash, soft_delete=True) 
     
  def test_release_put_locks_for_nontrans(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(None)
    db_batch.should_receive("batch_delete").and_return(None)

    dd = DatastoreDistributed(db_batch, zookeeper) 
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "bob", "prop1name", 
                                              "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")
    entities = [entity_proto1, entity_proto2]
    dd.release_locks_for_nontrans("test", entities, 
                  {'test\x00blah\x00test_kind:bob!': 1, 'test\x00blah\x00test_kind:nancy!': 2})
 
  def test_root_key_from_entity_key(self):
    zookeeper = flexmock()
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)

    dd = DatastoreDistributed(db_batch, zookeeper) 
    self.assertEquals("test\x00blah\x00test_kind:bob!", 
                      dd.get_root_key_from_entity_key("test\x00blah\x00test_kind:bob!nancy!"))
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")
    self.assertEquals("test\x00blah\x00test_kind:nancy!", 
      dd.get_root_key_from_entity_key(entity_proto1.key()))

  def test_remove_tombstoned_entities(self):
    zookeeper = flexmock()
    db_batch = flexmock()
    dd = DatastoreDistributed(db_batch, zookeeper) 
    self.assertEquals({}, dd.remove_tombstoned_entities({'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE}}))
    self.assertEquals({"key2": {APP_ENTITY_SCHEMA[0]:"blah"}}, 
                      dd.remove_tombstoned_entities({'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE}, 
                                                     'key2': {APP_ENTITY_SCHEMA[0]:"blah"}}))

  def test_dynamic_get(self):
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop2val", ns="blah")
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(
               {"test\x00blah\x00test_kind:nancy!": 
                 {
                   APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                   APP_ENTITY_SCHEMA[1]: 1
                 }
               })

    dd = DatastoreDistributed(db_batch, zookeeper) 

    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key() 
    key.MergeFrom(entity_key)
    get_resp = datastore_pb.GetResponse()
    
    dd.dynamic_get("test", get_req, get_resp)     
    self.assertEquals(get_resp.entity_size(), 1)

    # Now test while in a transaction
    get_resp = datastore_pb.GetResponse()
    get_req.mutable_transaction().set_handle(1)
    dd.dynamic_get("test", get_req, get_resp)     
    self.assertEquals(get_resp.entity_size(), 1)

  def test_ancestor_query(self):
    query = datastore_pb.Query()
    ancestor = query.mutable_ancestor()
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop1val", ns="blah")
    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key() 
    key.MergeFrom(entity_key)
    ancestor.MergeFrom(entity_key)
    
    filter_info = []
    tombstone1 = {'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE, APP_ENTITY_SCHEMA[1]: 1}}
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return(
               {"test\x00blah\x00test_kind:nancy!": 
                 {
                   APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                   APP_ENTITY_SCHEMA[1]: 1
                 }
               })

    db_batch.should_receive("batch_put_entity").and_return(None)
    entity_proto1 = {'test\x00blah\x00test_kind:nancy!':{APP_ENTITY_SCHEMA[0]:entity_proto1.Encode(),
                      APP_ENTITY_SCHEMA[1]: 1}}
    db_batch.should_receive("range_query").and_return([entity_proto1, tombstone1]).and_return([])
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper) 
    dd.ancestor_query(query, filter_info, None)
    # Now with a transaction
    transaction = query.mutable_transaction() 
    transaction.set_handle(2)
    dd.ancestor_query(query, filter_info, None)

  def test_ordered_ancestor_query(self):
    query = datastore_pb.Query()
    ancestor = query.mutable_ancestor()
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name",
                                              "prop1val", ns="blah")
    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key()
    key.MergeFrom(entity_key)
    ancestor.MergeFrom(entity_key)

    filter_info = []
    tombstone1 = {'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE, APP_ENTITY_SCHEMA[1]: 1}}
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return(
               {"test\x00blah\x00test_kind:nancy!":
                 {
                   APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                   APP_ENTITY_SCHEMA[1]: 1
                 }
               })

    db_batch.should_receive("batch_put_entity").and_return(None)
    entity_proto1 = {'test\x00blah\x00test_kind:nancy!':{APP_ENTITY_SCHEMA[0]:entity_proto1.Encode(),
                      APP_ENTITY_SCHEMA[1]: 1}}
    db_batch.should_receive("range_query").and_return([entity_proto1, tombstone1]).and_return([])
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper)
    dd.ordered_ancestor_query(query, filter_info, None)

    # Now with a transaction
    transaction = query.mutable_transaction()
    transaction.set_handle(2)
    dd.ordered_ancestor_query(query, filter_info, None) 

  
  def test_kindless_query(self):
    query = datastore_pb.Query()
    ancestor = query.mutable_ancestor()
    entity_proto1 = self.get_new_entity_proto("test", "test_kind", "nancy", "prop1name", 
                                              "prop1val", ns="blah")
    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key() 
    key.MergeFrom(entity_key)
    
    tombstone1 = {'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE, APP_ENTITY_SCHEMA[1]: 1}}
    db_batch = flexmock()
    db_batch.should_receive("batch_get_entity").and_return(
               {"test\x00blah\x00test_kind:nancy!": 
                 {
                   APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                   APP_ENTITY_SCHEMA[1]: 1
                 }
               })

    db_batch.should_receive("batch_put_entity").and_return(None)
    entity_proto1 = {'test\x00blah\x00test_kind:nancy!':{APP_ENTITY_SCHEMA[0]:entity_proto1.Encode(),
                      APP_ENTITY_SCHEMA[1]: 1}}
    db_batch.should_receive("range_query").and_return([entity_proto1, tombstone1]).and_return([])
    zookeeper = flexmock()
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    dd = DatastoreDistributed(db_batch, zookeeper) 
    filter_info = {
      '__key__' : [[0, 0]]
    }
    dd.kindless_query(query, filter_info, None)

  def test_dynamic_delete(self):
    del_request = flexmock()
    del_request.should_receive("key_list")
    del_request.should_receive("has_transaction").never()
    del_request.should_receive("transaction").never()
    dd = DatastoreDistributed(None, None)
    dd.dynamic_delete("appid", del_request)

    fake_element = flexmock()
    fake_element.should_receive("type").and_return("kind")
    fake_path = flexmock()
    fake_path.should_receive("element_list").and_return([fake_element])
    fake_key = flexmock()
    fake_key.should_receive("path").and_return(fake_path)

    del_request = flexmock()
    del_request.should_receive("key_list").and_return([fake_key])
    del_request.should_receive("has_transaction").and_return(True).twice()
    transaction = flexmock()
    transaction.should_receive("handle").and_return(1)
    del_request.should_receive("transaction").and_return(transaction).once()
    del_request.should_receive("has_mark_changes").and_return(False)
    dd = DatastoreDistributed(None, None)
    flexmock(dd).should_receive("acquire_locks_for_trans").and_return({})
    flexmock(dd).should_receive("release_locks_for_nontrans").never()
    flexmock(dd).should_receive("delete_entities").once()
    flexmock(dd).should_receive("get_entity_kind").and_return("kind")
    dd.dynamic_delete("appid", del_request)

    del_request = flexmock()
    del_request.should_receive("key_list").and_return([fake_key])
    del_request.should_receive("has_transaction").and_return(False).twice()
    del_request.should_receive("has_mark_changes").and_return(False)
    dd = DatastoreDistributed(None, None)
    flexmock(dd).should_receive("acquire_locks_for_trans").never()
    flexmock(dd).should_receive("acquire_locks_for_nontrans").once().and_return({})
    flexmock(dd).should_receive("delete_entities").once()
    flexmock(dd).should_receive("release_locks_for_nontrans").once()
    dd.dynamic_delete("appid", del_request)

  def test_reverse_path(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_transaction_id").and_return(1)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(None)

    dd = DatastoreDistributed(db_batch, zookeeper) 
    key = "Project:Synapse!Module:Core!"
    self.assertEquals(dd.reverse_path(key), "Module:Core!Project:Synapse!")

  def test_remove_exists_filters(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_transaction_id").and_return(1)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(None)

    query = datastore_pb.Query()
    dd = DatastoreDistributed(db_batch, zookeeper)     
    self.assertEquals(dd.remove_exists_filters({}), {})

    filter_info = {"prop1":[(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]}
    self.assertEquals(dd.remove_exists_filters(filter_info), filter_info)

    filter_info = {"prop1":[(datastore_pb.Query_Filter.EXISTS, "1")],
      "prop2": [(datastore_pb.Query_Filter.EXISTS, "2")]}
    self.assertEquals(dd.remove_exists_filters(filter_info), {})

  def test_is_zigzag_merge_join(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_transaction_id").and_return(1)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(None)

    query = datastore_pb.Query()
    dd = DatastoreDistributed(db_batch, zookeeper) 
    db_batch.should_receive("remove_exists_filters").and_return({})
    self.assertEquals(dd.is_zigzag_merge_join(query, {}, {}), False)
    filter_info = {"prop1":[(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]}
    db_batch.should_receive("remove_exists_filters").and_return(filter_info)
         
    self.assertEquals(dd.is_zigzag_merge_join(query, filter_info, []), True)

    filter_info = {"prop1":[(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop1": [(datastore_pb.Query_Filter.EQUAL, "2")]}
    self.assertEquals(dd.is_zigzag_merge_join(query, filter_info, []), False)

  def test_zigzag_merge_join(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_transaction_id").and_return(1)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("register_updated_key").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive("batch_delete").and_return(None)
    db_batch.should_receive("batch_put_entity").and_return(None)
    db_batch.should_receive("batch_get_entity").and_return(None)

    query = datastore_pb.Query()
    dd = DatastoreDistributed(db_batch, zookeeper) 
    flexmock(dd).should_receive("is_zigzag_merge_join").and_return(False)
    self.assertEquals(dd.zigzag_merge_join(None, None, None), None)

    filter_info = {"prop1":[(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]}
    flexmock(query).should_receive("kind").and_return("kind")
    flexmock(dd).should_receive("get_table_prefix").and_return("prefix")
    flexmock(dd).should_receive("__apply_filters").and_return([])
    flexmock(query).should_receive("limit").and_return(1)
    self.assertEquals(dd.zigzag_merge_join(query, filter_info, []), None)

  def test_get_meta_data_key(self):
    dd = DatastoreDistributed(None, None)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(str(dd.get_meta_data_key("howdy", "doody", "what")), 
      "howdy{0}doody{0}what".format(KEY_DELIMITER))

if __name__ == "__main__":
  unittest.main()    
