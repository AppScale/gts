#!/usr/bin/python
"""
Distributed id and lock service for transaction support.
Rewritten by Navraj Chohan and Chris Bunch (raj, chris@appscale.com)
"""

import re
import threading
import time
import traceback
import urllib

import dbconstants
import zookeeper


# A list that indicates that the Zookeeper node to create should be readable
# and writable by anyone.
ZOO_ACL_OPEN = [{"perms":0x1f, "scheme":"world", "id" :"anyone"}]

# The number of seconds to wait before we consider a transaction to be failed.
TX_TIMEOUT = 30

# The number of seconds to wait between invocations of the transaction
# garbage collector.
GC_INTERVAL = 30

# The number of IDs that should be assigned in batch to callers.
ID_BLOCK = 10

# The host and port that the Zookeeper service runs on, if none is provided.
DEFAULT_HOST = "localhost:2181"

PATH_SEPARATOR = "/"

APPS_PATH = "/appscale/apps"

APP_TX_PATH = "txids"

APP_LOCK_PATH = "locks"

APP_ID_PATH = "ids"

APP_TX_PREFIX = "tx"

APP_LOCK_PREFIX = "lk"

APP_ID_PREFIX = "id"

TX_UPDATEDKEY_PREFIX = "ukey"

TX_LOCK_PATH = "lockpath"

# The path for blacklisted transactions.
TX_BLACKLIST_PATH = "blacklist"

TX_VALIDLIST_PATH = "validlist"

GC_LOCK_PATH = "gclock"

GC_TIME_PATH = "gclasttime"

# A unique prefix for cross group transactions.
XG_PREFIX = "xg"

# Maximum number of groups allowed in cross group transactions.
MAX_GROUPS_FOR_XG = 5

# The separator value for the lock list when using XG transactions.
LOCK_LIST_SEPARATOR = "!XG_LIST!"

class ZKTransactionException(Exception):
  """ ZKTransactionException defines a custom exception class that should be
  thrown whenever there was a problem involving a transaction (e.g., the
  transaction failed, we couldn't get a transaction ID).
  """

  TYPE_UNKNOWN = 0
  TYPE_NO_CONNECTION = 1
  TYPE_INVALID = 2
  TYPE_EXPIRED = 3
  TYPE_DIFFERENT_ROOTKEY = 4
  TYPE_CONCURRENT = 5

  def __init__(self, exception_type, message):
    """ Creates a new ZKTransactionException.

    Args:
      exception_type: An int (from the above constants) that indicates why the
        transaction failed.
      message: A str representing the reason why the transaction failed.
    """
    Exception.__init__(self, message)
    self.exception_type = exception_type


