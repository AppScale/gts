#!/usr/bin/env python
# Programmer: Navraj Chohan

import dbconstants
import pycassa
import os 
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../cassandra"))  
import prime_cassandra

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))  
import helper_functions 

class FakeCassClient():
  """ Fake cassandra client class for mocking """
  def __init__(self):
    return
  def multiget_slice(self, rk, path, slice_predicate, consistency):
    return {}

class FakePool():
  """ Fake cassandra connection pool for mocking """
  def get(self):
    return FakeCassClient()
  def return_conn(self, client):
    return 

class FakeColumnFamily():
  """ Fake column family class for mocking """
  def __init__(self):
    return
  def batch_insert(self, multi_map):
    return
  def get_range(self, start='', finish='', columns='', row_count='', 
                read_consistency_level=''):
    return {}

class FakeSystemManager():
  """ Fake system manager class for mocking """
  def __init__(self):
    return
  def drop_column_family(self, keyspace, table_name):
    return
  def drop_keyspace(self, keyspace):
    return
  def create_keyspace(self, keyspace, strategy, rep_factor):
    return
  def create_column_family(self, keysapce, col_fam, 
                           comparator_type=pycassa.system_manager.UTF8_TYPE):
    return
  def close(self):
    return

class TestCassandraPrimer(unittest.TestCase):
  def test_primer(self):
    flexmock(helper_functions) \
        .should_receive('read_file') \
        .and_return('127.0.0.1')

    flexmock(pycassa.system_manager).should_receive("SystemManager") \
        .and_return(FakeSystemManager())
    
    assert prime_cassandra.create_keyspaces(1)
 
  def test_bad_arg(self):
    flexmock(helper_functions) \
       .should_receive('read_file') \
       .and_return('127.0.0.1')

    flexmock(pycassa.system_manager).should_receive("SystemManager") \
       .and_return(FakeSystemManager())
   
    #prime_cassandra.create_keyspaces(-1)
    self.assertRaises(dbconstants.AppScaleBadArg, 
                    prime_cassandra.create_keyspaces, -1)

if __name__ == "__main__":
  unittest.main()    
