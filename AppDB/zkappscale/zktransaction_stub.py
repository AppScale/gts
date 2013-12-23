#!/usr/bin/python
#
# Distributed id and lock service for transaction support.
# Written by Yoshi <nomura@pobox.com>
import random
#import zookeeper
import threading
import time
import urllib
import weakref
import re
import traceback
from dbconstants import *

ZOO_ACL_OPEN = [{"perms":0x1f, "scheme":"world", "id" :"anyone"}]
LOCK_TIMEOUT = 30 # seconds
TX_TIMEOUT = 30 # seconds
GC_INTERVAL = 30 # seconds
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

# This class take care of transaction id, lock and GC of transaction

class ZKTransactionException(Exception):
  TYPE_UNKNOWN = 0
  TYPE_NO_CONNECTION = 1
  TYPE_INVALID = 2
  TYPE_EXPIRED = 3
  TYPE_DIFFERENT_ROOTKEY = 4

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

  def __init__(self, host = DEFAULT_HOST, startgc = True):
    # for the connection
    self.connectcv = threading.Condition()
    self.connected = False
    #self.handle = zookeeper.init(host, self.__receiveNotify)
    # for gc
    self.gcrunning = False
    self.gccv = threading.Condition()
    self.__rollbackFunc = None

  def get_transaction_id(self, app_id, is_xg=False):
    """ Get new transaction ID for transaction.

    This function only create transaction ID, and you must lock
    particular root entity using acquireLock().
    The ID is long number.
    The transaction will expire in 30 seconds.
    """
    return random.randint(0,100000000)
    
  def check_transaction(self, app_id, txid):
    """ Get status of specified transaction.

    Returns: True - If transaction is alive.
    Raises: ZKTransactionException - If transaction is timeout or not exist.
    """
    return True

  def acquire_lock(self, app_id, txid, entity_key = GLOBAL_LOCK_KEY):
    """ Acquire lock for transaction.

    You must call getTransactionID() first to obtain transaction ID.
    You could call this method anytime if the root entity key is same.
    If you could not get lock, this returns False.
    """
    return True

  def get_update_key_list(self, app_id, txid):
    """ Get the list of updated key.

    This method just return updated key list which is registered using
    registUpdatedKey().
    This method doesn't check transaction state, so
    you can use this method for rollback.
    """
    return []
  def release_lock(self, app_id, txid, key = None):
    """ Release acquired lock.

    You must call acquireLock() first.
    if the transaction is not valid or it is expired, this raises Exception.
    After the release lock, you could not use transaction ID again.
    If there is no lock, this method returns False.
    """
    return True
   
  def is_blacklisted(self, app_id, txid, entity_key = None):
    """ This validate transaction id with black list.

    The PB server logic should use getValidTransactionID().
    """
    return False

  def get_valid_transaction_id(self, app_id, target_txid, entity_key):
    """ This returns valid transaction id for the entity key.

    If the specified transaction id is black-listed,
    this returns latest valid transaction id.
    If there is no valid transaction id, this returns 0.
    """
    return long(target_txid)

  def register_updated_key(self, app_id, current_txid, target_txid, entity_key):
    """ Regist valid transaction id for entity.

    target_txid must be the latest valid transaction id for the entity.
    """
    return

  def notify_failed_transaction(self, app_id, txid):
    """ Notify failed transaction id.

    This method will add the transaction id into black list.
    After this call, the transaction becomes invalid.
    """
    return 

  def close(self):
    """ Stub function for closing all ZooKeeper connections. """
    return


  def increment_and_get_counter(self, path, value):
    """ Stub function for incrementing a path by a given value. 
    
    Args: 
      path: A str (ignored)
      value: An int, the amount to increase by.
    Returns: 
      A tuple: (old_value, old_value + value).
    """
    fake_value = int(time.time() * 1000)
    return (fake_value, fake_value + value)

  def get_datastore_groomer_lock(self):
    """ Tries to get the lock for the datastore groomer. 

    Returns:
      True if the lock was obtained, False otherwise.
    """
    return True

