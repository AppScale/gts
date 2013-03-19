#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import time
import unittest

from flexmock import flexmock
import zookeeper

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

  def test_create_sequence_node(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

    # mock out zookeeper.create for txn id
    path_to_create = "/rootpath/" + self.appid
    zero_path = path_to_create + "/0"
    nonzero_path = path_to_create + "/1"
    zookeeper.should_receive('create').with_args(self.handle, path_to_create,
      "now", zk.ZOO_ACL_OPEN, zookeeper.SEQUENCE).and_return(zero_path) \
      .and_return(nonzero_path)

    # mock out deleting the zero id we get the first time around
    zookeeper.should_receive('adelete').with_args(self.handle, zero_path)

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
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

    # mock out zookeeper.create for txn id
    path_to_create = "/rootpath/" + self.appid
    zookeeper.should_receive('create').with_args(self.handle, path_to_create,
      "now", zk.ZOO_ACL_OPEN)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(None, transaction.create_node('/rootpath/' + self.appid,
      'now'))


  def test_get_transaction_id(self):
    # mock out waitForConnect
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    
    # mock out getTransactionRootPath
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath/' + self.appid)
    path_to_create = "/rootpath/" + self.appid + "/" + zk.APP_TX_PREFIX
    zk.ZKTransaction.should_receive('get_transaction_path_before_getting_id') \
      .with_args(self.appid).and_return(path_to_create)
    
    # mock out time.time
    flexmock(time)
    time.should_receive('time').and_return(1000)
    
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

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

  def test_get_transaction_path_before_getting_id(self):
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    flexmock(zk.ZKTransaction)

    zookeeper.should_receive('init').and_return(self.handle)
    
    zk.ZKTransaction.should_receive('get_app_root_path') \
      .and_return("app_root_path")

    expected = zk.PATH_SEPARATOR.join(["app_root_path", zk.APP_TX_PATH, zk.APP_TX_PREFIX])
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(expected,
      transaction.get_transaction_path_before_getting_id(self.appid))

  def test_get_xg_path(self):
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    flexmock(zk.ZKTransaction)

    zookeeper.should_receive('init').and_return(self.handle)
 
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
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('get_transaction_path') \
      .and_return('/transaction/path')

    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

    # test when the transaction is running
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    zookeeper.should_receive('exists').and_return(True)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.is_in_transaction(self.appid, 1))

    # and when it's not
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    zookeeper.should_receive('exists').and_return(False)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(False, transaction.is_in_transaction(self.appid, 1))

    # and when it's blacklisted
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(True)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException, transaction.is_in_transaction,
      self.appid, 1)

  def test_acquire_lock(self):
    # mock out waitForConnect
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('get_lock_root_path').\
       and_return('/lock/root/path')
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').\
       and_return('/rootpath/' + self.appid)
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

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
    zookeeper.should_receive('get').and_return(['/lock/root/path'])

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_lock(self.appid, "txid",
      "somekey"))

    # next, test when we're in a non-XG transaction and we're not in the lock
    # root path
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(True)
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
       and_return('/rootpath/' + self.appid + "/tx1")
    zookeeper.should_receive('get').and_return(['/lock/root/path2'])
    zk.ZKTransaction.should_receive('is_xg').and_return(False)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException, transaction.acquire_lock, 
      self.appid, "txid", "somekey")

    # next, test when we're in a XG transaction and we're not in the lock
    # root path
    zk.ZKTransaction.should_receive('is_in_transaction').and_return(True)
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
       and_return('/rootpath/' + self.appid + "/tx1")
    zookeeper.should_receive('get').and_return(['/lock/root/path2'])
    zk.ZKTransaction.should_receive('is_xg').and_return(True)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_lock(self.appid, "txid",
      "somekey"))


  def test_acquire_additional_lock(self):
    # mock out waitForConnect
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('check_transaction')
    zk.ZKTransaction.should_receive('get_transaction_path').\
       and_return('/txn/path')
    zk.ZKTransaction.should_receive('get_lock_root_path').\
       and_return('/lock/root/path')
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').\
       and_return('/rootpath/' + self.appid)
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('create').and_return("/some/lock/path")
    zookeeper.should_receive('acreate')
    lock_list = ['path1', 'path2', 'path3'] 
    lock_list_str = zk.LOCK_LIST_SEPARATOR.join(lock_list)
    zookeeper.should_receive('get').and_return([lock_list_str])
    zookeeper.should_receive('aset')

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.acquire_additional_lock(self.appid,
      "txid", "somekey", False))
  
    # Test for when we want to create a new ZK node for the lock path
    self.assertEquals(True, transaction.acquire_additional_lock(self.appid,
      "txid", "somekey", True))

    # Test for existing max groups 
    lock_list = ['path1', 'path2', 'path3', 'path4', 'path5'] 
    lock_list_str = zk.LOCK_LIST_SEPARATOR.join(lock_list)
    zookeeper.should_receive('get').and_return([lock_list_str])
    zookeeper.should_receive('aset')

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException,
      transaction.acquire_additional_lock, self.appid, "txid", "somekey", False)

    # Test for when there is a node which already exists.
    zookeeper.should_receive('create').and_raise(zookeeper.NodeExistsException)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertRaises(zk.ZKTransactionException,
      transaction.acquire_additional_lock, self.appid, "txid", "somekey", False)


  def test_check_transaction(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('get_transaction_prefix_path').with_args(
      self.appid).and_return('/rootpath')
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.check_transaction(self.appid, 1))

    # Check to make sure it raises exception for blacklisted transactions.
    zk.ZKTransaction.should_receive('is_blacklisted').and_return(True)
    self.assertRaises(zk.ZKTransactionException, transaction.check_transaction,
      self.appid, 1)

    zk.ZKTransaction.should_receive('is_blacklisted').and_return(False)
    zookeeper.should_receive('exists').and_return(False)
    self.assertRaises(zk.ZKTransactionException, transaction.check_transaction,
      self.appid, 1)
  
  def test_is_xg(self):
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.is_xg(self.appid, 1))

  def test_release_lock(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('check_transaction')
    zk.ZKTransaction.should_receive('get_transaction_path').\
      and_return('/rootpath')
    zk.ZKTransaction.should_receive('get_transaction_lock_list_path').\
      and_return('/rootpath')
    zk.ZKTransaction.should_receive('is_xg').and_return(False)

    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)
    zookeeper.should_receive('get').and_return(['/1/2/3'])
    zookeeper.should_receive('adelete')
    zookeeper.should_receive('delete')
    zookeeper.should_receive('get_children').and_return(['1','2'])

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.release_lock(self.appid, 1))

    zk.ZKTransaction.should_receive('is_xg').and_return(True)
    self.assertEquals(True, transaction.release_lock(self.appid, 1))

    # Check to make sure it raises exception for blacklisted transactions.
    zk.ZKTransaction.should_receive('is_xg').and_return(False)
    zookeeper.should_receive('get').and_raise(zookeeper.NoNodeException)
    self.assertRaises(zk.ZKTransactionException, transaction.release_lock,
      self.appid, 1)


  def test_is_blacklisted(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('force_create_path')
    zk.ZKTransaction.should_receive('get_blacklist_root_path').\
      and_return("bl_root_path")

    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)
    zookeeper.should_receive('get_children').and_return(['1','2'])

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    transaction.blacklist_cache[self.appid] = str(1)
    self.assertEquals(True, transaction.is_blacklisted(self.appid, 1))

    del transaction.blacklist_cache[self.appid]
    self.assertEquals(True, transaction.is_blacklisted(self.appid, 1))

    del transaction.blacklist_cache[self.appid]
    zookeeper.should_receive('get_children').\
      and_raise(zookeeper.NoNodeException)
    self.assertEquals(False, transaction.is_blacklisted(self.appid, 1))

  def test_register_updated_key(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('get_valid_transaction_path').\
      and_return('/txn/path')
    zk.ZKTransaction.should_receive('get_transaction_path').\
      and_return('/txn/path')

    zk.ZKTransaction.should_receive('get_blacklist_root_path').\
      and_return("bl_root_path")

    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)
    zookeeper.should_receive('acreate')
    zookeeper.should_receive('aset')

    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(True, transaction.register_updated_key(self.appid, 
      "1", "2", "somekey"))

    zookeeper.should_receive('exists').and_return(False)
    self.assertRaises(ZKTransactionException, 
      transaction.register_updated_key, self.appid, "1", "2", "somekey")

  def test_try_garbage_collection(self):
    # mock out getTransactionRootPath
    flexmock(zk.ZKTransaction)
    zk.ZKTransaction.should_receive('wait_for_connect')
    zk.ZKTransaction.should_receive('update_node')

    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)
    zookeeper.should_receive('exists').and_return(True)
    zookeeper.should_receive('get').and_return([str(time.time() + 10000)])
    zookeeper.should_receive('get_children').and_return(['1','2','3'])
    zookeeper.should_receive('create')
    zookeeper.should_receive('delete')

    # Put the last time we ran GC way into the future.
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(False, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # Make it so we recently ran the GC
    zookeeper.should_receive('get').and_return([str(time.time())])
    self.assertEquals(False, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # Make it so we ran the GC a long time ago.
    zookeeper.should_receive('get').and_return([str(time.time() - 1000)])
    self.assertEquals(True, transaction.try_garbage_collection(self.appid, 
      "/some/path"))

    # No node means we have not run the GC before, so run it.
    zookeeper.should_receive('get').and_raise(zookeeper.NoNodeException)
    self.assertEquals(True, transaction.try_garbage_collection(self.appid, 
      "/some/path"))
     

  def test_execute_garbage_collection(self):
    pass

if __name__ == "__main__":
  unittest.main()    
