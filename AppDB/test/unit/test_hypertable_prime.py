#!/usr/bin/env python
# Programmer: Navraj Chohan

import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../hypertable/"))  
from hypertable import thriftclient
import hypertable_interface
import py_hypertable
import prime_hypertable

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import helper_functions

class FakeHypertableClient():
  """ Fake hypertable client class for mocking """
  def __init__(self):
    return
  def namespace_open(self, NS):
    return "NS"
  def get_cells(self, ns, table_name, scane_spec):
    return []
  def drop_table(self, ns, table_name, x):
    return None
  def mutator_open(self, ns, table_name, x, y):
    return None
  def mutator_set_cells(self, mutator, cell_list):
    return None
  def mutator_close(self, mutator):
    return None
  def create_table(self, table, columns):
    return None
 
class TestHypertable(unittest.TestCase):
  def testConstructor(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(py_hypertable).should_receive("DatastoreProxy") \
        .and_return(FakeHypertableClient())

    prime_hypertable.create_app_tables()

if __name__ == "__main__":
  unittest.main()    
