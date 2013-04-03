import sys
import time
import unittest
import base64
import re
import threading
from test import test_support
from dbconstants import *
import zkappscale.zktransaction

class TestZKTransaction(unittest.TestCase):

  def test_getTransactionId(self):
    app = "testapp"
    id = self.zk.get_transaction_id(app)
    self.assertTrue(id > 0)

  def test_locksimple(self):
    app = "testapp"
    key = "root"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_lockpathkey(self):
    app = "testapp"
    key = "/root/child"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_lockspecialcharapp(self):
    app = "!@#$%^&*()-=_+[]{}\\|~`;:\"',.<>/?"
    key = "!@#$%^&*()-=_+[]{}\\|~`;:\"',.<>/?"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_locklongkey(self):
    app = "testapp"
    key = "/root/child/looooooooooooooooooooooooooooooooooooooong"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_locktwice(self):
    app = "testapp"
    key = "root"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_lockdifferentkey(self):
    app = "testapp"
    key = "root"
    key2 = "root2"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    try:
      ret = self.zk.acquire_lock(app, txid, key2)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_DIFFERENT_ROOTKEY, e.getType())
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def test_lockafterrelease(self):
    app = "testapp"
    key = "root"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)
    try:
      ret = self.zk.acquire_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_INVALID, e.getType())

  def test_lockinvalidid(self):
    app = "testapp"
    key = "root"
    txid = 99999L
    try:
      self.zk.acquire_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_INVALID, e.getType())

  def test_lock1000(self):
    app = "testapp"
    key = "root"
    for ii in range(1,1000):
      txid = self.zk.get_transaction_id(app)
      self.assertTrue(txid > 0)
      ret = self.zk.acquire_lock(app, txid, key)
      self.assertTrue(ret)
      ret = self.zk.release_lock(app, txid)
      self.assertTrue(ret)

  def test_releaseinvalidid(self):
    app = "testapp"
    key = "root"
    txid = 99999L
    try:
      self.zk.release_lock(app, txid)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_INVALID, e.getType())

  def test_releasewithoutlock(self):
    app = "testapp"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.release_lock(app, txid)
    self.assertFalse(ret)

  def test_releasedifferentkey(self):
    app = "testapp"
    key = "root"
    key2 = "root2"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    try:
      ret = self.zk.release_lock(app, txid, key2)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_DIFFERENT_ROOTKEY, e.getType())
    ret = self.zk.release_lock(app, txid, key)
    self.assertTrue(ret)

  def test_generateid(self):
    app = "testapp"
    key = "root"
    (id, block) = self.zk.generateIDBlock(app, key)
    print "id=%d, block=%d" % (id, block)
    self.assertTrue(id >= 0)
    self.assertTrue(block > 0)

  def test_generateid_pathkey(self):
    app = "testapp"
    key = "/root/child"
    (id, block) = self.zk.generateIDBlock(app, key)
    print "id=%d, block=%d" % (id, block)
    self.assertTrue(id >= 0)
    self.assertTrue(block > 0)

  def test_generateid_specialcharacterkey(self):
    app = "testapp"
    key = "!@#$%^&*()-=_+[]{}\\|~`;:\"',.<>/?"
    (id, block) = self.zk.generateIDBlock(app, key)
    print "id=%d, block=%d" % (id, block)
    self.assertTrue(id >= 0)
    self.assertTrue(block > 0)

  def test_generateid_twoblocks(self):
    app = "testapp"
    key = "root"
    (id, block) = self.zk.generateIDBlock(app, key)
    print "id=%d, block=%d" % (id, block)
    self.assertTrue(id >= 0)
    self.assertTrue(block > 0)
    (nextid, block) = self.zk.generateIDBlock(app, key)
    print "id=%d, block=%d" % (nextid, block)
    self.assertTrue(nextid >= 0)
    self.assertTrue(nextid > id)
    self.assertTrue(block > 0)

  def test_lockmultithread(self):
    self.valueA = 10
    tlist = []
    for i in range(5):
      thread = threading.Thread(target = self.__increaseA)
      thread.start()
      tlist.append(thread)
      thread = threading.Thread(target = self.__decreaseA)
      thread.start()
      tlist.append(thread)

    for t in tlist:
      t.join()

    self.assertEqual(10, self.valueA)

  def test_lockmultithread_differentkeys(self):
    self.valueA = 10
    self.valueB = 10
    tlist = []
    for i in range(5):
      thread = threading.Thread(target = self.__increaseA)
      thread.start()
      tlist.append(thread)
      thread = threading.Thread(target = self.__decreaseA)
      thread.start()
      tlist.append(thread)

    for i in range(5):
      thread = threading.Thread(target = self.__increaseB)
      thread.start()
      tlist.append(thread)
      thread = threading.Thread(target = self.__decreaseB)
      thread.start()
      tlist.append(thread)

    for t in tlist:
      t.join()

    self.assertEqual(10, self.valueA)
    self.assertEqual(10, self.valueB)

  def __increaseA(self):
    app = "testapp"
    key = "roota"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    while not self.zk.acquire_lock(app, txid, key):
      time.sleep(0.1)
    print "start increaseA %s" % threading.currentThread()
    tmp = self.valueA
    # make conflict between threads.
    time.sleep(0.5)
    self.valueA = tmp + 1
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def __increaseB(self):
    app = "testapp"
    key = "rootb"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    while not self.zk.acquire_lock(app, txid, key):
      time.sleep(0.1)
    print "start increaseB %s" % threading.currentThread()
    tmp = self.valueB
    # make conflict between threads.
