# Interface with Cassandra (AppScale)
__author__="Soo Hwan Park"
__date__ ="$2009. 3. 2  10:23:41$"

import Cassandra
from ttypes_cassandra import *
import string
import sys, os
import base64   # base64    2009.04.16 

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

ERROR_CASSANDRA = "CA_ERROR:"
DB_LOCATION = "localhost"
DB_PORT = 9160    # 9090

# use 1 Table and 1 ColumnFamily in Cassandra
TABLE_NAME = "AppScale"
COLUMN_FAMILY="appscale"
MAX_KEYS = 1000
KEY_REPOSITORY="__keys"	# special key for storing keys information. it has two columns (num, names)
TABLE_PREFIX="__table_" # special keys for storing a table information. it has two columns (num, names)
SCHEMA_COLUMN="schema" 

######################
# version
######################
def version(): 
  return "version 0.1.0"   	

######################
# get_keys
######################  
def get_keys(): 
  client, transport, protocol = __setup_connection()
  res = __get_keys(client,COLUMN_FAMILY) 
  __close_connection(transport)
  return res

######################
# get_keys_in_table
######################  
def get_keys_in_table(tablename): 
  client, transport, protocol = __setup_connection()
  res = __get_keys_in_table(client, COLUMN_FAMILY, tablename) 
  __close_connection(transport)
  return res

######################
# create_table
######################    
def create_table(table_name, schema ):
  list = [ERROR_CASSANDRA]
  key = table_name+"_schema"
  
  client, transport, protocol = __setup_connection()
  str_schema = string.join(schema, ",")

  client.insert(TABLE_NAME, key, COLUMN_FAMILY + ":schema", str_schema, 1,)
	 
  # add key in table 
  __add_key(client, COLUMN_FAMILY, key) 
  __add_key_in_table(client, COLUMN_FAMILY, table_name, key) 
  __close_connection(transport)
  return list

######################
# get table schema .. 
######################
def get_schema(table_name):
  list = [ERROR_CASSANDRA]
  key = table_name+"_schema"
      
  client, transport, protocol = __setup_connection()
  try:
    schema = client.get_column(TABLE_NAME, key, COLUMN_FAMILY+":schema")
    columns = schema.value.split(",")
    for column in columns:
      list.append(column)
  except :
    list[0] += "get_schema failed"

  __close_connection(transport)
  return list

######################
# get_row_count.. 
######################
def get_row_count(table_name):
  list = [ERROR_CASSANDRA]
  keyinfo = {}
  _tablename = TABLE_PREFIX + table_name

  value = 0
  client, transport, protocol = __setup_connection()
  
  try:
    keyinfo = client.get_slice(TABLE_NAME, _tablename, COLUMN_FAMILY, 1, 100)
  except CassandraException, cass:
    __close_connection(transport)
    list += [value]
    return list    
  __close_connection(transport)

  for info in keyinfo:
    if info.columnName == "num":
      value = int(info.value)-1 	# decrement by 1 (schema) 
  list += [value]
  return list
  
######################
# get_row.. 
######################  
def get_row(table_name, key, max_versions = 1):
  list = [ERROR_CASSANDRA]
  family = COLUMN_FAMILY

  client, transport, protocol = __setup_connection()
  try: 
    schema = client.get_column(TABLE_NAME, table_name+"_schema", COLUMN_FAMILY+":schema")
    columns = schema.value.split(",")
    for column in columns:
      columnFamily_column = family + ":" + column
      column = client.get_column(TABLE_NAME, key, columnFamily_column )
      list.append(column.value)
    
  except CassandraException, cass:
    __close_connection(transport)
    list += ["Not exist"]
    return list    
  __close_connection(transport)
  return list

######################
# put_entity
######################    
def put_entity(table_name, row_key, column_names, cell_values):
  list = [ERROR_CASSANDRA]
  family = COLUMN_FAMILY

  if len(column_names) != len(cell_values):
    IOError( "Number of values does not match the number of columns")
    
  if __table_exist( table_name) == 0:
    create_table(table_name, column_names)

  client, transport, protocol = __setup_connection()

  for ii in range(0,len(column_names)):
    columnFamily_column = family + ":" +  column_names[ii]
    value = cell_values[ii]
    if column_names[ii] == "Encoded_Entity":
      value = base64.b64encode(value)
      
    client.insert(TABLE_NAME, row_key, columnFamily_column, value, 1,)

  __add_key(client, family, row_key) 
  __add_key_in_table(client, family, table_name, row_key)

  __close_connection(transport)
  list += "0"
  return list

######################
# get_entity
######################   
def get_entity(table_name, row_key, column_names):
  list = [ERROR_CASSANDRA]
  family = COLUMN_FAMILY
  client, transport, protocol = __setup_connection()
  try:
    for ii in column_names:
      columnFamily_column = family + ":" + ii
      column = client.get_column(TABLE_NAME, row_key, columnFamily_column )
      value = column.value
      print value
      if ii == "Encoded_Entity":
        value = base64.b64decode(column.value)
      list += [value]
  except :
    list[0] += " Not found"
  
  __close_connection(transport)
  return list

######################
# delete_row
###################### 
def delete_row(table_name, row_key):
  list = [ERROR_CASSANDRA]
  family = COLUMN_FAMILY + ":*"
  return list

  client, transport, protocol = __setup_connection()
  # remove(self, tablename, key, columnFamily_column):
  # current remove in Cassandra has a problem
  # cannot delete a specific column
  # if remove row, that row_key cannot be reused.
  client.remove(TABLE_NAME, row_key, family)
  __remove_key(client, family, row_key)
  __remove_key_in_table(client, family, table_name, row_key)
  __close_connection(transport)
  return list

