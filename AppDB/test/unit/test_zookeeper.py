#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import time
import unittest

from flexmock import flexmock
import kazoo.client
import kazoo.exceptions
import kazoo.protocol
import kazoo.protocol.states

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from dbconstants import *

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException


class TestZookeeperTransaction(unittest.TestCase):
  """
  """

  def setUp(self):
    self.appid = 'appid'
    self.handle = None

  def test_increment_and_get_counter(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', create='create',
      delete_async='delete_async')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').and_return(None)

    fake_counter = flexmock(name='fake_counter', value='value')
    fake_counter.value = 1
    fake_counter.should_receive('__add__').and_return(2)
    fake_zookeeper.should_receive("Counter").and_return(fake_counter)
    # mock out deleting the zero id we get the first time around

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # assert, make sure we got back our id
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals((0, 1), transaction.increment_and_get_counter(
      self.appid, 1))


  def test_create_sequence_node(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', create='create',
      delete='delete')
    fake_zookeeper.should_receive('start')

    # mock out zookeeper.create for txn id
    path_to_create = "/rootpath/" + self.appid
    zero_path = path_to_create + "/0"
    nonzero_path = path_to_create + "/1"


    fake_zookeeper.should_receive('retry').with_args('create', str, value=str,
      acl=None, makepath=bool, sequence=bool, ephemeral=bool).\
      and_return(zero_path).and_return(nonzero_path)

    # mock out deleting the zero id we get the first time around
    fake_zookeeper.should_receive('retry').with_args('delete', zero_path)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # assert, make sure we got back our id
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(1, transaction.create_sequence_node('/rootpath/' + \
      self.appid, 'now'))

  def test_create_node(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', create='create')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('create', str, value=str,
      acl=None, makepath=bool, sequence=bool, ephemeral=bool)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # mock out zookeeper.create for txn id
    path_to_create = "/rootpath/" + self.appid
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(None, transaction.create_node('/rootpath/' + self.appid,
      'now'))


  def test_get_transaction_id(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath/' + self.appid)
    path_to_create = "/rootpath/" + self.appid + "/" + zk.APP_TX_PREFIX
    zk.ZKTransaction.should_receive('get_txn_path_before_getting_id') \
      .with_args(self.appid).and_return(path_to_create)
    
    # mock out time.time
    flexmock(time)
    time.should_receive('time').and_return(1000)
    
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry')

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # mock out making the txn id
    zk.ZKTransaction.should_receive('create_sequence_node').with_args(
      path_to_create, '1000').and_return(1)

    # mock out zookeeper.create for is_xg
    xg_path = path_to_create + "/1/" + zk.XG_PREFIX
    zk.ZKTransaction.should_receive('get_xg_path').and_return(xg_path)
    zk.ZKTransaction.should_receive('create_node').with_args(xg_path, '1000')

    # assert, make sure we got back our id
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(1, transaction.get_transaction_id(self.appid, is_xg=True))

  def test_get_txn_path_before_getting_id(self):
    # mock out initializing a ZK connection
    flexmock(zk.ZKTransaction)

    fake_zookeeper = flexmock(name='fake_zoo')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry')

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    zk.ZKTransaction.should_receive('get_app_root_path').and_return("app_root_path")

    expected = zk.PATH_SEPARATOR.join(["app_root_path", zk.APP_TX_PATH, zk.APP_TX_PREFIX])
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(expected,
      transaction.get_txn_path_before_getting_id(self.appid))

  def test_get_xg_path(self):
    # mock out initializing a ZK connection
    flexmock(zk.ZKTransaction)

    fake_zookeeper = flexmock(name='fake_zoo')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry')

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)
 
    tx_id = 100
    tx_str = zk.APP_TX_PREFIX + "%010d" % tx_id
    zk.ZKTransaction.should_receive('get_app_root_path') \
      .and_return("app_root_path")

    expected = zk.PATH_SEPARATOR.join(["app_root_path", zk.APP_TX_PATH,
      tx_str, zk.XG_PREFIX]) 

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(expected, transaction.get_xg_path("xxx", 100))

  def test_is_in_transaction(self):
    # shared mocks
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_path') \
      .and_return('/transaction/path')

    fake_zookeeper = flexmock(name='fake_zoo', exists='exists')
    fake_zookeeper.should_receive('start')

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # test when the transaction is running
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.is_in_transaction(self.appid, 1))

    # and when it's not
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(False)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(False, transaction.is_in_transaction(self.appid, 1))

    # and when it's blacklisted
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(True)
    fake_transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException, transaction.is_in_transaction,
      self.appid, 1)

  def test_acquire_lock(self):
    # mock out waitForConnect
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_lock_root_path').\
       and_return('/lock/root/path')
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').\
       and_return('/rootpath/' + self.appid)
    fake_zookeeper = flexmock(name='fake_zoo', get='get')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry')

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # first, test out getting a lock for a regular transaction, that we don't
    # already have the lock for
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(False)
    zk.ZKTransaction.should_receive('acquire_additional_lock').and_return(True)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_lock(self.appid, "txid",
      "somekey"))

    # next, test when we're in a transaction and we already have the lock
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(True)
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
       and_return('/rootpath/' + self.appid + "/tx1")
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return(['/lock/root/path'])

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_lock(self.appid, "txid",
      "somekey"))

    # next, test when we're in a non-XG transaction and we're not in the lock
    # root path
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(True)
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
       and_return('/rootpath/' + self.appid + "/tx1")
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return(['/lock/root/path2'])
    zk.ZKTransaction.should_receive('is_xg').and_return(False)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException, transaction.acquire_lock, 
      self.appid, "txid", "somekey")

    # next, test when we're in a XG transaction and we're not in the lock
    # root path
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(True)
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
       and_return('/rootpath/' + self.appid + "/tx1")
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return(['/lock/root/path2'])
    zk.ZKTransaction.should_receive('is_xg').and_return(True)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_lock(self.appid, "txid",
      "somekey"))


  def test_acquire_additional_lock(self):
    # mock out waitForConnect
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('check_transaction')
    zk.ZKTransaction.should_receive('get_transaction_path').\
       and_return('/txn/path')
    zk.ZKTransaction.should_receive('get_lock_root_path').\
       and_return('/lock/root/path')
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').\
       and_return('/rootpath/' + self.appid)

    fake_zookeeper = flexmock(name='fake_zoo', create='create',
      create_async='create_async', get='get', set_async='set_async')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('create', str, makepath=bool, sequence=bool,
      ephemeral=bool, value=str, acl=None).and_return("/some/lock/path")
    fake_zookeeper.should_receive('retry').with_args('create_async', str, value=str,
      acl=None, ephemeral=bool, makepath=bool)
    lock_list = ['path1', 'path2', 'path3'] 
    lock_list_str = zk.LOCK_LIST_SEPARATOR.join(lock_list)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([lock_list_str])
    fake_zookeeper.should_receive('retry').with_args('set_async', str, str)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_additional_lock(self.appid,
      "txid", "somekey", False))
 #MethodSignatureError: retry("create", "/lock/root/path", makepath=True, sequence=False, ephemeral=False, value="/txn/path", acl=None) 

    # Test for when we want to create a new ZK node for the lock path
    self.assertEquals(True, transaction.acquire_additional_lock(self.appid,
      "txid", "somekey", True))

    # Test for existing max groups 
    lock_list = ['path1', 'path2', 'path3', 'path4', 'path5'] 
    lock_list_str = zk.LOCK_LIST_SEPARATOR.join(lock_list)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([lock_list_str])

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException,
      transaction.acquire_additional_lock, self.appid, "txid", "somekey", False)

    # Test for when there is a node which already exists.
    fake_zookeeper.should_receive('retry').with_args('create', str, str, None,
      bool, bool, bool).and_raise(kazoo.exceptions.NodeExistsError)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException,
      transaction.acquire_additional_lock, self.appid, "txid", "somekey", False)


  def test_check_transaction(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.check_transaction(self.appid, 1))

    # Check to make sure it raises exception for blacklisted transactions.
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(True)
    self.assertRaises(zk.ZKTransactionException, transaction.check_transaction,
      self.appid, 1)

    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(False)
    self.assertRaises(zk.ZKTransactionException, transaction.check_transaction,
      self.appid, 1)
  
  def test_is_xg(self):
    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.is_xg(self.appid, 1))

  def test_release_lock(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('check_transaction')
    zk.ZKTransaction.should_receive('get_transaction_path').\
      and_return('/rootpath')
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
      and_return('/rootpath')
    zk.ZKTransaction.should_receive('is_xg').and_return(False)

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists', get='get',
      delete='delete', delete_async='delete_async', get_children='get_children')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return(['/1/2/3'])
    fake_zookeeper.should_receive('retry').with_args('delete_async', str)
    fake_zookeeper.should_receive('retry').with_args('delete', str)
    fake_zookeeper.should_receive('retry').with_args('get_children', str) \
      .and_return(['1','2'])

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.release_lock(self.appid, 1))

    zk.ZKTransaction.should_receive('is_xg').and_return(True)
    self.assertEquals(True, transaction.release_lock(self.appid, 1))

    # Check to make sure it raises exception for blacklisted transactions.
    zk.ZKTransaction.should_receive('is_xg').and_return(False)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_raise(kazoo.exceptions.NoNodeError)
    self.assertRaises(zk.ZKTransactionException, transaction.release_lock,
      self.appid, 1)


  def test_is_blacklisted(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_blacklist_root_path').\
      and_return("bl_root_path")

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', create='create', exists='exists',
      get_children='get_children')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('create', str, str, None,
      bool, bool, bool).and_return()
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    fake_zookeeper.should_receive('retry').with_args('get_children', str) \
      .and_return(['1','2'])

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.is_blacklisted(self.appid, 1))

  def test_register_updated_key(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_valid_transaction_path').\
      and_return('/txn/path')
    zk.ZKTransaction.should_receive('get_transaction_path').\
      and_return('/txn/path')

    zk.ZKTransaction.should_receive('get_blacklist_root_path').\
      and_return("bl_root_path")

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists',
      set_async='set_async')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    fake_zookeeper.should_receive('retry').with_args('set_async', str, str)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.register_updated_key(self.appid, 
      "1", "2", "somekey"))

    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(False)
    self.assertRaises(ZKTransactionException, 
      transaction.register_updated_key, self.appid, "1", "2", "somekey")

  def test_try_garbage_collection(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('update_node')

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists', get='get',
      get_children='get_children', create='create', delete='delete')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([str(time.time() + 10000)])
    fake_zookeeper.should_receive('retry').with_args('get_children', str) \
      .and_return(['1','2','3'])
    fake_zookeeper.should_receive('retry').with_args('create', str, value=str, 
      acl=None, ephemeral=bool)
    fake_zookeeper.should_receive('retry').with_args('delete', str)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    # Put the last time we ran GC way into the future.
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(False, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # Make it so we recently ran the GC
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([str(time.time())])
    self.assertEquals(False, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # Make it so we ran the GC a long time ago.
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([str(time.time() - 1000)])
    self.assertEquals(True, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # No node means we have not run the GC before, so run it.
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_raise(kazoo.exceptions.NoNodeError)
    self.assertEquals(True, transaction.try_garbage_collection(self.appid, 
      "/some/path"))
    
  def test_notify_failed_transaction(self):
    pass
    #TODO  

  def test_execute_garbage_collection(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('notify_failed_transaction')

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', exists='exists', get='get',
      get_children='get_children')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('exists', str) \
      .and_return(True)
    fake_zookeeper.should_receive('retry').with_args('get', str) \
      .and_return([str(time.time() + 10000)])
    fake_zookeeper.should_receive('retry').with_args('get_children', str) \
      .and_return(['1','2','3'])

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    transaction.execute_garbage_collection(self.appid, "some/path")

  def test_get_datastore_groomer_lock(self):
    flexmock(zk.ZKTransaction)

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', create='create')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('create', str, value=str,
      acl=None, ephemeral=bool).and_return(True)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.get_datastore_groomer_lock())

    fake_zookeeper.should_receive('retry').with_args('create', str, value=str,
      acl=None, ephemeral=bool).and_raise(kazoo.exceptions.NodeExistsError)
    self.assertEquals(False, transaction.get_datastore_groomer_lock())
  
  def test_release_datastore_groomer_lock(self):
    flexmock(zk.ZKTransaction)

    # mock out initializing a ZK connection
    fake_zookeeper = flexmock(name='fake_zoo', delete='delete')
    fake_zookeeper.should_receive('start')
    fake_zookeeper.should_receive('retry').with_args('delete', str)

    flexmock(kazoo.client)
    kazoo.client.should_receive('KazooClient').and_return(fake_zookeeper)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.release_datastore_groomer_lock())

    fake_zookeeper.should_receive('retry').with_args('delete', str) \
      .and_raise(kazoo.exceptions.NoNodeError)
    self.assertRaises(ZKTransactionException,
      transaction.release_datastore_groomer_lock)
     
if __name__ == "__main__":
  unittest.main()    
