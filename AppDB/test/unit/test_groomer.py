#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.ext import db

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import groomer
from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException

class TestGroomer(unittest.TestCase):
  """
  A set of test cases for the datastore groomer thread.
  """
  def test_init(self):
    datastore = flexmock()
    zookeeper = flexmock()
    dsg = groomer.DatastoreGroomer(zookeeper, datastore) 

  def test_get_groomer_lock(self):
    datastore = flexmock()
    zookeeper = flexmock()
    zookeeper.should_receive("get_datastore_groomer_lock").and_return(True)
    dsg = groomer.DatastoreGroomer(zookeeper, datastore)
    self.assertEquals(True, dsg.get_groomer_lock())

if __name__ == "__main__":
  unittest.main()    
