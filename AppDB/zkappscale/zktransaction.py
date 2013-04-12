#!/usr/bin/python
"""
Distributed id and lock service for transaction support.
Rewritten by Navraj Chohan and Chris Bunch (raj, chris@appscale.com)
"""
import logging
import re
import signal
import threading
import time
import traceback
import urllib

import zookeeper

class ZKTimeoutException(Exception):
  """ A special Exception class that should be thrown if a function is 
  taking longer than expected by the caller to run
  """
  pass

# A list that indicates that the Zookeeper node to create should be readable
# and writable by anyone.
ZOO_ACL_OPEN = [{"perms":0x1f, "scheme":"world", "id" :"anyone"}]

# The number of seconds to wait before we consider a transaction to be failed.
TX_TIMEOUT = 30

# The number of seconds to wait between invocations of the transaction
# garbage collector.
GC_INTERVAL = 30

# The host and port that the Zookeeper service runs on, if none is provided.
DEFAULT_HOST = "localhost:2181"

# Paths are separated by this for the tree structure in zookeeper.
PATH_SEPARATOR = "/"

# This is the path which contains the different application's lock meta-data.
APPS_PATH = "/appscale/apps"

# This path contains different transaction IDs.
APP_TX_PATH = "txids"

# This is the node which holds all the locks of an application.
APP_LOCK_PATH = "locks"

APP_ID_PATH = "ids"

APP_TX_PREFIX = "tx"

APP_LOCK_PREFIX = "lk"

APP_ID_PREFIX = "id"

# This is the prefix of all keys which have been updated within a transaction.
TX_UPDATEDKEY_PREFIX = "ukey"

# This is the name of the leaf. It holds a list of locks as a string.
TX_LOCK_PATH = "lockpath"

# The path for blacklisted transactions.
TX_BLACKLIST_PATH = "blacklist"

# This is the path name for valid versions of entities used in a transaction.
TX_VALIDLIST_PATH = "validlist"

GC_LOCK_PATH = "gclock"

GC_TIME_PATH = "gclast_time"

# Lock path for the datastore groomer.
DS_GROOM_LOCK_PATH = "/appscale_datastore_groomer"

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
  pass

