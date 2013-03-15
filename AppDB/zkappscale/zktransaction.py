#!/usr/bin/python
#
# Distributed id and lock service for transaction support.
# Written by Yoshi <nomura@pobox.com>

import zookeeper
import threading
import time
import urllib
import re
import traceback
from dbconstants import *

ZOO_ACL_OPEN = [{"perms":0x1f, "scheme":"world", "id" :"anyone"}]
LOCK_TIMEOUT = 30 # seconds
TX_TIMEOUT = 30 # seconds
GC_INTERVAL = 30 # seconds
ID_BLOCK = 10
DEFAULT_HOST = "localhost:2181"
GLOBAL_LOCK_KEY = "__global__"
GLOBAL_ID_KEY = "__global__"
PATH_SEPARATOR = "/"
APPS_PATH = "/appscale/apps"
APP_TX_PATH = "txids"
APP_LOCK_PATH = "locks"
APP_ID_PATH = "ids"
APP_TX_PREFIX = "tx"
APP_LOCK_PREFIX = "lk"
APP_ID_PREFIX = "id"
TX_LOCK_PATH = "lockpath"
TX_BLACKLIST_PATH = "blacklist"
TX_VALIDLIST_PATH = "validlist"
TX_UPDATEDKEY_PREFIX = "ukey"
GC_LOCK_PATH = "gclock"
GC_TIME_PATH = "gclasttime"
XG_PREFIX = "xg"

USE_BLOOMFILTER = False

# This class take care of transaction id, lock and GC of transaction

class ZKTransactionException(Exception):
  TYPE_UNKNOWN = 0
  TYPE_NO_CONNECTION = 1
  TYPE_INVALID = 2
  TYPE_EXPIRED = 3
  TYPE_DIFFERENT_ROOTKEY = 4
  TYPE_CONCURRENT = 5

  def __init__(self, type, message):
    Exception.__init__(self, message)
    self.type = type

  def getType(self):
    return self.type

class ZKTransaction:
  STATE_REGISTERED = 0
  STATE_MODIFIED = 1
  STATE_FAILED = 2
  STATE_DONE = 3

  # The number of times we should retry ZooKeeper operations, by default.
  DEFAULT_NUM_RETRIES = 5

  def __init__(self, host = DEFAULT_HOST, startgc = True):
    # for the connection
    self.connectcv = threading.Condition()
    self.connected = False
    self.handle = zookeeper.init(host, self.__receiveNotify)
    # for blacklist cache
    self.blacklistcv = threading.Condition()
    self.blacklistcache = {}
    # for gc
    self.gcrunning = False
    self.gccv = threading.Condition()
    if startgc:
      self.startGC()

  def startGC(self):
    """ Start GC thread.

    If it already started, GC thread will read new settings from
    constants.
    """
    with self.gccv:
      if not self.gcrunning:
        # start gc thread
        self.gcrunning = True
        self.gcthread = threading.Thread(target = self.__gcRunner)
        self.gcthread.start()
      else:
        # just notify
        self.gccv.notifyAll()

  def stopGC(self):
    """ Stop GC thread.
    """
    if self.gcrunning:
      with self.gccv:
        self.gcrunning = False
        self.gccv.notifyAll()
      self.gcthread.join()

  def close(self):
    """ Stop GC and close connection.
    """
    self.stopGC()
    zookeeper.close(self.handle)

  def __receiveNotify(self, handle, type, state, path):
#    print "notify type:%s, state:%s, path:%s" % (type, state, path)
    if type == zookeeper.SESSION_EVENT:
      if state == zookeeper.CONNECTED_STATE:
        # connected
        with self.connectcv:
          self.connected = True
          self.connectcv.notifyAll()
      else:
        # disconnected
        with self.connectcv:
          self.connected = False
          self.connectcv.notifyAll()

    elif type == zookeeper.CHILD_EVENT:
      pathlist = path.split(PATH_SEPARATOR)
      if pathlist[-1] == TX_BLACKLIST_PATH:
        # update blacklist cache
        appid = urllib.unquote_plus(pathlist[-3])
        try:
          blist = zookeeper.get_children(self.handle, path, self.__receiveNotify)
#          print "update blacklist: ",blist
          with self.blacklistcv:
            self.blacklistcache[appid] = set(blist)
        except zookeeper.NoNodeException:
          if appid in self.blacklistcache:
            with self.blacklistcv:
              del self.blacklistcache[appid]