#        time.sleep(0.5)
    self.valueB = tmp + 1
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def __decreaseA(self):
    app = "testapp"
    key = "roota"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    while not self.zk.acquire_lock(app, txid, key):
      time.sleep(0.1)
    print "start decreaseA %s" % threading.currentThread()
    tmp = self.valueA
    # make conflict between threads.
    time.sleep(0.5)
    self.valueA = tmp - 1
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def __decreaseB(self):
    app = "testapp"
    key = "rootb"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    while not self.zk.acquire_lock(app, txid, key):
      time.sleep(0.1)
    print "start decreaseB %s" % threading.currentThread()
    tmp = self.valueB
    # make conflict between threads.
#        time.sleep(0.5)
    self.valueB = tmp - 1
    ret = self.zk.release_lock(app, txid)
    self.assertTrue(ret)

  def __lockonlyB(self):
    app = "testapp"
    key = "rootb"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    while not self.zk.acquire_lock(app, txid, key):
      time.sleep(0.1)

  def test_gcsimple(self):
    # timeout very fast
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 1
    zkappscale.zktransaction.GC_INTERVAL = 1
#    self.zk.setRollbackFunction(self.__rollbackReceiver)
    # restart gc thread
    self.keylist = None
    self.zk.startGC()

    app = "testapp"
    key = "gctestkey"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    # wait for gc
    time.sleep(5)
    self.assertTrue(self.zk.is_blacklisted(app, txid))
    try:
      self.zk.release_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_EXPIRED, e.getType())
    try:
      self.zk.acquire_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_EXPIRED, e.getType())

#    self.assertEqual(txid, self.txid)
#    self.assertEqual(key, self.rootkey)
#    self.assertEqual([], self.keylist)

    # revert settings
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 30
    zkappscale.zktransaction.GC_INTERVAL = 30
#    self.zk.setRollbackFunction(None)
    self.zk.startGC()

  def test_gcwithkeylist(self):
    # timeout very fast
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 1
    zkappscale.zktransaction.GC_INTERVAL = 1
#    self.zk.setRollbackFunction(self.__rollbackReceiver)
    # restart gc thread
    self.keylist = None
    self.zk.startGC()

    app = "testapp"
    key = "gctestkey"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    vid = 100L
    self.zk.register_updated_key(app, txid, vid, key + "/a")
    # wait for gc
    time.sleep(5)
    self.assertTrue(self.zk.is_blacklisted(app, txid))
    try:
      self.zk.release_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_EXPIRED, e.getType())
    try:
      self.zk.acquire_lock(app, txid, key)
      self.fail()
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_EXPIRED, e.getType())