class ZKTransaction:
  """ ZKTransaction provides an interface that can be used to acquire locks
  and other functions needed to perform database-agnostic transactions
  (e.g., releasing locks, keeping track of transaction metadata).
  """

  # The number of times we should retry ZooKeeper operations, by default.
  DEFAULT_NUM_RETRIES = 5

  # The number of seconds to wait before we consider a zk call a failure.
  DEFAULT_ZK_TIMEOUT = 3

  def __init__(self, host=DEFAULT_HOST, start_gc=True):
    """ Creates a new ZKTransaction, which will communicate with Zookeeper
    on the given host.

    Args:
      host: A str that indicates which machine runs the Zookeeper service.
      start_gc: A bool that indicates if we should start the garbage collector
        for timed out transactions.
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.INFO)
    logging.debug("Started logging")

    # Connection instance variables.
    self.connect_cv = threading.Condition()
    self.connected = False
    self.host = host
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
    logging.info("Starting GC thread")
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
    logging.info("Stopping GC thread")
    if self.gc_running:
      with self.gc_cv:
        self.gc_running = False
        self.gc_cv.notifyAll()
      self.gcthread.join()

  def close(self):
    """ Stops the thread that cleans up failed transactions and closes its
    connection to Zookeeper.
    """
    logging.info("Closing ZK connection")
    self.stop_gc()
    zookeeper.close(self.handle)

  def receive_and_notify(self, _, event_type, state, path):
    """ Receives events and notifies other threads if ZooKeeper state changes.
 
    Args:
      _: A ZooKeeper connection (unused).
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
        self.update_blacklist_cache(path, appid)

  def update_blacklist_cache(self, path, app_id):
    """ Updates the blacklist cache.  
 
    Args: 
      path: The path for the blacklist.
      app_id: The application identifier.
    """
    logging.debug("Updating blacklist cache for app {0}".format(app_id))
    try:
      # This is not apart of the main thread, so don't run it 
      # with a timeout. (Signals can only be in the main thread)
      black_list = zookeeper.get_children(self.handle, path, 
        self.receive_and_notify)
      with self.blacklist_cv:
        self.blacklist_cache[app_id] = set(black_list)
    except zookeeper.NoNodeException:
      if app_id in self.blacklist_cache:
        with self.blacklist_cv:
          del self.blacklist_cache[app_id]
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("ZK Exception: {0}".format(zk_exception))
      self.reestablish_connection()
    
  def wait_for_connect(self):
    """ Blocks on a connection. Waits for a signal from the notify function """
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
    logging.debug("Force creating path {0}, with value {1}".format(path, value))
    self.wait_for_connect()
    while True:
      try:
        zookeeper.create(self.handle, path, str(value), ZOO_ACL_OPEN)
        return True
      except zookeeper.NoNodeException:
        # Recursively create this node's parents, but don't return - the next
        # iteration of this loop will create this node once the parents are
        # created.
        logging.debug("Couldn't create path {0}, so creating its parent " \
          "first.".format(path))
        self.force_create_path(PATH_SEPARATOR.join(
          path.split(PATH_SEPARATOR)[:-1]), value)
      except zookeeper.NodeExistsException:  # just update value
        logging.debug("Path {0} already exists, so setting its value.".format(
          path))
        zookeeper.aset(self.handle, path, str(value))
        return True
      except zookeeper.ZooKeeperException, zoo_exception:
        logging.error("Couldn't create path {0} because of ZK exception {1}".\
          format(path, str(zoo_exception)))
        return False
      except Exception as exception:
        logging.error("Couldn't create path {0} because of {1}".format(path,
          str(exception)))
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
    logging.debug("Updating node at {0}, with new value {1}".format(path,
      value))
    self.wait_for_connect()
    try:
      zookeeper.set(self.handle, path, value)
    except zookeeper.NoNodeException:
      self.force_create_path(path, value)
    except zookeeper.ZooKeeperException, zoo_exception:
      logging.error("Problem setting path {0} with {1}, exception {2}"\
        .format(path, value, str(zoo_exception)))

  def delete_recursive(self, path):
    """ Deletes the ZooKeeper node at path, and any child nodes it may have.

    Args:
      path: A PATH_SEPARATOR-separated str that represents the node to delete.
    """
    self.wait_for_connect()
    try:
      children = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.get_children, self.handle, path)
      for child in children:
        self.delete_recursive(PATH_SEPARATOR.join([path, child]))
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.delete, self.handle, path, -1)
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
      logging.info("{0} = \"{1}\"".format(path, value))
      children = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.get_children, self.handle, path)
      for child in children:
        self.dump_tree(PATH_SEPARATOR.join([path, child]))
    except zookeeper.NoNodeException:
      logging.info("{0} does not exist.".format(path))

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

  def get_txn_path_before_getting_id(self, app_id):
    """ Returns a path that callers can use to get new transaction IDs from
    ZooKeeper, which are given as sequence nodes.

    Args:
      app_id: A str that represents the application we wish to build a new
        transaction path for.
    Returns: A str that can be used to create new transactions.
    """
    return PATH_SEPARATOR.join([self.get_transaction_prefix_path(app_id),
      APP_TX_PREFIX])

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
    """ Gets the valid transaction path with the entity key.
    Args:
      app_id: The application ID.
      entity_key: The entity within the path.
    Returns:
      A str representing the transaction path.
    """
    return PATH_SEPARATOR.join([self.get_valid_transaction_root_path(app_id),
      urllib.quote_plus(entity_key)])

  def get_lock_root_path(self, app_id, key):
    """ Gets the root path of the lock for a particular app. 
    
    Args:
      app_id: The application ID.
      key: The key for which we're getting the root path lock.
    Returns: 
      A str of the root lock path.
    """
    return PATH_SEPARATOR.join([self.get_app_root_path(app_id), APP_LOCK_PATH,
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
        self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.create, self.handle, path, 
          value, ZOO_ACL_OPEN)
        logging.debug("Created path {0} with value {1}".format(path, value))
        return
      except zookeeper.NoNodeException:
        logging.debug("Couldn't create path {0} - recursively creating it." \
          .format(path))
        self.force_create_path(path)
      finally:
        retries_left -= 1
    
    raise ZKTransactionException("Unable to create sequence node with path " \
      "{0}, value {1}".format(path, value))


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
        txn_id_path = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT, 
          self.DEFAULT_NUM_RETRIES, zookeeper.create, 
          self.handle, path, value, ZOO_ACL_OPEN, zookeeper.SEQUENCE)
        if txn_id_path:
          txn_id = long(txn_id_path.split(PATH_SEPARATOR)[-1].lstrip(
            APP_TX_PREFIX))
          if txn_id == 0:
            logging.warning("Created sequence ID 0 - deleting it.")
            zookeeper.adelete(self.handle, txn_id_path)
          else:
            logging.debug("Created sequence ID {0} at path {1}".format(txn_id, 
              txn_id_path))
            return txn_id
      except zookeeper.NoNodeException:
        self.force_create_path(path)
      finally:
        retries_left -= 1
    
    logging.error("Unable to create sequence node with path {0}, value {1}" \
      .format(path, value))
    raise ZKTransactionException("Unable to create sequence node with path" \
      " {0}, value {1}".format(path, value))

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
    logging.debug("Getting new transaction id for app {0}, with is_xg set " \
      "to {1}".format(app_id, is_xg))
    self.wait_for_connect()
    timestamp = str(time.time())

    # First, make the ZK node for the actual transaction id.
    app_path = self.get_txn_path_before_getting_id(app_id)
    txn_id = self.create_sequence_node(app_path, timestamp)

    # Next, make the ZK node that indicates if this a XG transaction.
    if is_xg:
      xg_path = self.get_xg_path(app_id, txn_id)
      self.create_node(xg_path, timestamp)
    logging.debug("Returning transaction ID {0} with timestamp {1} for " \
      "app_id {2}, with is_xg set to {3}".format(txn_id, timestamp, app_id,
      is_xg))
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
    logging.debug("Checking transaction for app {0}, transaction id {1}".format(
      app_id, txid))
    self.wait_for_connect()
    txpath = self.get_transaction_path(app_id, txid)
    if self.is_blacklisted(app_id, txid):
      raise ZKTransactionException("[check_transaction] Transaction %d timed " \
        "out." % txid)
    if not self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.exists, self.handle, txpath):
      logging.debug("[check_transaction] {0} does not exist".format(txpath))
      raise ZKTransactionException("Transaction %d is not valid." % txid)
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
      raise ZKTransactionException("[is_in_transaction]: Transaction %d timed" \
        " out." % txid)
    if not self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.exists, self.handle, 
          tx_lock_path):
      logging.debug("[is_in_transaction] {0} does not exist".format(
        tx_lock_path))
      return False
    logging.debug("{0} does exist and is not blacklisted".format(tx_lock_path))
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
    logging.debug("Acquiring additional lock for appid {0}, transaction id " \
      "{1}, entity key {2}, with create {3}".format(app_id, txid, entity_key,
      create))
    txpath = self.get_transaction_path(app_id, txid)
    lockrootpath = self.get_lock_root_path(app_id, entity_key)
    lockpath = None
    retry = True

    while retry:
      retry = False
      try:
        logging.debug("Trying to create path {0} with value {1}".format(
          lockrootpath, txpath))
        lockpath = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.create, self.handle, 
          lockrootpath, txpath, ZOO_ACL_OPEN)
      except zookeeper.NoNodeException:
        # This is for recursively creating a path.
        self.force_create_path(PATH_SEPARATOR.join(lockrootpath.split(
          PATH_SEPARATOR)[:-1]))
        retry = True
      except zookeeper.NodeExistsException:
        # fail to get lock
        try:
          tx_lockpath = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT, 
            self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle, 
            lockrootpath, None)[0]
          logging.debug("Lock {0} in use by {1}".format(lockrootpath, 
            tx_lockpath))
        except zookeeper.NoNodeException, no_node:
          # If the lock is released by another thread this can get tossed.
          # A race condition.
          logging.warning("Lock {0} was in use but was released"\
            .format(lockrootpath))
        raise ZKTransactionException("acquire_additional_lock: There is " \
          "already another transaction using {0} lock".format(lockrootpath))

    logging.debug("Created new lock root path {0} with value {1}".format(
      lockrootpath, txpath))

    transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)

    if create:
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.acreate, self.handle, 
        transaction_lock_path, lockpath, ZOO_ACL_OPEN)
      logging.debug("Created lock list path {0} with value {1}".format(
        transaction_lock_path, lockpath))
    else:
      tx_lockpath = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle, 
        transaction_lock_path, None)[0]
      lock_list = tx_lockpath.split(LOCK_LIST_SEPARATOR)
      if len(lock_list) >= MAX_GROUPS_FOR_XG:
        raise ZKTransactionException("acquire_additional_lock: Too many " \
          "groups for this XG transaction.")

      lock_list.append(lockpath)
      lock_list_str = LOCK_LIST_SEPARATOR.join(lock_list)
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.aset, self.handle, 
        transaction_lock_path, lock_list_str)
      logging.debug("Set lock list path {0} to value {1}".format(
        transaction_lock_path, lock_list_str))

    return True

  def is_xg(self, app_id, tx_id):
    """ Checks to see if the transaction can operate over multiple entity
      groups.

    Args:
      app_id: The application ID that the transaction operates over.
      tx_id: The transaction ID that may or may not be XG.
    Returns:
      True if the transaction is XG, False otherwise.
    Raises:
      ZKTransactionException: on ZooKeeper exceptions.
    """
    try:
      return zookeeper.exists(self.handle, 
          self.get_xg_path(app_id, tx_id))
    except zookeeper.ZooKeeperException, zk_exception:
      raise ZKTransactionException("ZooKeeper exception:{0}"\
        .format(zk_exception)) 

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
    Returns:
      True on success, False otherwise.
    Raises:
      ZKTransactionException: If it could not get the lock.
    """
    logging.debug("Acquiring lock for appid {0}, transaction id {1}, " \
      "entity key {2}".format(app_id, txid, entity_key))
    lockrootpath = self.get_lock_root_path(app_id, entity_key)

    if self.is_in_transaction(app_id, txid):  # use current lock
      transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)
      prelockpath = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle, 
        transaction_lock_path, None)[0]
      lock_list = prelockpath.split(LOCK_LIST_SEPARATOR)
      logging.debug("Lock list: {0}".format(lock_list))
      if lockrootpath in lock_list:
        logging.debug("Already has lock: {0}".format(lockrootpath))
        return True
      else:
        if self.is_xg(app_id, txid):
          return self.acquire_additional_lock(app_id, txid, entity_key,
            create=False)
        else:
          raise ZKTransactionException("acquire_lock: You can not lock " \
            "different root entity in non-cross-group transaction.")

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
      child_list = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.get_children, self.handle, txpath)
      keylist = []
      for item in child_list:
        if re.match("^" + TX_UPDATEDKEY_PREFIX, item):
          keyandtx = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT, 
            self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle,
            PATH_SEPARATOR.join([txpath, item]), None)[0]
          key = urllib.unquote_plus(keyandtx.split(PATH_SEPARATOR)[0])
          keylist.append(key)
      return keylist
    except zookeeper.NoNodeException:
      raise ZKTransactionException("get_updated_key_list: Transaction ID %d " \
        "is not valid." % txid)

  def release_lock(self, app_id, txid):
    """ Releases all locks acquired during this transaction.

    Callers must call acquire_lock before calling release_lock. Upon calling
    release_lock, the given transaction ID is no longer valid.

    Args:
      app_id: The application ID we are releasing a lock for.
      txid: The transaction ID we are releasing a lock for.
    Returns:
      True if the locks were released, and False otherwise.
    Raises:
      ZKTransactionException: If any locks acquired during this transaction
        could not be released.
    """
    logging.debug("Releasing locks for app {0}, with transaction id {1} " \
      .format(app_id, txid))
    self.wait_for_connect()
    self.check_transaction(app_id, txid)
    txpath = self.get_transaction_path(app_id, txid)
     
    transaction_lock_path = self.get_transaction_lock_list_path(app_id, txid)
    try:
      lock_list_str = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT, 
          self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle,
          transaction_lock_path, None)[0]
      lock_list = lock_list_str.split(LOCK_LIST_SEPARATOR)
      for lock_path in lock_list:
        self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.adelete, self.handle, lock_path)
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.delete, self.handle, 
        transaction_lock_path)
    except zookeeper.NoNodeException:
      if self.is_blacklisted(app_id, txid):
        raise ZKTransactionException("Unable to release lock {0} for app id {1}"
          .format(transaction_lock_path, app_id))
      else:
        return True

    if self.is_xg(app_id, txid):
      xg_path = self.get_xg_path(app_id, txid)
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.adelete, self.handle, xg_path)

    for child in self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.get_children, self.handle, txpath):
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
        self.DEFAULT_NUM_RETRIES, zookeeper.adelete, self.handle, 
        PATH_SEPARATOR.join([txpath, child]))

    # This deletes the transaction root path.
    self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
      self.DEFAULT_NUM_RETRIES, zookeeper.adelete, self.handle, txpath)

    return True

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
      if not self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.exists, self.handle, 
          blacklist_root):
        self.force_create_path(blacklist_root)
      try:
        blacklist = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.get_children, self.handle, 
          blacklist_root, self.receive_and_notify)
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
      vid = self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.get, self.handle, vtxpath, 
          None)[0]
      return long(vid)
    except zookeeper.NoNodeException:
      # The transaction is blacklisted, but there is no valid id.
      return long(0)

  def register_updated_key(self, app_id, current_txid, target_txid, entity_key):
    """ Registers a key which is a part of a transaction. This is to know
    what journal version we must rollback to upon failure.

    Args:
      app_id: A str representing the application ID.
      current_txid: The current transaction ID for which we'll rollback to upon 
        failure.
      target_txid: A long transaction ID we are rolling forward to.
      entity_key: A str key we are registering.
    Returns:
      True on success.
    Raises:
      A ZKTransactionException if the transaction is not valid. 
    """
    self.wait_for_connect()
    vtxpath = self.get_valid_transaction_path(app_id, entity_key)

    if self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.exists, self.handle, vtxpath):
      # Update the transaction ID for entity if there is valid transaction.
      self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.aset, self.handle, 
          vtxpath, str(target_txid))
    else:
      # Store the updated key info into the current transaction node.
      value = PATH_SEPARATOR.join([urllib.quote_plus(entity_key),
        str(target_txid)])
      txpath = self.get_transaction_path(app_id, current_txid)

      if self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
          self.DEFAULT_NUM_RETRIES, zookeeper.exists, self.handle, txpath):
        self.run_with_timeout(self.DEFAULT_ZK_TIMEOUT,
            self.DEFAULT_NUM_RETRIES, zookeeper.acreate, self.handle, 
            PATH_SEPARATOR.join([txpath,
          TX_UPDATEDKEY_PREFIX]), value, ZOO_ACL_OPEN, zookeeper.SEQUENCE)
      else:
        raise ZKTransactionException("Transaction {0} is not valid.".format(
          current_txid))

    return True

  def notify_failed_transaction(self, app_id, txid):
    """ Marks the given transaction as failed, invalidating its use by future
    callers.

    Args:
      app_id: The application ID whose transaction we wish to invalidate.
      txid: An int representing the transaction ID we wish to invalidate.
    Returns:
      True if the transaction was invalidated, False otherwise.
    """
    logging.warning("Notify failed transaction app: {0}, txid: {1}"\
      .format(app_id, str(txid)))

    self.wait_for_connect()
    lockpath = None
    lock_list = []

    txpath = self.get_transaction_path(app_id, txid)

    try:
      lockpath = zookeeper.get(self.handle, 
          PATH_SEPARATOR.join([txpath, TX_LOCK_PATH]), None)[0]
      lock_list = lockpath.split(LOCK_LIST_SEPARATOR)
    except zookeeper.NoNodeException:
      # There is no need to rollback because there is no lock.
      pass
    except zookeeper.ZooKeeperException, zoo_exception:
      logging.error("Exception seen when notifying a failed transaction {0}"\
        .format(str(zoo_exception)))
      return

    try:
      if lock_list:
        # Add the transaction ID to the blacklist.
        now = str(time.time())
        blacklist_root = self.get_blacklist_root_path(app_id)

        if not zookeeper.exists(self.handle, blacklist_root):
          self.force_create_path(blacklist_root)

        zookeeper.acreate(self.handle, PATH_SEPARATOR.join([blacklist_root, 
          str(txid)]), now, ZOO_ACL_OPEN)

        # Update local cache before notification.
        if app_id in self.blacklist_cache:
          with self.blacklist_cv:
            self.blacklist_cache[app_id].add(str(txid))

        # Copy valid transaction ID for each updated key into valid list.
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

      # Release the locks.
      for lock in lock_list:
        zookeeper.adelete(self.handle, lock)

      if self.is_xg(app_id, txid):
        zookeeper.adelete(self.handle, self.get_xg_path(app_id, txid))
      
      # Remove the transaction paths.
      for item in zookeeper.get_children(self.handle, txpath):
        zookeeper.adelete(self.handle, PATH_SEPARATOR.join([txpath, item]))
        zookeeper.adelete(self.handle, txpath)
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("There was a ZooKeeper exception {0}".format(str( 
        zk_exception)))
    return True

  def reestablish_connection(self):
    """ Checks the connection and resets it as needed. """
    try:
      zookeeper.close(self.handle)
    except zookeeper.ZooKeeperException, close_exception:
      logging.error("Exception when closing ZK connection {0}".\
        format(close_exception))

    self.handle = zookeeper.init(self.host, self.receive_and_notify)

  def run_with_timeout(self, timeout_time, num_retries, function,
    *args):
    """Runs the given function, aborting it if it runs too long. Make sure
       the function does not have side effects.

    Args:
      timeout_time: The number of seconds that we should allow function to
        execute for.
      num_retries: The number of times we should retry the call if we see
        an unexpected exception.
      function: The function that should be executed.
      *args: The arguments that will be passed to function.
    Returns:
      Whatever function(*args) returns if it runs within the timeout window.
    Raises:
      zookeeper.ZooKeeperException: For non connection related zookeeper 
        exceptions and if the function runs out of retries.
    """
    def timeout_handler(_, __):
      """Raises a TimeoutException if the function we want to execute takes
      too long to run.

      Raises:
        TimeoutException: If a SIGALRM is raised.
      """
      raise ZKTimeoutException()
  
    def reset_timer_and_connection():
      """ Resets the timer and establishes a new connection. """
      self.reestablish_connection()
      logging.warning("Retrying with new connection")
      signal.alarm(0)  # turn off the alarm

    if num_retries <= 0:
      raise ZKTransactionException("Failed to run {0}, no more retries"\
        .format(str(function)))

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_time)  # trigger alarm in timeout_time seconds
    try:
      retval = function(*args)
      signal.alarm(0)
    except ZKTimeoutException:
      logging.warning("Call timed out to function {0} with args {1}".\
        format(str(function), str(args)))
      raise ZKTransactionException("Failed to run {0}, timed out"\
        .format(str(function)))
      
    # ZK expected exceptions:
    except zookeeper.NoNodeException, no_node:
      signal.alarm(0)  # turn off the alarm
      raise no_node
    except zookeeper.NodeExistsException, node_exist:
      signal.alarm(0)  # turn off the alarm
      raise node_exist
    # Exception we retry on:
    except zookeeper.ConnectionLossException, conn_loss:
      logging.warning("ZK connection was lost: {0}".format(str((conn_loss))))
      reset_timer_and_connection()
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)
    except zookeeper.ClosingException, conn_loss:
      logging.warning("ZK connection was closed: {0}".format(str((conn_loss))))
      reset_timer_and_connection()
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)
    except zookeeper.InvalidStateException, invalid_state:
      logging.warning("ZK had invalid state: {0}".format(str((invalid_state))))
      reset_timer_and_connection()
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)
    except zookeeper.OperationTimeoutException, op_timeout:
      logging.warning("ZK had an operation timeout: {0}".\
        format(str((op_timeout))))
      reset_timer_and_connection()
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function)
    except zookeeper.SessionExpiredException, ses_expired:
      logging.warning("System exception: {0}".format(ses_expired))
      reset_timer_and_connection()
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)
    # Serious exception we raise:
    except zookeeper.DataInconsistencyException, data_exception:
      signal.alarm(0)  # turn off the alarm before we retry
      raise data_exception
    except zookeeper.BadArgumentsException, bad_args:
      logging.error("Bad args exception: {0}".format(str((bad_args))))
      signal.alarm(0)  # turn off the alarm before we retry
      raise bad_args
    except zookeeper.SystemErrorException, sys_exception:
      logging.error("System exception: {0}".format(sys_exception))
      signal.alarm(0)  # turn off the alarm before we retry
      raise sys_exception
    # Retry any exception we did not foresee:
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("ZK Exception: {0}".format(zk_exception))
      signal.alarm(0)  # turn off the alarm before we retry
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)
    except Exception, general_exception:
      logging.warning("General exception: {0}".format(general_exception))
      signal.alarm(0)  # turn off the alarm before we retry
      return self.run_with_timeout(timeout_time, num_retries - 1, 
        function, *args)

    return retval

  def gc_runner(self):
    """ Transaction ID garbage collection (GC) runner.

    Note: This must be running as separate thread.
    """
    logging.info("Starting GC thread.")

    while self.gc_running:
      if self.connected:
        # Scan each application's last GC time.
        try:
          app_list = zookeeper.get_children(self.handle, APPS_PATH)

          for app in app_list:
            app_id = urllib.unquote_plus(app)
            # App is already encoded, so we should not use 
            # self.get_app_root_path.
            app_path = PATH_SEPARATOR.join([APPS_PATH, app])
            self.try_garbage_collection(app_id, app_path)
        except zookeeper.NoNodeException:
          # There were no nodes for this application.
          pass
        except zookeeper.OperationTimeoutException, ote:
          logging.warning("GC operation timed out while trying to get {0}"\
            " with {1}".format(APPS_PATH, str(ote)))
        except zookeeper.ZooKeeperException, zk_exception:
          logging.error("ZK Exception: {0}".format(zk_exception))
          self.reestablish_connection()
          return

      with self.gc_cv:
        self.gc_cv.wait(GC_INTERVAL)
    logging.info("Stopping GC thread.")

  def try_garbage_collection(self, app_id, app_path):
    """ Try to garbage collect timed out transactions.
  
    Args:
      app_id: The application ID.
      app_path: The application path for which we're garbage collecting.
    Returns:
      True if the garbage collector ran, False otherwise.
    """
    last_time = 0
    try:
      val = zookeeper.get(self.handle, PATH_SEPARATOR.join([app_path, 
        GC_TIME_PATH]), None)[0]
      last_time = float(val)
    except zookeeper.NoNodeException:
      last_time = 0
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("ZK Exception: {0}".format(zk_exception))
      self.reestablish_connection()
      return

    # If the last time plus our GC interval is less than the current time,
    # that means its time to run the GC again.
    if last_time + GC_INTERVAL < time.time():
      gc_path = PATH_SEPARATOR.join([app_path, GC_LOCK_PATH])
      try:
        now = str(time.time())
        zookeeper.create(self.handle, gc_path, 
          now, ZOO_ACL_OPEN, zookeeper.EPHEMERAL)
        try:
          self.execute_garbage_collection(app_id, app_path)
          # Update the last time when the GC was successful.
          now = str(time.time())
          self.update_node(PATH_SEPARATOR.join([app_path, GC_TIME_PATH]), now)
        except Exception as exception:
          logging.error("Warning: GC error {0}".format(str(exception)))
          traceback.print_exc()
          zookeeper.delete(self.handle, gc_path, -1)
      except zookeeper.NodeExistsException:
        # Failed to obtain the GC lock. Try again later.
        pass
      except zookeeper.ZooKeeperException, zk_exception:
        logging.error("ZK Exception: {0}".format(zk_exception))
        self.reestablish_connection()
        return

      return True
    return False

  def get_datastore_groomer_lock(self):
    """ Tries to get the lock for the datastore groomer. 

    Returns:
      True if the lock was obtained, False otherwise.
    """
    try:
      now = str(time.time())
      zookeeper.create(self.handle, DS_GROOM_LOCK_PATH, now, ZOO_ACL_OPEN, 
        zookeeper.EPHEMERAL)
    except zookeeper.NoNodeException:
      logging.debug("Couldn't create path {0}".format(DS_GROOM_LOCK_PATH))
      return False
    except zookeeper.NodeExistsException:
      return False
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("ZK Exception: {0}".format(zk_exception))
      self.reestablish_connection()
      return False
    except zookeeper.SystemErrorException, sys_exception:
      logging.error("System exception: {0}".format(sys_exception))
      self.reestablish_connection()
      return False
    except SystemError, sys_exception:
      logging.error("System error {0}".format(sys_exception))
      self.reestablish_connection()
      return False
    except Exception, exception:
      logging.error("General exception {0}".format(exception))
      self.reestablish_connection()
      return False
      
    return True

  def release_datastore_groomer_lock(self):
    """ Releases the datastore groomer lock. 
   
    Returns:
      True on success, False on system failures.
    Raises:
      ZKTransactionException: If the lock could not be released.
    """
    try:
      zookeeper.delete(self.handle, DS_GROOM_LOCK_PATH, -1)
    except zookeeper.NoNodeException:
      raise ZKTransactionException("Unable to delete datastore groomer lock.")
    except zookeeper.SystemErrorException, sys_exception:
      logging.error("System exception: {0}".format(sys_exception))
      self.reestablish_connection()
      return False
    except SystemError, sys_exception:
      logging.error("System error {0}".format(sys_exception))
      self.reestablish_connection()
      return False
    except Exception, exception:
      logging.error("General exception {0}".format(exception))
      self.reestablish_connection()
      return False
    return True

  def execute_garbage_collection(self, app_id, app_path):
    """ Execute garbage collection for an application.
    
    Args:
      app_id: The application ID.
      app_path: The application path. 
    """
    start = time.time()
    # Get the transaction ID list.
    txrootpath = PATH_SEPARATOR.join([app_path, APP_TX_PATH])
    try:
      txlist = zookeeper.get_children( self.handle, txrootpath)
    except zookeeper.NoNodeException:
      # there is no transaction yet.
      return
    except zookeeper.ZooKeeperException, zk_exception:
      logging.error("ZK Exception: {0}".format(zk_exception))
      self.reestablish_connection()
      return

    # Verify the time stamp of each transaction.
    for txid in txlist:
      if not re.match("^" + APP_TX_PREFIX + '\d', txid):
        logging.debug("Skipping {0} because it is not a transaction.".format(
          txid))
        continue

      txpath = PATH_SEPARATOR.join([txrootpath, txid])

      try:
        #logging.debug("Getting timestamp from transaction ID {0} at path {1}" \
        #  .format(txid, txpath))
        txtime = float(zookeeper.get(self.handle, txpath, None)[0])
        # If the timeout plus our current time is in the future, then
        # we have not timed out yet.
        if txtime + TX_TIMEOUT < time.time():
          self.notify_failed_transaction(app_id, long(txid.lstrip(
            APP_TX_PREFIX)))
      except zookeeper.NoNodeException:
        # Transaction id dissappeared during garbage collection.
        # The transaction may have finished successfully.
        pass
      except zookeeper.ZooKeeperException, zk_exception:
        logging.error("ZK Exception: {0}".format(zk_exception))
        self.reestablish_connection()
        return
    logging.info("Lock GC took {0} seconds.".format(str(time.time() - start)))
