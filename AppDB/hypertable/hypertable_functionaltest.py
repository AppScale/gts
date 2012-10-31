import os
import unittest

import hypertable_interface
from dbconstants import *

# Prereq: Cassandra must be running first 
TEST1_TABLE = "TestTable1"
TEST1_TABLE_SCHEMA = ['c1','c2','c3']

TEST2_TABLE = "TestTable2"
TEST2_TABLE_SCHEMA = ['c1','c2','c3']

TEST3_TABLE = "TestTable3"
TEST3_TABLE_SCHEMA = ['c1','c2','c3']

TEST4_TABLE = "TestTable4"
TEST4_TABLE_SCHEMA = ['c1','c2','c3']

TEST5_TABLE = "TestTable5"
TEST5_TABLE_SCHEMA = ['c1','c2','c3']


class PutTestCase(unittest.TestCase): 
  def setUp(self):
    self.dbstore = hypertable_interface.DatastoreProxy()
    self.dbstore.delete_table(TEST1_TABLE) 
    self.dbstore.create_table(TEST1_TABLE, TEST1_TABLE_SCHEMA)

  def runTest(self):
    row_key = ['a','b','c']
    cell_values = {'a':{'c1':'1','c2':'2','c3':'3'},
                   'b':{'c1':'4','c2':'5','c3':'6'},
                   'c':{'c1':'7','c2':'8','c3':'9'}}
    self.dbstore.batch_put_entity(TEST1_TABLE, row_key, TEST1_TABLE_SCHEMA, 
                               cell_values)

    assert self.dbstore.batch_get_entity(TEST1_TABLE, row_key, TEST1_TABLE_SCHEMA) == cell_values

  def tearDown(self):
    self.dbstore.delete_table(TEST1_TABLE) 

class DeleteTestCase(unittest.TestCase): 
  def setUp(self):
    self.dbstore = hypertable_interface.DatastoreProxy()
    self.dbstore.delete_table(TEST2_TABLE) 
    self.dbstore.create_table(TEST2_TABLE, TEST2_TABLE_SCHEMA)

  def runTest(self):
    row_key = ['a','b','c']
    cell_values = {'a':{'c1':'1','c2':'2','c3':'3'},
                   'b':{'c1':'4','c2':'5','c3':'6'},
                   'c':{'c1':'7','c2':'8','c3':'9'}}
    self.dbstore.batch_put_entity(TEST2_TABLE, row_key, TEST2_TABLE_SCHEMA, 
                               cell_values)

    assert self.dbstore.batch_get_entity(TEST2_TABLE, 
                                      row_key, 
                                      TEST2_TABLE_SCHEMA) == cell_values
    self.dbstore.batch_delete(TEST2_TABLE, ['a','b'])
    assert self.dbstore.batch_get_entity(TEST2_TABLE, 
                                      row_key, 
                                      TEST2_TABLE_SCHEMA) == \
                      {'a':{}, 'b':{}, 'c':{'c1':'7','c2':'8','c3':'9'}}

  def tearDown(self):
    self.dbstore.delete_table(TEST2_TABLE) 

class GetOnNonExistantKey(unittest.TestCase):
  def setUp(self):
    self.dbstore = hypertable_interface.DatastoreProxy()
    self.dbstore.delete_table(TEST3_TABLE) 
    self.dbstore.create_table(TEST3_TABLE, TEST3_TABLE_SCHEMA)

  def runTest(self):
    row_key = ['a','b','c']
    cell_values = {'a':{}, 'b':{}, 'c':{}}
    ret = self.dbstore.batch_get_entity(TEST3_TABLE, row_key, TEST3_TABLE_SCHEMA) 
    assert ret == cell_values

  def tearDown(self):
    self.dbstore.delete_table(TEST3_TABLE) 

class PutOverwriteTestCase(unittest.TestCase): 
  def setUp(self):
    self.dbstore = hypertable_interface.DatastoreProxy()
    self.dbstore.delete_table(TEST4_TABLE) 
    self.dbstore.create_table(TEST4_TABLE, TEST4_TABLE_SCHEMA)

  def runTest(self):
    row_key = ['a','b','c']
    cell_values = {'a':{'c1':'1','c2':'2','c3':'3'},
                   'b':{'c1':'4','c2':'5','c3':'6'},
                   'c':{'c1':'7','c2':'8','c3':'9'}}
    self.dbstore.batch_put_entity(TEST4_TABLE, row_key, TEST4_TABLE_SCHEMA, 
                               cell_values)
    cell_values = {'a':{'c1':'10','c2':'20','c3':'30'},
                   'b':{'c1':'40','c2':'50','c3':'60'},
                   'c':{'c1':'70','c2':'80','c3':'90'}}
    self.dbstore.batch_put_entity(TEST4_TABLE, row_key, TEST4_TABLE_SCHEMA, 
                               cell_values)
  
    assert self.dbstore.batch_get_entity(TEST4_TABLE, row_key, TEST4_TABLE_SCHEMA) == cell_values

  def tearDown(self):
    self.dbstore.delete_table(TEST4_TABLE) 