class ZKTransaction:
  """ ZKTransaction provides an interface that can be used to acquire locks
  and other functions needed to perform database-agnostic transactions
  (e.g., releasing locks, keeping track of transaction metadata).
  """

  # The number of times we should retry ZooKeeper operations, by default.
  DEFAULT_NUM_RETRIES = 5

  def __init__(self, host=DEFAULT_HOST, start_gc=True):
    """ Creates a new ZKTransaction, which will communicate with Zookeeper
    on the given host.

    Args:
      host: A str that indicates which machine runs the Zookeeper service.
      start_gc: A bool that indicates if we should start the garbage collector
        for timed out transactions.
    """
    # Connection instance variables.
    self.connect_cv = threading.Condition()
    self.connected = False
    self.handle = zookeeper.init(host, self.receive_and_notify)

    # for blacklist cache
    self.blacklist_cv = threading.Condition()
    self.blacklist_cache = {}

    # for gc
    self.gc_running = False
    self.gc_cv = threading.Condition()
    if start_gc:
      self.start_gc()

  def start_gc(self):
    """ Starts a new thread that cleans up failed transactions.

    If called when the GC thread is already started, this causes the GC thread
    to reload its GC settings.
    """
    with self.gc_cv:
      if self.gc_running:
        self.gc_cv.notifyAll()
      else:
        self.gc_running = True
        self.gcthread = threading.Thread(target=self.gc_runner)
        self.gcthread.start()

  def stop_gc(self):
    """ Stops the thread that cleans up failed transactions.
    """
    if self.gc_running:
      with self.gc_cv:
        self.gc_running = False
        self.gc_cv.notifyAll()
      self.gcthread.join()

  def close(self):
    """ Stops the thread that cleans up failed transactions and closes its
    connection to Zookeeper.
    """
    self.stop_gc()
    zookeeper.close(self.handle)

  def receive_and_notify(self, handle, event_type, state, path):
    """ Receives events and notifies other threads if ZooKeeper state changes.
 
    Args:
      handle: A ZooKeeper connection.
      event_type: An int representing a ZooKeeper event.
      state: An int representing a ZooKeeper connection state.
      path: A str representing the path that changed.
    """
    if event_type == zookeeper.SESSION_EVENT:
      if state == zookeeper.CONNECTED_STATE:
        with self.connect_cv:
          self.connected = True
          self.connect_cv.notifyAll()
      else:
        with self.connect_cv:
          self.connected = False
          self.connect_cv.notifyAll()
    elif event_type == zookeeper.CHILD_EVENT:
      path_list = path.split(PATH_SEPARATOR)
      if path_list[-1] == TX_BLACKLIST_PATH:
        appid = urllib.unquote_plus(path_list[-3])
        self.update_blacklist_cache(appid)

  def update_blacklist_cache(self, path, app_id):
    """ Updates the blacklist cache.  
 
    Args: 
      path: The path for the blacklist.
      app_id: The application identifier.
    """
    try:
      black_list = zookeeper.get_children(self.handle, path,
        self.receive_and_notify)
      with self.blacklist_cv:
        self.blacklist_cache[app_id] = set(black_list)
    except zookeeper.NoNodeException:
      if app_id in self.blacklist_cache:
        with self.blacklist_cv:
          del self.blacklist_cache[app_id]
    
  def wait_for_connect(self):
    if self.connected:
      return
    with self.connect_cv:
      while not self.connected:
        self.connect_cv.wait(10.0)

  def force_create_path(self, path, value="default"):
    """ Creates a new ZooKeeper node at the given path, recursively creating its
      parent nodes if necessary.
    
    Args:
      path: A PATH_SEPARATOR-separated str that represents the path to create.
      value: A str representing the value that should be associated with the
        new node, created at path.
    Returns:
      True if the new ZooKeeper node at path was created successfully, and False
        otherwise.
    """
    self.wait_for_connect()
    while True:
      try:
        zookeeper.create(self.handle, path, str(value), ZOO_ACL_OPEN)
        return True
      except zookeeper.NoNodeException:
        # Recursively create this node's parents, but don't return - the next
        # iteration of this loop will create this node once the parents are
        # created.
        self.force_create_path(PATH_SEPARATOR.join(
          path.split(PATH_SEPARATOR)[:-1]), value)
      except zookeeper.NodeExistsException:  # just update value
        zookeeper.aset(self.handle, path, str(value))
        return True
      except Exception as e:
        print "warning: create error %s" % e
        return False

  def update_node(self, path, value):
    """ Sets the ZooKeeper node at path to value, creating the node if it
      doesn't exist.

    Args:
      path: A PATH_SEPARATOR-separated str that represents the node whose value
        should be updated.
      value: A str representing the value that should be associated with the
        updated node.
    """
    self.wait_for_connect()
    try:
      zookeeper.set(self.handle, path, value)
    except zookeeper.NoNodeException:
      self.force_create_path(path, value)

  def delete_recursive(self, path):
    """ Deletes the ZooKeeper node at path, and any child nodes it may have.

    Args:
      path: A PATH_SEPARATOR-separated str that represents the node to delete.
    """
    self.wait_for_connect()
    try:
      children = zookeeper.get_children(self.handle, path)
      for child in children:
        self.delete_recursive(PATH_SEPARATOR.join([path, child]))
      zookeeper.delete(self.handle, path, -1)
    except zookeeper.NoNodeException:
      pass

  def dump_tree(self, path):
    """ Prints information about the given ZooKeeper node and its children.

    Args:
      path: A PATH_SEPARATOR-separated str that represents the node to print
        info about.
    """
    self.wait_for_connect()
    try:
      value = zookeeper.get(self.handle, path, None)[0]
      print "%s = \"%s\"" % (path, value)
      children = zookeeper.get_children(self.handle, path)
      for child in children:
        self.dump_tree(PATH_SEPARATOR.join([path, child]))
    except zookeeper.NoNodeException:
      print "%s does not exist." % path

  def get_app_root_path(self, app_id):
    """ Returns the ZooKeeper path that holds all information for the given
      application.

    Args:
      app_id: A str that represents the application we wish to get the root
        path for.
    Returns:
      A str that represents a ZooKeeper node, whose immediate children are
      the transaction prefix path and the locks prefix path.
    """
    return PATH_SEPARATOR.join([APPS_PATH, urllib.quote_plus(app_id)])

  def get_transaction_prefix_path(self, app_id):
    """ Returns the location of the ZooKeeper node who contains all transactions
    in progress for the given application.

    Args:
      app_id: A str that represents the application we wish to get all
        transaction information for.
    Returns:
      A str that represents a ZooKeeper node, whose immediate children are all
      of the transactions currently in progress.
    """
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_TX_PATH])

  def get_transaction_path_before_getting_id(self, app_id):
    """ Returns a path that callers can use to get new transaction IDs from
    ZooKeeper, which are given as sequence nodes.

    Args:
      app_id: A str that represents the application we wish to build a new
        transaction path for.
    Returns: A str that can be used to create new transactions.
    """
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_TX_PREFIX])

  def get_transaction_path(self, app_id, txid):
    """ Returns the location of the ZooKeeper node who contains all information
      for a transaction, and is the parent of the transaction lock list and
      registered keys for the transaction.

    Args:
      app_id: A str that represents the application we wish to get the prefix
        path for.
      txid: An int that represents the transaction ID whose path we wish to
        acquire.
    """
    txstr = APP_TX_PREFIX + "%010d" % txid
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_TX_PATH,
      txstr])

  def get_transaction_lock_list_path(self, app_id, txid):
    """ Returns the location of the ZooKeeper node whose value is a
    XG_LIST-separated str, representing all of the locks that have been acquired
    for the given transaction ID.

    Args:
      app_id: A str that represents the application we wish to get the
        transaction information about.
      txid: A str that represents the transaction ID we wish to get the lock
        list location for.
    Returns:
      A PATH_SEPARATOR-delimited str corresponding to the ZooKeeper node that
      contains the list of locks that have been taken for the given transaction.
    """
    return PATH_SEPARATOR.join([self.get_transaction_path(app_id, txid),
      TX_LOCK_PATH])

  def get_blacklist_root_path(self, app_id):
    """ Returns the location of the ZooKeeper node whose children are
      all of the blacklisted transaction IDs for the given application ID.

    Args:
      app_id: A str corresponding to the application who we want to get
        blacklisted transaction IDs for.
    Returns:
      A str corresponding to the ZooKeeper node whose children are blacklisted
      transaction IDs.
    """
    return PATH_SEPARATOR.join([self.get_transaction_prefix_path(app_id),
      TX_BLACKLIST_PATH])

  def get_valid_transaction_root_path(self, app_id):
    """ Returns the location of the ZooKeeper node whose children are
      all of the valid transaction IDs for the given application ID.

    Args:
      app_id: A str corresponding to the application who we want to get
        valid transaction IDs for.
    Returns:
      A str corresponding to the ZooKeeper node whose children are valid
      transaction IDs.
    """
    return PATH_SEPARATOR.join([self.get_transaction_prefix_path(app_id),
      TX_VALIDLIST_PATH])

  def get_valid_transaction_path(self, app_id, entity_key):
    return PATH_SEPARATOR.join([self.get_valid_transaction_root_path(app_id),
      urllib.quote_plus(entity_key)])

  def get_lock_root_path(self, app_id, key):
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_LOCK_PATH,
      urllib.quote_plus(key)])

  def get_id_root_path(self, app_id, key):
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_ID_PATH,
      urllib.quote_plus(key)])

  def get_xg_path(self, app_id, tx_id):
    """ Gets the XG path for a transaction.
  
    Args:
      app_id: The application ID whose XG path we want.
      tx_id: The transaction ID whose XG path we want.
    Returns:
      A str representing the XG path for the given transaction.
    """ 
    txstr = APP_TX_PREFIX + "%010d" % tx_id
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_TX_PATH, 
      txstr, XG_PREFIX])
 
  def create_node(self, path, value):
    """ Creates a new node in ZooKeeper, with the given value.

    Args:
      path: The path to create the node at.
      value: The value that we should store in the node.
    Raises:
      ZKTransactionException: If the sequence node couldn't be created.
    """
    retries_left = self.DEFAULT_NUM_RETRIES
    while retries_left > 0:
      try:
        zookeeper.create(self.handle, path, value, ZOO_ACL_OPEN)
        return
      except zookeeper.NoNodeException:
        self.force_create_path(path)
      finally:
        retries_left -= 1
    
    raise ZKTransactionException(ZKTransactionException.TYPE_UNKNOWN, 
      "Unable to create sequence node with path {0}, value {1}" \
      .format(path, value))


  def create_sequence_node(self, path, value):
    """ Creates a new sequence node in ZooKeeper, with a non-zero initial ID.

    We avoid using zero as the initial ID because Google App Engine apps can
    use a zero ID as a sentinel value, to indicate that an ID should be
    allocated for them.

    Args:
      path: The prefix to create the sequence node at. For example, a prefix
        of '/abc' would result in a sequence node of '/abc1' being created.
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
          txn_id = long(txn_id_path.split(PATH_SEPARATOR)[-1].lstrip(
            APP_TX_PREFIX))
          if txn_id == 0:
            zookeeper.adelete(self.handle, txn_id_path)
          else:
            return txn_id
      except zookeeper.NoNodeException:
        self.force_create_path(path)
      finally:
        retries_left -= 1
    
    raise ZKTransactionException(ZKTransactionException.TYPE_UNKNOWN,
      "Unable to create sequence node with path {0}, value {1}" \
      .format(path, value))


  def get_transaction_id(self, app_id, is_xg=False):
    """Acquires a new id for an upcoming transaction.

    Note that the caller must lock particular root entities using acquire_lock,
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
    rootpath = self.get_transaction_prefix_path(app_id)
    timestamp = str(time.time())
    txn_id = -1

    # First, make the ZK node for the actual transaction id.
    app_path = self.get_transaction_path_before_getting_id(app_id)
    txn_id = self.create_sequence_node(app_path, timestamp)

    # Next, make the ZK node that indicates if this a XG transaction.
    if is_xg:
      xg_path = self.get_xg_path(app_id, txn_id)
      self.create_node(xg_path, timestamp)
    return txn_id

  def check_transaction(self, app_id, txid):
    """ Gets the status of the given transaction.

    Args:
      app_id: A str representing the application whose transaction we wish to
        query.
      txid: An int that indicates the transaction ID we should query.
    Returns:
      True if the transaction is in progress.
    Raises:
      ZKTransactionException: If the transaction is not in progress, or it
        has timed out.
    """
    self.wait_for_connect()
    txpath = self.get_transaction_path(app_id, txid)
    if self.is_blacklisted(app_id, txid):
      raise ZKTransactionException(ZKTransactionException.TYPE_EXPIRED, 
            "zktransaction.check_transaction: Transaction %d timed out." % txid)
    if not zookeeper.exists(self.handle, txpath):
      raise ZKTransactionException(ZKTransactionException.TYPE_INVALID, 
            "zktransaction.check_transaction: Transaction %d is not valid." %
            txid)
    return True

  def is_in_transaction(self, app_id, txid):
    """ Checks to see if the named transaction is currently running.

    Args:
      app_id: A str representing the application whose transaction we wish to
        query.
      txid: An int that indicates the transaction ID we should query.
    Returns:
      True if the transaction is in progress, and False otherwise.
    Raises:
      ZKTransactionException: If the transaction is blacklisted.
    """
    self.wait_for_connect()
    tx_lock_path = self.get_transaction_lock_list_path(app_id, txid)
    if self.is_blacklisted(app_id, txid):
      raise ZKTransactionException(ZKTransactionException.TYPE_EXPIRED, 
            "zktransaction.is_in_transaction: Transaction %d timed out." % txid)
    if not zookeeper.exists(self.handle, tx_lock_path):
      return False
    return True

  def acquire_additional_lock(self, app_id, txid, entity_key, create):
    """ Acquire an additional lock for a cross group transaction.

    Args:
      app_id: A str representing the application ID.
      txid: The transaction ID you are acquiring a lock for. Built into
            the path.
      entity_key: Used to get the root path.
      create: A bool that indicates if we should create a new Zookeeper node
        to store the lock information in.
    Returns:
      Boolean, of true on success, false if lock can not be acquired.
    Raises:
      ZKTransactionException: If we can't acquire the lock for the given
        entity group, because a different transaction already has it.
    """
    self.check_transaction(app_id, txid)
    txpath = self.get_transaction_path(app_id, txid)
    lockrootpath = self.get_lock_root_path(app_id, entity_key)
    lockpath = None
    retry = True
    while retry:
      retry = False
      try:
        lockpath = zookeeper.create(self.handle, lockrootpath, txpath,
          ZOO_ACL_OPEN)
      except zookeeper.NoNodeException:
        # This is for recursively creating a path.
        self.force_create_path(PATH_SEPARATOR.join(lockrootpath.split(
          PATH_SEPARATOR)[:-1]))
        retry = True
      except zookeeper.NodeExistsException:
        # fail to get lock
        raise ZKTransactionException(ZKTransactionException.TYPE_CONCURRENT,
          "acquire_additional_lock: There is already another transaction " + \
          "using this lock")

    # set lockpath for transaction node
    # TODO: we should think about atomic operation or recovery of
    #       inconsistent lockpath node.
    transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)
    if create:
      zookeeper.acreate(self.handle, transaction_lock_path, lockpath, 
        ZOO_ACL_OPEN)
    else:
      tx_lockpath = zookeeper.get(self.handle, transaction_lock_path, None)[0]
      lock_list = tx_lockpath.split(LOCK_LIST_SEPARATOR)
      if len(lock_list) >= MAX_GROUPS_FOR_XG:
        raise ZKTransactionException(ZKTransactionException.TYPE_CONCURRENT,
          "acquire_additional_lock: Too many groups for this XG transaction.")
      lock_list.append(txpath)
      lock_list_str = LOCK_LIST_SEPARATOR.join(lock_list)
      zookeeper.aset(self.handle, tx_lockpath, lock_list_str)

    return True

  def is_xg(self, app_id, tx_id):
    """ Checks to see if the transaction can operate over multiple entity
      groups.

    Args:
      app_id: The application ID that the transaction operates over.
      tx_id: The transaction ID that may or may not be XG.
    Returns:
      True if the transaction is XG, False otherwise.
    """
    return zookeeper.exists(self.handle, self.get_xg_path(app_id, tx_id))

  def acquire_lock(self, app_id, txid, entity_key):
    """ Acquire lock for transaction. It will acquire additional locks
    if the transactions is XG.

    You must call get_transaction_id() first to obtain transaction ID.
    You could call this method anytime if the root entity key is same, 
    or different in the case of it being XG.

    Args:
      app_id: The application ID to acquire a lock for.
      txid: The transaction ID you are acquiring a lock for. Built into 
        the path. 
       entity_key: Used to get the root path.
    Raises:
      ZKTransactionException: If it could not get the lock.
    """
    lockrootpath = self.get_lock_root_path(app_id, entity_key)

    if self.is_in_transaction(app_id, txid):  # use current lock
      transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)
      prelockpath = zookeeper.get(self.handle, transaction_lock_path, None)[0]
      lock_list = prelockpath.split(LOCK_LIST_SEPARATOR)
      if lockrootpath in lock_list:
        print "Already has lock: %s" % lockrootpath
        return True
      else:
        if self.is_xg(app_id, txid):
          return self.acquire_additional_lock(app_id, txid, entity_key,
            create=False)
        else:
          raise ZKTransactionException(
            ZKTransactionException.TYPE_DIFFERENT_ROOTKEY, "acquire_lock: " + \
              "You can not lock different root entity in " + \
              "non-cross-group transaction.")

    return self.acquire_additional_lock(app_id, txid, entity_key, create=True)

  def get_updated_key_list(self, app_id, txid):
    """ Gets a list of keys updated in this transaction.

    Args:
      app_id: A str corresponding to the application ID whose transaction we
        wish to query.
      txid: The transaction ID that we want to get a list of updated keys for.
    Returns:
      A list of keys that have been updated in this transaction.
    Raises:
      ZKTransactionException: If the given transaction ID does not correspond
        to a transaction that is currently in progress.
    """
    self.wait_for_connect()
    txpath = self.get_transaction_path(app_id, txid)
    try:
      child_list = zookeeper.get_children(self.handle, txpath)
      keylist = []
      for item in child_list:
        if re.match("^" + TX_UPDATEDKEY_PREFIX, item):
          keyandtx = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath,
            item]), None)[0]
          key = urllib.unquote_plus(keyandtx.split(PATH_SEPARATOR)[0])
          keylist.append(key)
      return keylist
    except zookeeper.NoNodeException:
      raise ZKTransactionException(ZKTransactionException.TYPE_INVALID, 
        "get_updated_key_list: Transaction ID %d is not valid." % txid)

  def release_lock(self, app_id, txid, entity_key=None):
    """ Releases all locks acquired during this transaction.

    Callers must call acquire_lock before calling release_lock. Upon calling
    release_lock, the given transaction ID is no longer valid.

    Args:
      app_id: The application ID we are releasing a lock for.
      txid: The transaction ID we are releasing a lock for.
      entity_key: The entity key we use to build the path.
    Returns:
      True if the locks were released, and False otherwise.
    Raises:
      ZKTransactionException: If any locks acquired during this transaction
        could not be released.
    """
    self.wait_for_connect()
    self.check_transaction(app_id, txid)
    txpath = self.get_transaction_path(app_id, txid)
     
    transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)
    try:
      lock_list_str = zookeeper.get(self.handle, transaction_lock_path, None)[0]
      lock_list = lock_list_str.split(LOCK_LIST_SEPARATOR)
      for lock_path in lock_list:
        zookeeper.adelete(self.handle, lock_path)
      zookeeper.delete(self.handle, transaction_lock_path)
    except zookeeper.NoNodeException:
      pass

    if self.is_xg(app_id, txid):
      xg_path = self.get_xg_path(app_id, txid)
      zookeeper.adelete(self.handle, xg_path)

    for child in zookeeper.get_children(self.handle, txpath):
      zookeeper.adelete(self.handle, PATH_SEPARATOR.join([txpath, child]))

    # This delets the transaction root path.
    zookeeper.adelete(self.handle, txpath)

  def is_blacklisted(self, app_id, txid):
    """ Checks to see if the given transaction ID has been blacklisted (that is,
    if it is no longer considered to be a valid transaction).

    Args:
      app_id: The application ID whose transaction ID we want to validate.
      txid: The transaction ID that we want to validate.
    Returns:
      True if the transaction is blacklisted, False otherwise.
    """
    self.wait_for_connect()
    if app_id in self.blacklist_cache:
      with self.blacklist_cv:
        return str(txid) in self.blacklist_cache[app_id]
    else:
      blacklist_root = self.get_blacklist_root_path(app_id)
      if not zookeeper.exists(self.handle, blacklist_root):
        self.force_create_path(blacklist_root)
      try:
        blacklist = zookeeper.get_children(self.handle, blacklist_root,
          self.receive_and_notify)
        with self.blacklist_cv:
          self.blacklist_cache[app_id] = set(blacklist)
          return str(txid) in self.blacklist_cache[app_id]
      except zookeeper.NoNodeException:  # there is no blacklist
        return False

  def get_valid_transaction_id(self, app_id, target_txid, entity_key):
    """ This returns valid transaction id for the entity key.

    If the specified transaction id is black-listed,
    this returns latest valid transaction id.
    If there is no valid transaction id, this returns 0.
    """
    self.wait_for_connect()
    if not self.is_blacklisted(app_id, target_txid):
      return target_txid
    # get the valid id
    vtxpath = self.get_valid_transaction_path(app_id, entity_key)
    try:
      vid = zookeeper.get(self.handle, vtxpath, None)[0]
      return long(vid)
    except zookeeper.NoNodeException:
      # The transaction is blacklisted, but there is no valid id.
      return long(0)

  def register_updated_key(self, app_id, current_txid, target_txid, entity_key):
    """ Regist valid transaction id for entity.

    target_txid must be the latest valid transaction id for the entity.
    """
    self.wait_for_connect()
    vtxpath = self.get_valid_transaction_path(app_id, entity_key)
    if zookeeper.exists(self.handle, vtxpath):
      # just update transaction id for entity if there is valid transaction.
      zookeeper.aset(self.handle, vtxpath, str(target_txid))
    else:
      # store the updated key info into current transaction node.
      value = PATH_SEPARATOR.join([urllib.quote_plus(entity_key),
        str(target_txid)])
      txpath = self.get_transaction_path(app_id, current_txid)
      if zookeeper.exists(self.handle, txpath):
        zookeeper.acreate(self.handle, PATH_SEPARATOR.join([txpath,
          TX_UPDATEDKEY_PREFIX]), value, ZOO_ACL_OPEN, zookeeper.SEQUENCE)
      else:
        raise ZKTransactionException(ZKTransactionException.TYPE_INVALID,
          "Transaction %d is not valid." % current_txid)

  def notify_failed_transaction(self, app_id, txid):
    """ Marks the given transaction as failed, invalidating its use by future
    callers.

    Args:
      app_id: The application ID whose transaction we wish to invalidate.
      txid: An int representing the transaction ID we wish to invalidate.
    Returns:
      True if the transaction was invalidated, False otherwise.
    """
    self.wait_for_connect()
    self.check_transaction(app_id, txid)
    print "notify failed transaction app:%s, txid:%d" % (app_id, txid)
    txpath = self.get_transaction_path(app_id, txid)
    lockpath = None
    try:
      lockpath = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath,
        TX_LOCK_PATH]), None)[0]
    except zookeeper.NoNodeException:
      # there is no lock. it means there is no need to rollback.
      pass

    if lockpath:
      # add transaction id to black list.
      now = str(time.time())
      broot = self.get_blacklist_root_path(app_id)
      if not zookeeper.exists(self.handle, broot):
        self.force_create_path(broot)
      zookeeper.acreate(self.handle, PATH_SEPARATOR.join([broot, str(txid)]),
        now, ZOO_ACL_OPEN)
      # update local cache before notification
      if app_id in self.blacklist_cache:
        with self.blacklist_cv:
          self.blacklist_cache[app_id].add(str(txid))
      # copy valid transaction id for each updated key into valid list.
      for child in zookeeper.get_children(self.handle, txpath):
        if re.match("^" + TX_UPDATEDKEY_PREFIX, child):
          value = zookeeper.get(self.handle, PATH_SEPARATOR.join([txpath,
            child]), None)[0]
          valuelist = value.split(PATH_SEPARATOR)
          key = urllib.unquote_plus(valuelist[0])
          vid = valuelist[1]
          vtxroot = self.get_valid_transaction_root_path(app_id)
          if not zookeeper.exists(self.handle, vtxroot):
            self.force_create_path(vtxroot)
          vtxpath = self.get_valid_transaction_path(app_id, key)
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
      return True
    except zookeeper.NoNodeException:
      # something went wrong. next GC will take care of it.
      return False

  def generate_id_block(self, app_id, entity_key):
    """ Allocates a range of IDs that can be used for an entity group.

    Google App Engine reserves ID 0 for callers to indicate that we should
    pick out an ID for them, so this method makes sure that we don't return
    ID 0 to the caller.

    Args:
      app_id: A str corresponding to the application whose key we want to
        allocate IDs for.
      entity_key: The entity that we want to generate a block of IDs for.
    Returns:
      A tuple, whose first value is a long corresponding to the first ID that
      can be used by callers, and whose second value corresponds to the number
      of IDs that have been allocated.
    """
    self.wait_for_connect()
    id_root_path = self.get_id_root_path(app_id, entity_key)
    path = PATH_SEPARATOR.join([id_root_path, APP_ID_PREFIX])
    value = entity_key
    start = -1
    while True:
      try:
        id_path = zookeeper.create(self.handle, path, value, ZOO_ACL_OPEN,
          zookeeper.SEQUENCE)
        zookeeper.adelete(self.handle, id_path)
        id_base = long(id_path.split(PATH_SEPARATOR)[-1].lstrip(APP_ID_PREFIX))
        start = id_base * ID_BLOCK
        if start != 0:
          return (start, ID_BLOCK)
      except zookeeper.NoNodeException:
        self.force_create_path(id_root_path)
      except Exception, e:
        print e
        raise ZKTransactionException(ZKTransactionException.TYPE_UNKNOWN,
          "Failed to generate ID block: %s" % e)

  def gc_runner(self):
    """ Transaction ID garbage collection runner.

    This must be running as separate thread.
    """
    print "Starting GC thread."
    while self.gc_running:
      if self.connected:
        # scan each application's last gc time
        try:
          app_list = zookeeper.get_children(self.handle, APPS_PATH)
          for app in app_list:
            app_id = urllib.unquote_plus(app)
            # app is already encoded, so we shouldn't use self.get_app_root_path
            app_path = PATH_SEPARATOR.join([APPS_PATH, app])
            self.try_gc(app_id, app_path)
        except zookeeper.NoNodeException:
          # no apps node.
          pass
      with self.gc_cv:
        self.gc_cv.wait(GC_INTERVAL)
    print "Stopping GC thread."

  def try_gc(self, app_id, app_path):
    try:
      val = zookeeper.get(self.handle, PATH_SEPARATOR.join([app_path,
        GC_TIME_PATH]), None)[0]
      lasttime = float(val)
    except zookeeper.NoNodeException:
      lasttime = 0
    if lasttime + GC_INTERVAL < time.time():
      # try to gc this app.
      gc_path = PATH_SEPARATOR.join([app_path, GC_LOCK_PATH])
      try:
        now = str(time.time())
        zookeeper.create(self.handle, gc_path, now, ZOO_ACL_OPEN,
          zookeeper.EPHEMERAL)
        # succeed to obtain lock.
        # TODO: should we handle the timeout of gc also?
        try:
          self.execute_gc(app_id, app_path)
          # update lasttime when gc was succeeded.
          now = str(time.time())
          self.update_node(PATH_SEPARATOR.join([app_path, GC_TIME_PATH]), now)
        except Exception, e:
          print "warning: gc error %s" % e
          traceback.print_exc()
        zookeeper.delete(self.handle, gc_path, -1)
      except zookeeper.NodeExistsException:
        # fail to obtain lock. try next time.
        pass

  def execute_gc(self, app_id, app_path):
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
          self.notify_failed_transaction(app_id, long(txid.lstrip(
            APP_TX_PREFIX)))
      except zookeeper.NoNodeException:
        # Transaction id was dissappeared during gc.
        # The transaction may finished correctly.
        pass