# for bloom filter
#    elif type == zookeeper.CHANGED_EVENT:


  def wait_for_connect(self):
    if self.connected:
      return
#    if not self.handle:
#      raise ZKTransactionException(ZKTransactionException.TYPE_NO_CONNECTION, "There is no connection.")
    # wait until connected
    with self.connectcv:
      while not self.connected:
        self.connectcv.wait(10.0)

  def __forceCreatePath(self, path, value="default"):
    """ Try to create path first.

    If the parent doesn't exists, this method will try to create it.
    """
    self.wait_for_connect()
    retry = True
    while retry:
      retry = False
      try:
        zookeeper.create(self.handle, path, str(value), ZOO_ACL_OPEN, NODE_TYPE)
      except zookeeper.NoNodeException:
        retry = self.__forceCreatePath(PATH_SEPARATOR.join(path.split(PATH_SEPARATOR)[:-1]), value)
      except zookeeper.NodeExistsException:
        # just update value
        zookeeper.aset(self.handle, path, str(value))
      except Exception as e:
        print "warning: create error %s" % e
        return False
    return True

  def __updateNode(self, path, value):
    """ Try to update path first.

    If the path doesn't exists, this method will try to create it.
    """
    self.wait_for_connect()
    try:
      zookeeper.set(self.handle, path, value)
    except zookeeper.NoNodeException:
      self.__forceCreatePath(path, value)

  def deleteRecursive(self, path):
    self.wait_for_connect()
    try:
      children = zookeeper.get_children(self.handle, path)
      for child in children:
        self.deleteRecursive(PATH_SEPARATOR.join([path, child]))
      zookeeper.delete(self.handle, path, -1)
    except zookeeper.NoNodeException:
      pass

  def dumpTree(self, path):
    self.wait_for_connect()
    try:
      value = zookeeper.get(self.handle, path, None)[0]
      print "%s = \"%s\"" % (path, value)
      children = zookeeper.get_children(self.handle, path)
      for child in children:
        self.dumpTree(PATH_SEPARATOR.join([path, child]))
    except zookeeper.NoNodeException:
      print "%s is not exist." % path

  def __getAppRootPath(self, app_id):
    return PATH_SEPARATOR.join([APPS_PATH, urllib.quote_plus(app_id)])

  def get_transaction_root_path(self, app_id):
    return PATH_SEPARATOR.join([self.__getAppRootPath(app_id), APP_TX_PATH])

  def __getTransactionPath(self, app_id, txid):
    txstr = APP_TX_PREFIX + "%010d" % txid
    return PATH_SEPARATOR.join([self.__getAppRootPath(app_id), APP_TX_PATH, txstr])

  def __getBlacklistRootPath(self, app_id):
    return PATH_SEPARATOR.join([self.get_transaction_root_path(app_id), TX_BLACKLIST_PATH])

  def __getValidTransactionRootPath(self, app_id):
    return PATH_SEPARATOR.join([self.get_transaction_root_path(app_id), TX_VALIDLIST_PATH])

  def __getValidTransactionPath(self, app_id, entity_key):
    return PATH_SEPARATOR.join([self.__getValidTransactionRootPath(app_id), urllib.quote_plus(entity_key)])

  def __getLockRootPath(self, app_id, key):
    return PATH_SEPARATOR.join([self.__getAppRootPath(app_id), APP_LOCK_PATH, urllib.quote_plus(key)])

  def __getIDRootPath(self, app_id, key):
    return PATH_SEPARATOR.join([self.__getAppRootPath(app_id), APP_ID_PATH, urllib.quote_plus(key)])


  def create_node(self, path, value):
    """ Creates a new node in ZooKeeper, with the given value.

    Args:
      path: The path to create the node at.
      value: The value that we should store in the node.
    Returns:
      A str that ??    
    Raises:
      ZKTransactionException: If the sequence node couldn't be created.
    """
    retries_left = self.DEFAULT_NUM_RETRIES
    while retries_left > 0:
      try:
        path = zookeeper.create(self.handle, 
                                path,
                                value, 
                                ZOO_ACL_OPEN)
        if path:
          txn_id = long(path.split(PATH_SEPARATOR)[-1].lstrip(APP_TX_PREFIX))
          if txn_id == 0:
            # ID 0 is reserved for callers without IDs pre-set, so don't use that
            # sentinel value for our IDs.
            zookeeper.adelete(self.handle, path)
          else:
            return txn_id
      except zookeeper.NoNodeException:
        self.__forceCreatePath(rootpath)
      finally:
        retries_left -= 1
    
    raise ZKTransactionException("Unable to create sequence node with path" \
      " {0}, value {1}".format(path, value))


  def create_sequence_node(self, path, value):
    """ Creates a new sequence node in ZooKeeper, with a non-zero initial ID.

    Args:
      path: The path to create the sequence node at.
      value: The value that we should store in the sequence node.
    Returns:
      A long that represents the sequence ID.    
    Raises:
      ZKTransactionException: If the sequence node couldn't be created.
    """
    retries_left = self.DEFAULT_NUM_RETRIES
    while retries_left > 0:
      try:
        txn_id_path = zookeeper.create(self.handle, 
                                path,
                                value, 
                                ZOO_ACL_OPEN, 
                                zookeeper.SEQUENCE)
        if txn_id_path:
          txn_id = long(txn_id_path.split(PATH_SEPARATOR)[-1].lstrip(APP_TX_PREFIX))
          if txn_id == 0:
            # ID 0 is reserved for callers without IDs pre-set, so don't use that
            # sentinel value for our IDs.
            zookeeper.adelete(self.handle, txn_id_path)
          else:
            return txn_id
      except zookeeper.NoNodeException:
        self.__forceCreatePath(rootpath)
      finally:
        retries_left -= 1
    
    raise ZKTransactionException("Unable to create sequence node with path" \
      " {0}, value {1}".format(path, value))


  def get_transaction_id(self, app_id, is_xg):
    """Acquires a new id for an upcoming transaction.

    Note that the caller must lock particular root entities using acquireLock,
    and that the transaction ID expires after a constant amount of time.

    Args:
      app_id: A str representing the application we want to perform a
        transaction on.
      is_xg: A bool that indicates if this transaction operates across multiple
        entity groups.

    Returns:
      A long that represents the new transaction ID.
    """
    self.wait_for_connect()
    rootpath = self.get_transaction_root_path(app_id)
    value = str(time.time())
    txn_id = -1
    retry = True
    # First, make the ZK node for the actual transaction id.
    # TODO(cgb): Make functions to generate the paths.
    app_path = PATH_SEPARATOR.join([rootpath, APP_TX_PREFIX])
    txn_id = self.create_sequence_node(app_path, value)

    # Next, make the ZK node that indicates if this a XG transaction.
    if is_xg:
      self.create_node(PATH_SEPARATOR.join([app_path, str(txn_id), XG_PREFIX]), value)

    return txn_id

  def checkTransaction(self, app_id, txid):
    """ Get status of specified transaction.

    Returns: True - If transaction is alive.
    Raises: ZKTransactionException - If transaction is timeout or not exist.
    """
    self.wait_for_connect()
    txpath = self.__getTransactionPath(app_id, txid)
    if self.isBlacklisted(app_id, txid):
      raise ZKTransactionException(ZKTransactionException.TYPE_EXPIRED, 
            "zktransaction.checkTransaction: Transaction %d is timeout." % txid)
    if not zookeeper.exists(self.handle, txpath):
      raise ZKTransactionException(ZKTransactionException.TYPE_INVALID, 
            "zktransaction.checkTransaction: TransactionID %d is not valid." % txid)
    return True

  def acquireLock(self, app_id, txid, entity_key = GLOBAL_LOCK_KEY):
    """ Acquire lock for transaction.

    You must call get_transaction_id() first to obtain transaction ID.
    You could call this method anytime if the root entity key is same.
    Args:
      app_id: The application ID to acquire a lock for.
      txid: The transaction ID you are acquiring a lock for. Built into 
            the path. 
       entity_key: Used to get the root path.
    Raises:
      ZKTransactionException: If it could not get the lock.
    """
    self.wait_for_connect()
    txpath = self.__getTransactionPath(app_id, txid)
    lockrootpath = self.__getLockRootPath(app_id, entity_key)
    lockpath = None
    if zookeeper.exists(self.handle, PATH_SEPARATOR.join([txpath, TX_LOCK_PATH])):
      # use current lock
      prelockpath = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath, TX_LOCK_PATH]), None)[0]
      if not lockrootpath == prelockpath:
        raise ZKTransactionException(ZKTransactionException.TYPE_DIFFERENT_ROOTKEY, 
                                     "zktransaction.acquireLock: You can not lock different root entity in same transaction.")
      print "Already has lock: %s" % lockrootpath
      return True

    self.checkTransaction(app_id, txid)

    # create new lock
    retry = True
    while retry:
      retry = False
      try:
        lockpath = zookeeper.create(self.handle, lockrootpath, txpath, ZOO_ACL_OPEN)
      except zookeeper.NoNodeException:
        self.__forceCreatePath(PATH_SEPARATOR.join(lockrootpath.split(PATH_SEPARATOR)[:-1]))
        retry = True
      except zookeeper.NodeExistsException:
        # fail to get lock
        raise ZKTransactionException(ZKTransactionException.TYPE_CONCURRENT, 
                                     "zktransaction.acquireLock: There is already another transaction using this lock")

    # set lockpath for transaction node
    # TODO: we should think about atomic operation or recovery of
    #       inconsistent lockpath node.
    zookeeper.acreate(self.handle, PATH_SEPARATOR.join([txpath, TX_LOCK_PATH]),  lockpath, ZOO_ACL_OPEN)

    return True

  def getUpdatedKeyList(self, app_id, txid):
    """ Get the list of updated key.

    This method just return updated key list which is registered using
    registUpdatedKey().
    This method doesn't check transaction state, so
    you can use this method for rollback.
    """
    self.wait_for_connect()
    txpath = self.__getTransactionPath(app_id, txid)
    try:
      list = zookeeper.get_children(self.handle, txpath)
      keylist = []
      for item in list:
        if re.match("^" + TX_UPDATEDKEY_PREFIX, item):
          keyandtx = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath, item]), None)[0]
          key = urllib.unquote_plus(keyandtx.split(PATH_SEPARATOR)[0])
          keylist.append(key)
      return keylist
    except zookeeper.NoNodeException:
      raise ZKTransactionException(ZKTransactionException.TYPE_INVALID, 
                                  "zktransaction.getUpdatedKeyList: TransactionID %d is not valid." % txid)

  def releaseLock(self, app_id, txid, key = None):
    """ Release acquired lock.

    You must call acquireLock() first.
    if the transaction is not valid or it is expired, this raises Exception.
    After the release lock, you could not use transaction ID again.
    If there is no lock, this method returns False.
    Args:
      app_id: The application ID we are releasing a lock for.
      txid: The transaction ID we are releasing a lock for.
      key: The entity key we use to build the path.
    Returns:
      True on success.
    Raises:
      ZKTransactionException: When a lock can not be released. 
    """
    self.wait_for_connect()
    self.checkTransaction(app_id, txid)
    txpath = self.__getTransactionPath(app_id, txid)

    has_lock = False
    try:
      lockpath = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath, TX_LOCK_PATH]), None)[0]
      if key:
        lockroot = self.__getLockRootPath(app_id, key)
        if not lockroot == lockpath:
          raise ZKTransactionException(ZKTransactionException.TYPE_DIFFERENT_ROOTKEY, 
                               "zktransaction.releaseLock: You can not specify different root entity for release.")
      zookeeper.adelete(self.handle, lockpath)
      has_lock = True
    except zookeeper.NoNodeException:
      # there is no lock.
      pass
    # If the transaction doesn't have active lock or not, we should delete it.
    # delete transaction node
    for child in zookeeper.get_children(self.handle, txpath):
      zookeeper.adelete(self.handle, PATH_SEPARATOR.join([txpath, child]))
    zookeeper.adelete(self.handle, txpath)

    return has_lock

  def isBlacklisted(self, app_id, txid, entity_key = None):
    """ This validate transaction id with black list.

    The PB server logic should use getValidTransactionID().
    """
    self.wait_for_connect()
    if app_id in self.blacklistcache:
      with self.blacklistcv:
        return str(txid) in self.blacklistcache[app_id]
    else:
      broot = self.__getBlacklistRootPath(app_id)
      if not zookeeper.exists(self.handle, broot):
        self.__forceCreatePath(broot)
      try:
        blist = zookeeper.get_children(self.handle, broot, self.__receiveNotify)
        with self.blacklistcv:
          self.blacklistcache[app_id] = set(blist)
          return str(txid) in self.blacklistcache[app_id]
      except zookeeper.NoNodeException:
        # there is no blacklist
        return False

  def getValidTransactionID(self, app_id, target_txid, entity_key):
    """ This returns valid transaction id for the entity key.

    If the specified transaction id is black-listed,
    this returns latest valid transaction id.
    If there is no valid transaction id, this returns 0.
    """
    self.wait_for_connect()
    if not self.isBlacklisted(app_id, target_txid, entity_key):
      return target_txid
    # get the valid id
    vtxpath = self.__getValidTransactionPath(app_id, entity_key)
    try:
      vid = zookeeper.get(self.handle, vtxpath, None)[0]
      return long(vid)
    except zookeeper.NoNodeException:
      # The transaction is blacklisted, but there is no valid id.
      return long(0)

  def registUpdatedKey(self, app_id, current_txid, target_txid, entity_key):
    """ Regist valid transaction id for entity.

    target_txid must be the latest valid transaction id for the entity.
    """
    self.wait_for_connect()
    vtxpath = self.__getValidTransactionPath(app_id, entity_key)
    if zookeeper.exists(self.handle, vtxpath):
      # just update transaction id for entity if there is valid transaction node.
      zookeeper.aset(self.handle, vtxpath, str(target_txid))
    else:
      # store the updated key info into current transaction node.
      value = PATH_SEPARATOR.join([urllib.quote_plus(entity_key), str(target_txid)])
      txpath = self.__getTransactionPath(app_id, current_txid)
      if zookeeper.exists(self.handle, txpath):
        zookeeper.acreate(self.handle, PATH_SEPARATOR.join([txpath, TX_UPDATEDKEY_PREFIX]), value, ZOO_ACL_OPEN, zookeeper.SEQUENCE)
      else:
        raise ZKTransactionException(ZKTransactionException.TYPE_INVALID, "Transaction %d is not valid." % current_txid)

  def notifyFailedTransaction(self, app_id, txid):
    """ Notify failed transaction id.

    This method will add the transaction id into black list.
    After this call, the transaction becomes invalid.
    """
    self.wait_for_connect()
    self.checkTransaction(app_id, txid)
    print "notify failed transaction app:%s, txid:%d" % (app_id, txid)
    txpath = self.__getTransactionPath(app_id, txid)
    lockpath = None
    try:
      lockpath = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath, TX_LOCK_PATH]), None)[0]
    except zookeeper.NoNodeException:
      # there is no lock. it means there is no need to rollback.
      pass

    if lockpath:
      # add transacion id to black list.
      now = str(time.time())
      broot = self.__getBlacklistRootPath(app_id)
      if not zookeeper.exists(self.handle, broot):
        self.__forceCreatePath(broot)
      zookeeper.acreate(self.handle, PATH_SEPARATOR.join([broot, str(txid)]), now, ZOO_ACL_OPEN)
      # update local cache before notification
      if app_id in self.blacklistcache:
        with self.blacklistcv:
          self.blacklistcache[app_id].add(str(txid))
      # copy valid transaction id for each updated key into valid list.
      for child in zookeeper.get_children(self.handle, txpath):
        if re.match("^" + TX_UPDATEDKEY_PREFIX, child):
          value = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath, child]), None)[0]
          valuelist = value.split(PATH_SEPARATOR)
          key = urllib.unquote_plus(valuelist[0])
          vid = valuelist[1]
          vtxroot = self.__getValidTransactionRootPath(app_id)
          if not zookeeper.exists(self.handle, vtxroot):
            self.__forceCreatePath(vtxroot)
          vtxpath = self.__getValidTransactionPath(app_id, key)
          zookeeper.acreate(self.handle, vtxpath, vid, ZOO_ACL_OPEN)
      # release the lock
      try:
        zookeeper.adelete(self.handle, lockpath)
      except zookeeper.NoNodeException:
        # this should be retry.
        pass

    # just remove transaction node
    try:
      for item in zookeeper.get_children(self.handle, txpath):
        zookeeper.adelete(self.handle, PATH_SEPARATOR.join([txpath, item]))
      zookeeper.adelete(self.handle, txpath)
    except zookeeper.NoNodeException:
      # something wrong. next GC will take care of it.
      return False

    return True

     
  def generateIDBlock(self, app_id, entity_key = GLOBAL_ID_KEY):
    """ Generate ID block for specific key.

    This generates ID block that is unique in specified key.
    If the key doesn't specify, this generates global ID.
    This method returns long start ID and block length tuple.
    """
    self.wait_for_connect()
    idrootpath = self.__getIDRootPath(app_id, entity_key)
    path = PATH_SEPARATOR.join([idrootpath, APP_ID_PREFIX])
    value = entity_key
    start = -1
    retry = True
    while retry:
      retry = False
      try:
        idpath = zookeeper.create(self.handle, path, value, ZOO_ACL_OPEN, zookeeper.SEQUENCE)
        zookeeper.adelete(self.handle, idpath)
        idbase = long(idpath.split(PATH_SEPARATOR)[-1].lstrip(APP_ID_PREFIX))
        start = idbase * ID_BLOCK
