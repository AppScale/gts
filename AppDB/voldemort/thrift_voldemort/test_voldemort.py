#!/usr/bin/env python
import os,sys
import string, cgi
sys.path.append("/usr/share/python-support/python-support/SOAPpy")
sys.path.append("/var/lib/python-support/python2.5/")
import SOAPpy
import time
import socket
import datetime
import os
import cgitb; 
import getopt
sys.path.append("/root/cassandra/client")
import py_cassandra
import pickle

"""
def version(): checked 
__add_key: works 
def test_insert(key, family, column, value): checked 
def create_table(table_name, schema ): works 
def get_schema(table_name): works 
def get_row_count(table_name):works
def get_keys(family): works 
def get_row(table_name, key, max_versions = 1): works 
def put_entity(table_name, row_key, column_names, cell_values): works
def get_entity(table_name, row_key, column_names):  works

def delete_row(table_name, row_key):  works 
def get_table(table_name, column_names = []):

# now insert() and remove() are fine. 
"""



def main(argv):
  print "************************* cassandra test START" 
  print py_cassandra.version()
  
  users_columns = ["email","pw","date_creation","date_change","date_last_login","applications","appdrop_rem_token", "appdrop_rem_token_exp","visit_cnt",  "cookie", "cookie_ip","cookie_exp", "cksum"]
  users_values = ["suwanny@gmail.com", "11", "2009", "2009", "2009", "bbs", "xxx", "xxx","1", "yyy", "0.0.0.0", "2009", "zzz"]
  
  apps_columns = ["name", "version","owner","admins_list","host","port","creation_date",  "last_time_updated_date", "yaml_file",  "cksum", "num_entries"]
  apps_values = ["name",  "version","owner","admins_list","host","port","creation_date",  "last_time_updated_date", "yaml_file",  "cksum", "num_entries"]
    
  TABLE_NAME = "AppScale"
  COLUMN_FAMILY="appscale"
  TABLE= "AppScale"
  FAMILY="appscale"
  KEY = "test"
  COLUMN = "column1"
  VALUE = "value1"
  
  
  # key, family, column, value 
  # print py_cassandra.test_insert(KEY, COLUMN, VALUE) 
  # family(table_name), row_key 
  # print py_cassandra.get_row(FAMILY, KEY)
   
  #create table .. : tablename(family), schema list
  
  #print py_cassandra.create_table("apps", apps_columns)
  #print py_cassandra.get_schema("apps")
  #print py_cassandra.create_table("users", users_columns)
  #print py_cassandra.get_schema("users")
  #print py_cassandra.get_row_count("apps") [1:]
  #print py_cassandra.get_row_count("users") [1:]
   
  
  #print py_cassandra.put_entity("users", "users_suwanny", users_columns, users_values) 
  #print py_cassandra.get_row("users", "users_suwanny")[1:]
  
  print "before keys", py_cassandra.get_keys()
  
  column_names = ["name", "email", "date_creation", "column3"] 
  values = ["value1", "value2","value3", "value4"]
  values2 = ["value2-1", "value2-2","value2-3", "value2-4"]
  table = "temp" 
  key = "test_1"
  key2 = "test_2"

  #print "create table", py_cassandra.create_table(table, column_names)
  #print "get_schema", py_cassandra.get_schema(table)[1:]
  #print "row_count", py_cassandra.get_row_count(table)[1:]
  #print "put_entity", py_cassandra.put_entity(table, key, column_names, values) 
  #print "put_entity", py_cassandra.put_entity(table, key2, column_names, values2) 
  #print "get_row", py_cassandra.get_row(table, key)[1:] 
  #print "delete_row", py_cassandra.delete_row(table, key) 
  #print "get_entity", (py_cassandra.get_entity(table, key2, column_names))[1:] 
  
  #print "get_table", py_cassandra.get_table(table, column_names)[1:] 
  print "put_entity", py_cassandra.put_entity("temp2", "test3", column_names, values) 
  print "get_schema", py_cassandra.get_schema("temp2")[1:]
  print "get_table", py_cassandra.get_table("temp2", column_names)[1:] 
  # everything is sorted by alphabet order ..   
    
  print "after keys", py_cassandra.get_keys()
  print "************************* cassandra test END" 
  
if __name__ == "__main__":
    try:
        main(sys.argv)
    except:
        print "internal error occurred"
        raise
