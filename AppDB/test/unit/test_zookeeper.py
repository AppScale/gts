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
    zk.ZKTransaction.should_receive('get_transaction_root_path').with_args(
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
    zk.ZKTransaction.should_receive('get_transaction_root_path').with_args(
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
    zk.ZKTransaction.should_receive('get_transaction_root_path').with_args(
      self.appid).and_return('/rootpath/' + self.appid)
    
    # mock out time.time
    flexmock(time)
    time.should_receive('time').and_return('now')
    
    # mock out initializing a ZK connection
    flexmock(zookeeper)
    zookeeper.should_receive('init').and_return(self.handle)

    # mock out making the txn id
    path_to_create = "/rootpath/" + self.appid + "/" + zk.APP_TX_PREFIX
    zk.ZKTransaction.should_receive('create_sequence_node').with_args(
      path_to_create, 'now').and_return(1)

    # mock out zookeeper.create for is_xg
    xg_path = path_to_create + "/1/" + zk.XG_PREFIX
    zk.ZKTransaction.should_receive('create_node').with_args(xg_path, 'now')

    # assert, make sure we got back our id
    transaction = zk.ZKTransaction(host="something", start_gc=False)
    self.assertEquals(1, transaction.get_transaction_id(self.appid, is_xg=True))


if __name__ == "__main__":
  unittest.main()    