#        self.__updateNode(PATH_SEPARATOR.join([idrootpath, APP_ID_PREID_PATH]), str(start))
        if start == 0:
          retry = True
      except zookeeper.NoNodeException:
        self.__forceCreatePath(idrootpath)
        retry = True
      except Exception, e:
        print e
        raise ZKTransactionException(ZKTransactionException.TYPE_UNKNOWN, "Fail to generate ID: %s" % e)

    return (start, ID_BLOCK)

  def __gcRunner(self):
    """ Transaction ID garbage collection runner.

    This must be running as separate thread.
    """
    print "Starting GC thread."
    while self.gcrunning:
      if self.connected:
        # scan each application's last gc time
        try:
          app_list = zookeeper.get_children(self.handle, APPS_PATH)
          for app in app_list:
            app_id = urllib.unquote_plus(app)
            # app is already encoded, so we should not use self.__getAppRootPath()
            app_path = PATH_SEPARATOR.join([APPS_PATH, app])
            self.__tryGC(app_id, app_path)
        except zookeeper.NoNodeException:
          # no apps node.
          pass
      with self.gccv:
        self.gccv.wait(GC_INTERVAL)
    print "Stopping GC thread."

  def __tryGC(self, app_id, app_path):
    try:
#      print "try to obtrain app %s lock" % app_id
      val = zookeeper.get(self.handle, PATH_SEPARATOR.join([app_path, GC_TIME_PATH]), None)[0]
      lasttime = float(val)
    except zookeeper.NoNodeException:
      lasttime = 0
    if lasttime + GC_INTERVAL < time.time():
      # try to gc this app.
      gc_path = PATH_SEPARATOR.join([app_path, GC_LOCK_PATH])
      try:
        now = str(time.time())
        zookeeper.create(self.handle, gc_path, now, ZOO_ACL_OPEN, zookeeper.EPHEMERAL)
        # succeed to obtain lock.
        # TODO: should we handle the timeout of gc also?
        try:
          self.__executeGC(app_id, app_path)
          # update lasttime when gc was succeeded.
          now = str(time.time())
          self.__updateNode(PATH_SEPARATOR.join([app_path, GC_TIME_PATH]), now)
        except Exception, e:
          print "warning: gc error %s" % e
          traceback.print_exc()
        zookeeper.delete(self.handle, gc_path, -1)
      except zookeeper.NodeExistsException:
        # fail to obtain lock. try next time.
        pass

  def __executeGC(self, app_id, app_path):
    # get transaction id list
    txrootpath = PATH_SEPARATOR.join([app_path, APP_TX_PATH])
    try:
      txlist = zookeeper.get_children(self.handle, txrootpath)
    except zookeeper.NoNodeException:
      # there is no transaction yet.
      return

    for txid in txlist:
      if not re.match("^" + APP_TX_PREFIX, txid):
        continue
      txpath = PATH_SEPARATOR.join([txrootpath, txid])
      try:
        txtime = float(zookeeper.get(self.handle, txpath, None)[0])
        if txtime + TX_TIMEOUT < time.time():
          self.notifyFailedTransaction(app_id, long(txid.lstrip(APP_TX_PREFIX)))
      except zookeeper.NoNodeException:
        # Transaction id was dissappeared during gc.
        # The transaction may finished correctly.
        pass