######################
# get_table
###################### 
def get_table(table_name, column_names = []):
  list = [ERROR_CASSANDRA]
  family = COLUMN_FAMILY

  try:
    client, transport, protocol = __setup_connection()
    keys = __get_keys_in_table(client, family, table_name)
    for key in keys :
      if key == table_name+"_schema":
        continue  # this is schema information 

      # change this get_entity .. because of orders of values 
      # otherwise .. get_schema and reorder the values .. 
      # save to dictionary first and return.. 
      row = client.get_slice(TABLE_NAME, key, family, 1, 100)
      res = {}
      for column in row:
        #save to dict .. 
        value = column.value
        if column.columnName == "Encoded_Entity":
          value = base64.b64decode(value)
        res[column.columnName] = value
			
      if len(column_names) > 0 :
        for name in column_names :
          list.append(res[name])
      else:
        list += res.values()

  except Exception, e:
    print e
    
  __close_connection(transport)
  return list

# private methods 

######################
# __setup_connection
###################### 
def __setup_connection():
  global DB_LOCATION
  transport = TSocket.TSocket(DB_LOCATION, DB_PORT)
  transport = TTransport.TBufferedTransport(transport)
  protocol = TBinaryProtocol.TBinaryProtocol(transport)
  client = Cassandra.Client(protocol)
  transport.open()
  return client, transport, protocol

######################
# __close_connection
###################### 
def __close_connection(transport): # Close connection ..
  transport.close()
  return

######################
# __table_exist
###################### 
def __table_exist(table_name): # Cassandra doesn't support this
  column_list = get_schema(table_name) 
  if len(column_list) < 2 :
    return 0
  else :
    return 1

# new method for Cassandra

######################
# __get_keys
###################### 
def __get_keys(client, family):
  try:
    key_info = client.get_slice(TABLE_NAME, KEY_REPOSITORY, family, 1, 100)
    num_keys = 0
    key_string = ""
    for info in key_info:
      if info.columnName == "num":
        num_keys = int(info.value)
      elif info.columnName == "names" :
        key_string += info.value
    key_list = key_string.split(",")
    return key_list
  except CassandraException, cass:
    print cass.error
    return []

######################
# __add_key
###################### 
def __add_key(client, family, key):
  try:
    key_info = client.get_slice(TABLE_NAME, KEY_REPOSITORY, family, 1, 100)
    num_keys = 0
    key_string = ""
    for info in key_info:
      if info.columnName == "num":
        num_keys = int(info.value)
      elif info.columnName == "names" :
        key_string = info.value
  	
    # check if it exists
    key_list = key_string.split(',')
    if key in key_list:
      return; 

    key_list.append(key)
    num_keys = len(key_list)
    key_string = string.join(key_list,',')
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":num", str(num_keys), 1,)
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":names", key_string, 1,)
    return
  except CassandraException, cass:
    # if there is no key_info at all .. 
    # insert default values .. 
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":num", str(1), 1,)
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":names", key, 1,)
  return 

######################
# __remove_key
###################### 
def __remove_key(client, family, key):
  key_info = client.get_slice(TABLE_NAME, KEY_REPOSITORY, family, 1, 100)
  num_keys = 0
  key_string = ""
  for info in key_info:
    if info.columnName == "num":
      num_keys = int(info.value)
    elif info.columnName == "names" :
      key_string = info.value

  # check if it exists
  key_list = key_string.split(',')
  if key in key_list:
    key_list.remove(key)
    num_keys = len(key_list)
    key_string = string.join(key_list,',')
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":num", str(num_keys), 1,)
    client.insert(TABLE_NAME, KEY_REPOSITORY, COLUMN_FAMILY+":names", key_string, 1,)
  return

######################
# __get_keys_in_table
###################### 
def __get_keys_in_table(client, family, tablename):
  _tablename = TABLE_PREFIX + tablename
  key_info = client.get_slice(TABLE_NAME, _tablename, family, 1, 10)
  num_keys = 0
  key_string = ""
  for info in key_info:
    if info.columnName == "names":
      key_string = info.value
    elif info.columnName == "num":
      num_keys = int(info.value)
  key_list = key_string.split(",")
  return key_list

######################
# __add_key_in_table
###################### 
def __add_key_in_table(client, family, tablename, key):
  _tablename = TABLE_PREFIX + tablename
  try:
    key_info = client.get_slice(TABLE_NAME, _tablename, family, 1, 10)
    num_keys = 0
    key_string = ""
    for info in key_info:
      if info.columnName == "num":
        num_keys = int(info.value)
      elif info.columnName == "names" :
        key_string = info.value
  
    # check if it exists
    key_list = key_string.split(',')
    if key in key_list:
      return; 
  
    key_list.append(key)
    num_keys = len(key_list)
    key_string = string.join(key_list, ',')
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":num", str(num_keys), 1,)
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":names", key_string, 1,)
  
  except CassandraException, cass :  # if there is no key_info at all .. 
    # insert default values .. 
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":num", str(1), 1,)
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":names", key, 1,)
  return 

######################
# __remove_key_in_table
###################### 
def __remove_key_in_table(client, family, tablename, key):
  _tablename = TABLE_PREFIX + tablename
  key_info = client.get_slice(TABLE_NAME, _tablename, family, 1, 100)
  num_keys = 0
  key_string = ""
  for info in key_info:
    if info.columnName == "num":
      num_keys = int(info.value)
    elif info.columnName == "names" :
      key_string = info.value

  # check if it exists
  key_list = key_string.split(',')
  if key in key_list:
    key_list.remove(key)
    num_keys = len(key_list)
    key_string = string.join(key_list, ',')
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":num", str(num_keys), 1,)
    client.insert(TABLE_NAME, _tablename, COLUMN_FAMILY+":names", key_string, 1,)
  return