class RangeTestCase(unittest.TestCase): 
  def setUp(self):
    self.dbstore = hypertable_interface.DatastoreProxy()
    self.dbstore.delete_table(TEST5_TABLE) 
    self.dbstore.create_table(TEST5_TABLE, TEST5_TABLE_SCHEMA)

  def runTest(self):
    row_key = ['a','b','c','d','e','f']
    cell_values = {'a':{'c1':'1','c2':'2','c3':'3'},
                   'b':{'c1':'4','c2':'5','c3':'6'},
                   'c':{'c1':'7','c2':'8','c3':'9'},
                   'd':{'c1':'10','c2':'11','c3':'12'},
                   'e':{'c1':'13','c2':'14','c3':'15'},
                   'f':{'c1':'16','c2':'17','c3':'18'}}
    expected = [{'a':{'c1':'1','c2':'2','c3':'3'}},
                   {'b':{'c1':'4','c2':'5','c3':'6'}},
                   {'c':{'c1':'7','c2':'8','c3':'9'}},
                   {'d':{'c1':'10','c2':'11','c3':'12'}},
                   {'e':{'c1':'13','c2':'14','c3':'15'}},
                   {'f':{'c1':'16','c2':'17','c3':'18'}}]

    self.dbstore.batch_put_entity(TEST5_TABLE, row_key, TEST5_TABLE_SCHEMA, 
                               cell_values)
    column_names = TEST5_TABLE_SCHEMA
    limit = 10
    offset = 0
    startrow = 'a'
    endrow = 'f'
    start_in = True
    end_in = True
    assert self.dbstore.range_query(TEST5_TABLE, column_names, 
                                 startrow, endrow, 
                                 limit, offset, start_in, end_in) == expected

    keys_only = True
    expected = ['a','b','c','d','e','f']
    assert self.dbstore.range_query(TEST5_TABLE, column_names, 
                                 startrow, endrow, 
                                 limit, offset, start_in, 
                                 end_in, keys_only) == expected

    keys_only = False
    start_in = False
    expected = [{'b':{'c1':'4','c2':'5','c3':'6'}},
                   {'c':{'c1':'7','c2':'8','c3':'9'}},
                   {'d':{'c1':'10','c2':'11','c3':'12'}},
                   {'e':{'c1':'13','c2':'14','c3':'15'}},
                   {'f':{'c1':'16','c2':'17','c3':'18'}}]
    assert self.dbstore.range_query(TEST5_TABLE, column_names,
                                 startrow, endrow, limit, 
                                 offset, start_in, end_in) == expected

    expected = [{'b':{'c1':'4','c2':'5','c3':'6'}},
                   {'c':{'c1':'7','c2':'8','c3':'9'}},
                   {'d':{'c1':'10','c2':'11','c3':'12'}},
                   {'e':{'c1':'13','c2':'14','c3':'15'}}]

    end_in = False
    assert self.dbstore.range_query(TEST5_TABLE, column_names,
                                 startrow, endrow, limit, 
                                 offset, start_in, end_in) == expected

    expected = [{'b':{'c1':'4','c2':'5','c3':'6'}},
                   {'c':{'c1':'7','c2':'8','c3':'9'}},
                   {'d':{'c1':'10','c2':'11','c3':'12'}},
                   {'e':{'c1':'13','c2':'14','c3':'15'}}]
    start_in = True
    end_in = True
    startrow = 'b'
    endrow = 'e'
    assert self.dbstore.range_query(TEST5_TABLE, column_names,
                                 startrow, endrow, limit, offset, 
                                 start_in, end_in) == expected

    expected = [{'b':{'c1':'4','c2':'5','c3':'6'}},
                   {'c':{'c1':'7','c2':'8','c3':'9'}}]
    limit = 2    
    assert self.dbstore.range_query(TEST5_TABLE, column_names,
                                 startrow, endrow, limit, 
                                 offset, start_in, end_in) == expected

    expected = [{'c':{'c1':'7','c2':'8','c3':'9'}}]
    offset = 1
    assert self.dbstore.range_query(TEST5_TABLE, column_names,
                                 startrow, endrow, limit, 
                                 offset, start_in, end_in) == expected
     
  def tearDown(self):
    self.dbstore.delete_table(TEST5_TABLE) 


if __name__ == "__main__":
  unittest.main()
  
