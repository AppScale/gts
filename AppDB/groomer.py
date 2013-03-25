""" This process grooms the datastore cleaning up old state and 
calculates datastore statistics. 
"""

import threading

import tornado.httpserver
import tornado.ioloop
import tornado.web

from google.appengine.ext import db
from google.appengine.ext.db import stats

class DatastoreGroomer(threading.Thread):
  """ Scans the entire database for each application. """
 
  # The amount of seconds between polling to get the groomer lock.
  LOCK_POLL_PERIOD = 3600
 
  def __init__(self, zk, datastore):
    """ Constructor. 

    Args:
      zk: ZooKeeper client.
      datastore: The datastore client.
    """
    threading.Thread.__init__(self)
    self.zk = zk
    self.datastore = datastore

  def run(self):
    """ Starts the main loop of the groomer thread. """
    while True:
      sleep(self.LOCK_POLL_PERIOD)
      if self.get_groomer_lock():
        self.run_groomer()

  def get_groomer_lock(self):
    """ Tries to acquire the lock to the datastore groomer. 
  
    Returns:
      True on success, False otherwise.
    """
    return self.zk.get_datastore_groomer_lock()
 
  def run_groomer(self):
    """ Runs the grooming process.
    """
    pass
