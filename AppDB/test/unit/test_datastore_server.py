#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import datetime
import random
import sys
import unittest

from tornado import gen, testing

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore import dbconstants
from appscale.datastore import utils
from appscale.datastore.datastore_distributed import DatastoreDistributed
from appscale.datastore.dbconstants import APP_ENTITY_SCHEMA
from appscale.datastore.dbconstants import JOURNAL_SCHEMA
from appscale.datastore.dbconstants import TOMBSTONE
from appscale.datastore.cassandra_env.entity_id_allocator import\
  ScatteredAllocator

from appscale.datastore.cassandra_env.utils import deletions_for_entity
from appscale.datastore.cassandra_env.utils import index_deletions
from appscale.datastore.cassandra_env.utils import mutations_for_entity

from appscale.datastore.utils import (
  encode_index_pb,
  get_entity_key,
  get_entity_kind,
  get_index_key_from_params,
  get_index_kv_from_tuple,
  get_kind_key
)

from appscale.datastore.zkappscale.entity_lock import EntityLock
from appscale.datastore.zkappscale.zktransaction import ZKTransactionException
from flexmock import flexmock

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb
from google.appengine.datastore import datastore_pb
from google.appengine.ext import db


class Item(db.Model):
  name = db.StringProperty(required = True)


ASYNC_NONE = gen.Future()
ASYNC_NONE.set_result(None)