#    self.assertEqual(app, self.app_id)
#    self.assertEqual(txid, self.txid)
#    self.assertEqual(key, self.rootkey)
#    self.assertTrue(self.keylist.index("a") >= 0)
#    self.assertTrue(self.keylist.index("b") >= 0)

    # revert settings
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 30
    zkappscale.zktransaction.GC_INTERVAL = 30
#    self.zk.setRollbackFunction(None)
    self.zk.startGC()

  def test_gcreleaselock(self):
    # timeout very fast
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 1
    zkappscale.zktransaction.GC_INTERVAL = 1
#    self.zk.setRollbackFunction(self.__rollbackReceiver)
    # restart gc thread
    self.keylist = None
    self.zk.startGC()

    self.valueB = 1

    tlock = threading.Thread(target = self.__lockonlyB)
    tlock.start()
    time.sleep(1.5)

    # this will be executed after gc
    tincrease = threading.Thread(target = self.__increaseB)
    tincrease.start()

    tlock.join()
    tincrease.join()

    self.assertEqual(2, self.valueB)

    # revert settings
#    self.zk.stopGC()
    zkappscale.zktransaction.TX_TIMEOUT = 30
    zkappscale.zktransaction.GC_INTERVAL = 30
#    self.zk.setRollbackFunction(None)
    self.zk.startGC()

  def __rollbackReceiver(self, app_id, txid, rootkey, keylist):
    print "rollback called. app=%s, txid=%s, rootkey=%s, keylist=%s" % (app_id, txid, rootkey, keylist)
    self.app_id = app_id
    self.txid = txid
    self.rootkey = rootkey
    self.keylist = keylist

  def test_rollback(self):
    app = "testapp"
    key = "root"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    ret = self.zk.notify_failed_transaction(app, txid)
    self.assertTrue(ret)
    self.assertTrue(self.zk.is_blacklisted(app, txid))
    try:
      ret = self.zk.release_lock(app, txid)
      self.fail
    except zkappscale.zktransaction.ZKTransactionException as e:
      print e
      self.assertEqual(zkappscale.zktransaction.ZKTransactionException.TYPE_EXPIRED, e.getType())

  def test_updateafterrollback(self):
    app = "testapp"
    key = "root"
    txid = self.zk.get_transaction_id(app)
    self.assertTrue(txid > 0)
    ret = self.zk.acquire_lock(app, txid, key)
    self.assertTrue(ret)
    vid = 0L
    self.zk.register_updated_key(app, txid, vid, key + "/a")
    ret = self.zk.notify_failed_transaction(app, txid)
    self.assertTrue(ret)
    self.assertTrue(self.zk.is_blacklisted(app, txid))

    # update value after rollback
    txid2 = self.zk.get_transaction_id(app)
    self.assertTrue(txid2 > 0)
    ret = self.zk.acquire_lock(app, txid2, key)
    self.assertTrue(ret)
    # get previous valid id
    ret = self.zk.get_valid_transaction_id(app, txid, key + "/a")
    self.assertEqual(vid, ret)
    # update previous valid id
    vid = 100L
    self.zk.register_updated_key(app, txid2, vid, key + "/a")
    # try to get updated previous valid id
    ret = self.zk.get_valid_transaction_id(app, txid, key + "/a")
    self.assertEqual(vid, ret)
    self.assertTrue(self.zk.release_lock(app, txid2))

  def setUp(self):
    global zkconnection
    self.zk = zkconnection

  def tearDown(self):
    # for debug
    self.zk.dump_tree("/appscale/apps")

if __name__ == "__main__":
  global zkconnection
  zkconnection = zkappscale.zktransaction.ZKTransaction()
  if len(sys.argv) > 1 and sys.argv[1] == "dump":
    zkconnection.dump_tree("/appscale")
  else:
    zkconnection.deleteRecursive("/appscale/apps")
    test_support.run_unittest(TestZKTransaction)
  zkconnection.close()
