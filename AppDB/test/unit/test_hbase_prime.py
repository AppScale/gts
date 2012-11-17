#!/usr/bin/env python
# Programmer: Navraj Chohan

import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../hbase/"))  
import py_hbase
import prime_hbase

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import helper_functions

class FakeHBaseClient():
  """ Fake hbase client class for mocking """
  def __init__(self):
    return
  def getRowsWithColumns(self, table_name, row_keys, column_list):
    return "NS"
  def mutateRows(self, table_name, all_mutations):
    return []
  def disableTable(self, table_name):
    return 
  def deleteTable(self, table_name):
    return
  def create_table(self, table_name, columns):
    return
  def scannerOpenWithStop(self, table_name, start_key, end_key, col_names):
    return []
  def scannerGetList(self, scanner, rowcount):
    return []
  def scannerClose(self, scanner):
    return
 
class TestHBasePrimer(unittest.TestCase):
  def testPrimer(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(py_hbase).should_receive("DatastoreProxy") \
        .and_return(FakeHBaseClient())
    
    prime_hbase.create_table('table', ['a','b','c'])
if __name__ == "__main__":
  unittest.main()    