class TestDatastoreServer(testing.AsyncTestCase):
  """
  A set of test cases for the datastore server (datastore server v2)
  """
  BASIC_ENTITY = ['guestbook', 'Greeting', 'foo', 'content', 'hello world']

  def setUp(self, *args, **kwargs):
    super(TestDatastoreServer, self).setUp(*args, **kwargs)



  def get_zookeeper(self):
    zk_handle = flexmock(handler=flexmock(event_object=lambda: None,
                                          sleep_func=lambda: None,
                                          lock_object=lambda: None))
    zk_handle.should_receive('add_listener')
    zookeeper = flexmock(handle=zk_handle)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("increment_and_get_counter").and_return(0,1000)
    return zookeeper

  def test_get_entity_kind(self):
    item = Item(name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(get_entity_kind(key), "Item")

  def test_kind_key(self):
    item = Item(name="Dyan", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(get_kind_key("howdy", key.key().path()), "howdy\x00Item\x01Item:0000000000\x01")

    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item1)
    self.assertEquals(get_kind_key("howdy", key.key().path()), "howdy\x00Item\x01Item:Bob\x01")

    item2 = Item(key_name="Frank", name="Frank", _app="hello", parent = item1)
    key = db.model_to_protobuf(item2)
    self.assertEquals(get_kind_key("howdy", key.key().path()),
           "howdy\x00Item\x01Item:Bob\x01Item:Frank\x01")

  def test_get_entity_key(self):
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(str(get_entity_key("howdy", key.key().path())), "howdy\x00Item:Bob\x01")

  def test_validate_key(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)

    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    dd.validate_key(key.key())

  def test_get_table_prefix(self):
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    item = Item(key_name="Bob", name="Bob", _app="hello")
    key = db.model_to_protobuf(item)
    self.assertEquals(dd.get_table_prefix(key), "hello\x00")

  def test_get_index_key_from_params(self):
    params = ['a','b','c','d','e']
    self.assertEquals(get_index_key_from_params(params),
                      "a\x00b\x00c\x00d\x00e")

  def test_get_index_kv_from_tuple(self):
    item1 = Item(key_name="Bob", name="Bob", _app="hello")
    item2 = Item(key_name="Sally", name="Sally", _app="hello")
    key1 = db.model_to_protobuf(item1)
    key2 = db.model_to_protobuf(item2)
    tuples_list = [("a\x00b",key1),("a\x00b",key2)]
    self.assertEquals(get_index_kv_from_tuple(
      tuples_list), (['a\x00b\x00Item\x00name\x00\x9aBob\x01\x01\x00Item:Bob\x01',
      'a\x00b\x00Item:Bob\x01'],
      ['a\x00b\x00Item\x00name\x00\x9aSally\x01\x01\x00Item:Sally\x01',
      'a\x00b\x00Item:Sally\x01']))

  def test_get_composite_index_key(self):
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
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

    self.assertEquals(
      dd.get_composite_index_key(composite_index, ent),
      "appid\x00\x00123\x00\x9avalue\x01\x01\x00\x00kind:entity_name\x01")

  @testing.gen_test
  def test_delete_composite_index_metadata(self):
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_delete").and_return(ASYNC_NONE)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd = flexmock(dd)
    dd.index_manager = flexmock(
      projects={'appid': flexmock(delete_index_definition=lambda id_: None)})
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(1)
    yield dd.delete_composite_index_metadata("appid", composite_index)

  @testing.gen_test
  def test_create_composite_index(self):
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_put_entity").and_return(ASYNC_NONE)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    zk_handle = flexmock(ensure_path=lambda path: None,
                         get=lambda path: (None, flexmock(version=None)),
                         set=lambda path, value, version: None)
    dd.zookeeper.handle = zk_handle
    dd = flexmock(dd)
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

    index_id = yield dd.create_composite_index("appid", index)
    assert index_id > 0

  @testing.gen_test
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

    ent = self.get_new_entity_proto(
      "appid", "kind", "entity_name", "prop1", "value", ns="")

    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_put_entity").and_return(ASYNC_NONE).once()
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    yield dd.insert_composite_indexes([ent], [composite_index])

  @testing.gen_test
  def test_fetch_keys(self):
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "bob", "prop1name", "prop1val", ns="blah")
    async_get_1 = gen.Future()
    async_get_1.set_result({
      'test\x00blah\x00test_kind:bob\x01': {
        APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    })
    async_get_2 = gen.Future()
    async_get_2.set_result({
      'test\x00blah\x00test_kind:bob\x01\x000000000002': {
        JOURNAL_SCHEMA[0]: entity_proto1.Encode()
    }})

    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_delete").and_return(ASYNC_NONE)
    db_batch.should_receive("batch_put_entity").and_return(ASYNC_NONE)
    db_batch.should_receive("batch_get_entity").\
      and_return(async_get_1).\
      and_return(async_get_2)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("release_lock").and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)

    fetched = yield dd.fetch_keys([entity_proto1.key()])
    self.assertEquals(fetched[0], {
      'test\x00blah\x00test_kind:bob\x01': {
       'txnID': 1, 'entity': entity_proto1.Encode()
      }
    })
    self.assertEqual(fetched[1], ['test\x00blah\x00test_kind:bob\x01'])

  def test_rollback_transcation(self):
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("release_lock").and_return(True)
    zookeeper.should_receive("notify_failed_transaction").and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    commit_request = datastore_pb.Transaction()
    commit_request.set_handle(123)
    commit_request.set_app("aaa")
    self.assertEquals(
      dd.rollback_transaction("app_id", commit_request.handle()), None)

  @staticmethod
  def get_new_entity_proto(app_id, kind, entity_name, prop_name, prop_value, ns=""):
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

  @testing.gen_test
  def test_dynamic_put(self):
    db_batch = flexmock(session=flexmock())
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "bob", "prop1name", "prop1val", ns="blah")
    entity_key1 = 'test\x00blah\x00test_kind:bob\x01'
    entity_proto2 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop2val", ns="blah")
    entity_key2 = 'test\x00blah\x00test_kind:nancy\x01'
    async_result = gen.Future()
    async_result.set_result({entity_key1: {}, entity_key2: {}})

    db_batch.should_receive('batch_get_entity').and_return(async_result)
    db_batch.should_receive('normal_batch').and_return(ASYNC_NONE)
    transaction_manager = flexmock(
      create_transaction_id=lambda project, xg: 1,
      delete_transaction_id=lambda project, txid: None,
      set_groups=lambda project, txid, groups: None)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={'test': flexmock(indexes_pb=[])})
    putreq_pb = datastore_pb.PutRequest()
    putreq_pb.add_entity()
    putreq_pb.mutable_entity(0).MergeFrom(entity_proto1)
    putreq_pb.add_entity()
    putreq_pb.mutable_entity(1).MergeFrom(entity_proto2)

    putresp_pb = datastore_pb.PutResponse()

    async_true = gen.Future()
    async_true.set_result(True)
    entity_lock = flexmock(EntityLock)
    entity_lock.should_receive('acquire').and_return(async_true)
    entity_lock.should_receive('release')

    flexmock(ScatteredAllocator).should_receive('next').\
      and_return(random.randint(1, 500))

    yield dd.dynamic_put('test', putreq_pb, putresp_pb)
    self.assertEquals(len(putresp_pb.key_list()), 2)

  @testing.gen_test
  def test_put_entities(self):
    app_id = 'test'
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    entity_proto1 = self.get_new_entity_proto(
      app_id, "test_kind", "bob", "prop1name", "prop1val", ns="blah")
    entity_key1 = 'test\x00blah\x00test_kind:bob\x01'
    entity_proto2 = self.get_new_entity_proto(
      app_id, "test_kind", "nancy", "prop1name", "prop2val", ns="blah")
    entity_key2 = 'test\x00blah\x00test_kind:nancy\x01'
    entity_list = [entity_proto1, entity_proto2]
    async_result = gen.Future()
    async_result.set_result({entity_key1: {}, entity_key2: {}})

    db_batch.should_receive('batch_get_entity').and_return(async_result)
    db_batch.should_receive('normal_batch').and_return(ASYNC_NONE)
    transaction_manager = flexmock(
      create_transaction_id=lambda project, xg: 1,
      delete_transaction_id=lambda project, txid: None,
      set_groups=lambda project, txid, groups: None)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={app_id: flexmock(indexes_pb=[])})

    async_true = gen.Future()
    async_true.set_result(True)
    entity_lock = flexmock(EntityLock)
    entity_lock.should_receive('acquire').and_return(async_true)
    entity_lock.should_receive('release')

    yield dd.put_entities(app_id, entity_list)

  def test_acquire_locks_for_trans(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    flexmock(dd).should_receive("is_instance_wrapper").and_return(False).once()
    self.assertRaises(TypeError, dd.acquire_locks_for_trans, [1], 1)

    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(False).and_return(False)
    self.assertRaises(TypeError, dd.acquire_locks_for_trans, [1], 1)

    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True)

    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(False)
    flexmock(dd).should_receive("get_table_prefix").and_return("prefix").never()
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").never()
    self.assertEquals({}, dd.acquire_locks_for_trans([], 1))

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("acquire_lock").once()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    entity = flexmock()
    entity.should_receive("app").and_return("appid")
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(True)
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").once()
    self.assertEquals({'rootkey':1}, dd.acquire_locks_for_trans([entity], 1))

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("acquire_lock").once().and_raise(ZKTransactionException)
    zookeeper.should_receive("notify_failed_transaction").once()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    entity = flexmock()
    entity.should_receive("app").and_return("appid")
    flexmock(dd).should_receive("is_instance_wrapper").and_return(True) \
      .and_return(True).and_return(True)
    flexmock(dd).should_receive("get_root_key_from_entity_key").and_return("rootkey").once()
    self.assertRaises(ZKTransactionException, dd.acquire_locks_for_trans, [entity], 1)

  @testing.gen_test
  def test_delete_entities(self):
    app_id = 'test'
    entity_proto1 = self.get_new_entity_proto(
      app_id, "test_kind", "bob", "prop1name", "prop1val", ns="blah")
    row_key = "test\x00blah\x00test_kind:bob\x01"
    row_values = {row_key: {APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
                            APP_ENTITY_SCHEMA[1]: '1'}}
    async_result = gen.Future()
    async_result.set_result(row_values)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_get_entity").and_return(async_result)
    db_batch.should_receive('normal_batch').and_return(ASYNC_NONE)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)

    row_keys = [entity_proto1.key()]

    yield dd.delete_entities(entity_proto1.key(), 1, row_keys)

  def test_release_put_locks_for_nontrans(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("release_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "bob", "prop1name", "prop1val", ns="blah")
    entity_proto2 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop2val", ns="blah")
    entities = [entity_proto1, entity_proto2]
    dd.release_locks_for_nontrans(
      "test", entities, {
        'test\x00blah\x00test_kind:bob\x01': 1,
        'test\x00blah\x00test_kind:nancy\x01': 2
      })

  def test_root_key_from_entity_key(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    self.assertEquals(
      "test\x00blah\x00test_kind:bob\x01",
      dd.get_root_key_from_entity_key("test\x00blah\x00test_kind:bob\x01nancy\x01")
    )
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop2val", ns="blah")
    self.assertEquals(
      "test\x00blah\x00test_kind:nancy\x01",
      dd.get_root_key_from_entity_key(entity_proto1.key())
    )

  @testing.gen_test
  def test_dynamic_get(self):
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop2val", ns="blah")

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    async_result = gen.Future()
    async_result.set_result({
      "test\x00blah\x00test_kind:nancy\x01": {
        APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    })

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_get_entity").and_return(async_result)
    db_batch.should_receive('record_reads').and_return(ASYNC_NONE)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)

    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key()
    key.MergeFrom(entity_key)
    get_resp = datastore_pb.GetResponse()

    yield dd.dynamic_get("test", get_req, get_resp)
    self.assertEquals(get_resp.entity_size(), 1)

    # Now test while in a transaction
    get_resp = datastore_pb.GetResponse()
    get_req.mutable_transaction().set_handle(1)
    yield dd.dynamic_get("test", get_req, get_resp)
    self.assertEquals(get_resp.entity_size(), 1)

  @testing.gen_test
  def test_ancestor_query(self):
    query = datastore_pb.Query()
    ancestor = query.mutable_ancestor()
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop1val", ns="blah")
    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key()
    key.MergeFrom(entity_key)
    ancestor.MergeFrom(entity_key)

    async_result = gen.Future()
    async_result.set_result({
      "test\x00blah\x00test_kind:nancy\x01": {
        APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    })

    filter_info = []
    tombstone1 = {'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE, APP_ENTITY_SCHEMA[1]: 1}}
    db_batch = flexmock()
    db_batch.should_receive('record_reads').and_return(ASYNC_NONE)
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_get_entity").and_return(async_result)

    entity_proto1 = {
      'test\x00blah\x00test_kind:nancy\x01': {
        APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    }
    async_result_1 = gen.Future()
    async_result_1.set_result([entity_proto1, tombstone1])
    async_result_2 = gen.Future()
    async_result_2.set_result([])

    db_batch.should_receive("range_query").\
      and_return(async_result_1).\
      and_return(async_result_2)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("acquire_lock").and_return(True)
    zookeeper.should_receive("is_in_transaction").and_return(False)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    yield dd.ancestor_query(query, filter_info)
    # Now with a transaction
    transaction = query.mutable_transaction()
    transaction.set_handle(2)
    yield dd.ancestor_query(query, filter_info)

  @testing.gen_test
  def test_kindless_query(self):
    query = datastore_pb.Query()
    entity_proto1 = self.get_new_entity_proto(
      "test", "test_kind", "nancy", "prop1name", "prop1val", ns="blah")
    entity_key = entity_proto1.key()
    get_req = datastore_pb.GetRequest()
    key = get_req.add_key()
    key.MergeFrom(entity_key)

    async_result = gen.Future()
    async_result.set_result({
      "test\x00blah\x00test_kind:nancy\x01": {
        APP_ENTITY_SCHEMA[0]: entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    })

    tombstone1 = {'key': {APP_ENTITY_SCHEMA[0]:TOMBSTONE, APP_ENTITY_SCHEMA[1]: 1}}
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive("batch_get_entity").and_return(async_result)

    entity_proto1 = {
      'test\x00blah\x00test_kind:nancy\x01': {
        APP_ENTITY_SCHEMA[0]:entity_proto1.Encode(),
        APP_ENTITY_SCHEMA[1]: 1
      }
    }
    async_result_1 = gen.Future()
    async_result_1.set_result([entity_proto1, tombstone1])
    async_result_2 = gen.Future()
    async_result_2.set_result([])
    db_batch.should_receive("range_query").\
      and_return(async_result_1).\
      and_return(async_result_2)

    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    zookeeper.should_receive("get_valid_transaction_id").and_return(1)
    zookeeper.should_receive("is_in_transaction").and_return(False)
    zookeeper.should_receive("acquire_lock").and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    filter_info = {
      '__key__' : [[0, 0]]
    }
    yield dd.kindless_query(query, filter_info)

  @testing.gen_test
  def test_dynamic_delete(self):
    async_true = gen.Future()
    async_true.set_result(True)
    entity_lock = flexmock(EntityLock)
    entity_lock.should_receive('acquire').and_return(async_true)
    entity_lock.should_receive('release')

    del_request = flexmock()
    del_request.should_receive("key_list")
    del_request.should_receive("has_transaction").never()
    del_request.should_receive("transaction").never()
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    transaction_manager = flexmock(
      create_transaction_id=lambda project, xg: 1,
      delete_transaction_id=lambda project, txid: None,
      set_groups=lambda project_id, txid, groups: None)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={'guestbook': flexmock(indexes_pb=[])})
    yield dd.dynamic_delete("appid", del_request)

    fake_key = entity_pb.Reference()
    fake_key.set_app('foo')
    path = fake_key.mutable_path()
    element = path.add_element()
    element.set_type('bar')
    element.set_id(1)

    del_request = flexmock()
    del_request.should_receive("key_list").and_return([fake_key])
    del_request.should_receive("has_transaction").and_return(True)
    transaction = flexmock()
    transaction.should_receive("handle").and_return(1)
    del_request.should_receive("transaction").and_return(transaction)
    del_request.should_receive("has_mark_changes").and_return(False)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={'appid': flexmock(indexes_pb=[])})
    flexmock(utils).should_receive("get_entity_kind").and_return("kind")
    db_batch.should_receive('delete_entities_tx').and_return(ASYNC_NONE)
    yield dd.dynamic_delete("appid", del_request)

    del_request = flexmock()
    del_request.should_receive("key_list").and_return([fake_key])
    del_request.should_receive("has_transaction").and_return(False)
    del_request.should_receive("has_mark_changes").and_return(False)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={'appid': flexmock(indexes_pb=[])})
    flexmock(dd).should_receive("delete_entities").and_return(ASYNC_NONE).once()
    yield dd.dynamic_delete("appid", del_request)

  def test_reverse_path(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    key = "Project:Synapse\x01Module:Core\x01"
    self.assertEquals(dd.reverse_path(key), "Module:Core\x01Project:Synapse\x01")

  def test_remove_exists_filters(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    self.assertEquals(dd.remove_exists_filters({}), {})

    filter_info = {
      "prop1": [(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]
    }
    self.assertEquals(dd.remove_exists_filters(filter_info), filter_info)

    filter_info = {
      "prop1": [(datastore_pb.Query_Filter.EXISTS, "1")],
      "prop2": [(datastore_pb.Query_Filter.EXISTS, "2")]
    }
    self.assertEquals(dd.remove_exists_filters(filter_info), {})

  def test_is_zigzag_merge_join(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    query = datastore_pb.Query()
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    self.assertEquals(dd.is_zigzag_merge_join(query, {}, {}), False)
    filter_info = {
      "prop1": [(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]
    }
    self.assertEquals(dd.is_zigzag_merge_join(query, filter_info, []), True)

    filter_info = {
      "prop1": [(datastore_pb.Query_Filter.EQUAL, "1")]
    }
    self.assertEquals(dd.is_zigzag_merge_join(query, filter_info, []), False)

  @testing.gen_test
  def test_zigzag_merge_join(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)

    query = datastore_pb.Query()
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager, zookeeper)
    flexmock(dd).should_receive("is_zigzag_merge_join").and_return(False)
    result = yield dd.zigzag_merge_join(None, None, None)
    self.assertEquals(result, (None, False))

    filter_info = {
      "prop1": [(datastore_pb.Query_Filter.EQUAL, "1")],
      "prop2": [(datastore_pb.Query_Filter.EQUAL, "2")]
    }
    result = yield dd.zigzag_merge_join(query, filter_info, [])
    self.assertEquals(result, (None, False))

  def test_index_deletions(self):
    old_entity = self.get_new_entity_proto(*self.BASIC_ENTITY)

    # No deletions should occur when the entity doesn't change.
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    self.assertListEqual([], index_deletions(old_entity, old_entity))

    # When a property changes, the previous index entries should be deleted.
    new_entity = entity_pb.EntityProto()
    new_entity.MergeFrom(old_entity)
    new_entity.property_list()[0].value().set_stringvalue('updated content')

    deletions = index_deletions(old_entity, new_entity)
    self.assertEqual(len(deletions), 2)
    self.assertEqual(deletions[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(deletions[1]['table'], dbconstants.DSC_PROPERTY_TABLE)

    prop = old_entity.add_property()
    prop.set_name('author')
    value = prop.mutable_value()
    value.set_stringvalue('author1')

    prop = new_entity.add_property()
    prop.set_name('author')
    value = prop.mutable_value()
    value.set_stringvalue('author1')

    # When given an index, an entry should be removed from the composite table.
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id('guestbook')
    definition = composite_index.mutable_definition()
    definition.set_entity_type('Greeting')
    prop1 = definition.add_property()
    prop1.set_name('content')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)
    prop2 = definition.add_property()
    prop2.set_name('author')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)
    deletions = index_deletions(old_entity, new_entity, (composite_index,))
    self.assertEqual(len(deletions), 3)
    self.assertEqual(deletions[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(deletions[1]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(deletions[2]['table'], dbconstants.COMPOSITE_TABLE)

    # No composite deletions should occur when the entity type differs.
    definition.set_entity_type('TestEntity')
    deletions = index_deletions(old_entity, new_entity, (composite_index,))
    self.assertEqual(len(deletions), 2)

  def test_deletions_for_entity(self):
    entity = self.get_new_entity_proto(*self.BASIC_ENTITY)

    # Deleting an entity with one property should remove four entries.
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    deletions = deletions_for_entity(entity)
    self.assertEqual(len(deletions), 4)
    self.assertEqual(deletions[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(deletions[1]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(deletions[2]['table'], dbconstants.APP_ENTITY_TABLE)
    self.assertEqual(deletions[3]['table'], dbconstants.APP_KIND_TABLE)

    prop = entity.add_property()
    prop.set_name('author')
    value = prop.mutable_value()
    value.set_stringvalue('author1')

    # Deleting an entity with two properties and one composite index should
    # remove seven entries.
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id('guestbook')
    definition = composite_index.mutable_definition()
    definition.set_entity_type('Greeting')
    prop1 = definition.add_property()
    prop1.set_name('content')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)
    prop2 = definition.add_property()
    prop2.set_name('author')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)
    deletions = deletions_for_entity(entity, (composite_index,))
    self.assertEqual(len(deletions), 7)
    self.assertEqual(deletions[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(deletions[1]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(deletions[2]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(deletions[3]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(deletions[4]['table'], dbconstants.COMPOSITE_TABLE)
    self.assertEqual(deletions[5]['table'], dbconstants.APP_ENTITY_TABLE)
    self.assertEqual(deletions[6]['table'], dbconstants.APP_KIND_TABLE)

  def test_mutations_for_entity(self):
    entity = self.get_new_entity_proto(*self.BASIC_ENTITY)
    txn = 1

    # Adding an entity with one property should add four entries.
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    mutations = mutations_for_entity(entity, txn)
    self.assertEqual(len(mutations), 4)
    self.assertEqual(mutations[0]['table'], dbconstants.APP_ENTITY_TABLE)
    self.assertEqual(mutations[1]['table'], dbconstants.APP_KIND_TABLE)
    self.assertEqual(mutations[2]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[3]['table'], dbconstants.DSC_PROPERTY_TABLE)

    # Updating an entity with one property should delete two entries and add
    # four more.
    new_entity = entity_pb.EntityProto()
    new_entity.MergeFrom(entity)
    new_entity.property_list()[0].value().set_stringvalue('updated content')
    mutations = mutations_for_entity(entity, txn, new_entity)
    self.assertEqual(len(mutations), 6)
    self.assertEqual(mutations[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[0]['operation'], dbconstants.Operations.DELETE)
    self.assertEqual(mutations[1]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(mutations[1]['operation'], dbconstants.Operations.DELETE)
    self.assertEqual(mutations[2]['table'], dbconstants.APP_ENTITY_TABLE)
    self.assertEqual(mutations[3]['table'], dbconstants.APP_KIND_TABLE)
    self.assertEqual(mutations[4]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[5]['table'], dbconstants.DSC_PROPERTY_TABLE)

    prop = entity.add_property()
    prop.set_name('author')
    prop.set_multiple(0)
    value = prop.mutable_value()
    value.set_stringvalue('author1')

    prop = new_entity.add_property()
    prop.set_name('author')
    prop.set_multiple(0)
    value = prop.mutable_value()
    value.set_stringvalue('author1')

    # Updating one property of an entity with two properties and one composite
    # index should remove three entries and add seven more.
    composite_index = entity_pb.CompositeIndex()
    composite_index.set_id(123)
    composite_index.set_app_id('guestbook')
    definition = composite_index.mutable_definition()
    definition.set_entity_type('Greeting')
    prop1 = definition.add_property()
    prop1.set_name('content')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)
    prop2 = definition.add_property()
    prop2.set_name('author')
    prop1.set_direction(datastore_pb.Query_Order.ASCENDING)

    mutations = mutations_for_entity(entity, txn, new_entity,
                                     (composite_index,))
    self.assertEqual(len(mutations), 10)
    self.assertEqual(mutations[0]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[0]['operation'], dbconstants.Operations.DELETE)
    self.assertEqual(mutations[1]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(mutations[1]['operation'], dbconstants.Operations.DELETE)
    self.assertEqual(mutations[2]['table'], dbconstants.COMPOSITE_TABLE)
    self.assertEqual(mutations[2]['operation'], dbconstants.Operations.DELETE)
    self.assertEqual(mutations[3]['table'], dbconstants.APP_ENTITY_TABLE)
    self.assertEqual(mutations[4]['table'], dbconstants.APP_KIND_TABLE)
    self.assertEqual(mutations[5]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[6]['table'], dbconstants.ASC_PROPERTY_TABLE)
    self.assertEqual(mutations[7]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(mutations[8]['table'], dbconstants.DSC_PROPERTY_TABLE)
    self.assertEqual(mutations[9]['table'], dbconstants.COMPOSITE_TABLE)

  @testing.gen_test
  def test_apply_txn_changes(self):
    app = 'guestbook'
    txn = 1
    entity = self.get_new_entity_proto(app, *self.BASIC_ENTITY[1:])

    async_metadata = gen.Future()
    async_metadata.set_result({
      'puts': {entity.key().Encode(): entity.Encode()},
      'deletes': [],
      'tasks': [],
      'reads': set(),
      'start': datetime.datetime.utcnow(),
      'is_xg': False,
    })

    db_batch = flexmock()
    db_batch.should_receive('get_transaction_metadata').\
      and_return(async_metadata)
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    db_batch.should_receive('group_updates').and_return([])

    transaction_manager = flexmock(
      delete_transaction_id=lambda project_id, txid: None,
      set_groups=lambda project_id, txid, groups: None)
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    dd.index_manager = flexmock(
      projects={'guestbook': flexmock(indexes_pb=[])})
    prefix = dd.get_table_prefix(entity)
    entity_key = get_entity_key(prefix, entity.key().path())

    async_result = gen.Future()
    async_result.set_result({entity_key: {}})

    db_batch.should_receive('batch_get_entity').and_return(async_result)
    db_batch.should_receive('normal_batch').and_return(ASYNC_NONE)

    async_true = gen.Future()
    async_true.set_result(True)
    entity_lock = flexmock(EntityLock)
    entity_lock.should_receive('acquire').and_return(async_true)
    entity_lock.should_receive('release')

    yield dd.apply_txn_changes(app, txn)

  def test_extract_entities_from_composite_indexes(self):
    project_id = 'guestbook'
    props = ['prop1', 'prop2']
    db_batch = flexmock()
    db_batch.should_receive('valid_data_version_sync').and_return(True)
    transaction_manager = flexmock()
    dd = DatastoreDistributed(db_batch, transaction_manager,
                              self.get_zookeeper())
    query = datastore_pb.Query()
    for prop_name in props:
      query.add_property_name(prop_name)

    index = query.add_composite_index()
    definition = index.mutable_definition()
    for prop_name in props:
      prop = definition.add_property()
      prop.set_name(prop_name)

    entity_id = 1524699263329044
    val1 = entity_pb.PropertyValue()
    val1.set_int64value(5)
    val2 = entity_pb.PropertyValue()
    val2.set_stringvalue('test')
    index_key = '\x00'.join(
      [project_id, 'namespace', 'index1', str(encode_index_pb(val1)),
       str(encode_index_pb(val2)), 'Greeting:{}\x01'.format(entity_id)])

    index_results = [{index_key: {'reference': 'ignored-ref'}}]
    entities = dd._extract_entities_from_composite_indexes(
      query, index_results, index)
    self.assertEqual(len(entities), 1)
    returned_entity = entity_pb.EntityProto(entities[0])
    self.assertEqual(returned_entity.property_size(), 2)
    self.assertEqual(returned_entity.key().path().element(0).type(), 'Greeting')
    self.assertEqual(returned_entity.key().path().element(0).id(), entity_id)
    self.assertEqual(returned_entity.property(0).name(), 'prop1')
    self.assertEqual(returned_entity.property(0).value().int64value(), 5)
    self.assertEqual(returned_entity.property(1).name(), 'prop2')
    self.assertEqual(returned_entity.property(1).value().stringvalue(), 'test')

if __name__ == "__main__":
  unittest.main()
