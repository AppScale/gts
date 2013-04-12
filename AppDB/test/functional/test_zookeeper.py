#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>
""" This is a top level test for ZooKeeper. ZooKeeper must be running. """

import os
import sys
import unittest

import kazoo.client
import kazoo.exceptions
import kazoo.protocol
import kazoo.protocol.states

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
from zkappscale import zktransaction as zk

PATH_SEPARATOR = "/"
TOP_LEVEL = "/appscale/apps/appid"

class TestZookeeperTransaction(unittest.TestCase):
  """ Functional test for ZK interface.
  """
  def setUp(self):
    self.appid = 'appid'

  def test_successful_transaction(self):
    zoo = zk.ZKTransaction()
    txid = zoo.get_transaction_id(self.appid, is_xg=False)
    zoo.acquire_lock(self.appid, txid, "__allocate__") 
    self.assertEquals(True, zoo.release_lock(self.appid, txid))

  def test_two_locks_transaction(self):
    zoo = zk.ZKTransaction()
    txid = zoo.get_transaction_id(self.appid, is_xg=False)
    zoo.acquire_lock(self.appid, txid, "__lock_one__") 
    self.assertRaises(zk.ZKTransactionException, zoo.acquire_lock,
      self.appid, txid, "__lock_two__") 

  def test_no_lock_transaction(self):
    zoo = zk.ZKTransaction()
    txid = zoo.get_transaction_id(self.appid, is_xg=False)
    self.assertEquals(True, zoo.release_lock(self.appid, txid))

  def test_no_lock_with_notify_failed_transaction(self):
    zoo = zk.ZKTransaction()
    txid = zoo.get_transaction_id(self.appid, is_xg=False)
    zoo.notify_failed_transaction(self.appid, txid)
    self.assertRaises(zk.ZKTransactionException, zoo.release_lock, self.appid, txid)

  def test_xg_successful_transaction(self):
    zoo = zk.ZKTransaction()

    txid = zoo.get_transaction_id(self.appid, is_xg=True)

    zoo.acquire_lock(self.appid, txid, "__allocate1__") 
    zoo.acquire_lock(self.appid, txid, "__allocate2__") 
    zoo.acquire_lock(self.appid, txid, "__allocate3__") 

    self.assertEquals(True, zoo.release_lock(self.appid, txid))

  def test_xg_failed_transaction(self):
    zoo = zk.ZKTransaction()

    txid = zoo.get_transaction_id(self.appid, is_xg=True)

    zoo.acquire_lock(self.appid, txid, "__allocate4__") 
    zoo.acquire_lock(self.appid, txid, "__allocate5__") 
    zoo.acquire_lock(self.appid, txid, "__allocate6__") 
    zoo.acquire_lock(self.appid, txid, "__allocate7__") 
    zoo.acquire_lock(self.appid, txid, "__allocate8__") 

    self.assertRaises(zk.ZKTransactionException, zoo.acquire_lock,
      self.appid, txid, "__allocate9__") 
  
  def test_versions_on_success(self):
    zoo = zk.ZKTransaction()

    txid = zoo.get_transaction_id(self.appid, is_xg=True)

    zoo.acquire_lock(self.appid, txid, "__allocate9__") 
    zoo.acquire_lock(self.appid, txid, "__allocate10__") 

    current_id_1 = zoo.get_valid_transaction_id(self.appid, txid, "__allocate9__/key")
    current_id_2 = zoo.get_valid_transaction_id(self.appid, txid, "__allocate10__/key")

    zoo.register_updated_key(self.appid, current_id_1, txid, "__allocate9__/key")
    zoo.register_updated_key(self.appid, current_id_2, txid, "__allocate10__/key")

    self.assertEquals(txid, zoo.get_valid_transaction_id(self.appid, txid, "__allocate9__/key"))
    self.assertEquals(txid, zoo.get_valid_transaction_id(self.appid, txid, "__allocate10__/key"))

    self.assertEquals(True, zoo.release_lock(self.appid, txid))

  def test_versions_on_failure(self):
    zoo = zk.ZKTransaction()

    txid = zoo.get_transaction_id(self.appid, is_xg=True)

    zoo.acquire_lock(self.appid, txid, "__allocate11__") 
    zoo.acquire_lock(self.appid, txid, "__allocate12__") 

    current_id_1 = zoo.get_valid_transaction_id(self.appid, txid, "__allocate11__/key")
    current_id_2 = zoo.get_valid_transaction_id(self.appid, txid, "__allocate12__/key")

    zoo.register_updated_key(self.appid, current_id_1, txid, "__allocate11__/key")
    zoo.register_updated_key(self.appid, current_id_2, txid, "__allocate12__/key")

    zoo.notify_failed_transaction(self.appid, txid)

    self.assertEquals(current_id_1, 
      zoo.get_valid_transaction_id(self.appid, txid, "__allocate11__/key"))
    self.assertEquals(current_id_2, 
      zoo.get_valid_transaction_id(self.appid, txid, "__allocate12__/key"))

    self.assertRaises(zk.ZKTransactionException, zoo.release_lock, self.appid, txid)

  def tearDown(self):
    def delete_recursive(handle, path):
      try:
        children = handle.get_children(path)
        for child in children:
          delete_recursive(handle, PATH_SEPARATOR.join([path, child]))
        handle.delete(path)
      except kazoo.exceptions.NoNodeError:
        pass

    handle = kazoo.client.KazooClient(hosts="localhost:2181")
    delete_recursive(handle, TOP_LEVEL)
 
if __name__ == "__main__":
  unittest.main()    
