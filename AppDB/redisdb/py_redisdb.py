#Writter by Navyasri Canumalla

import sys
import base64
import redis
from dbinterface import *
import sqlalchemy.pool as pool
import appscale_logger


ERROR_DEFAULT = "DB_ERROR:"
DEBUG = False
FILENAME = "/var/log/appscale/redis.out"
FILE = open(FILENAME,"w",0)

class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-redis")):
    self.logger = logger
    self.masterConn = self.__createMasterConnection()
    self.slaveConn = self.__createLocalConnection()
  #Writes go through the Master  
  def create_table(self, table_name,columns):
    
    elist = [ERROR_DEFAULT]
    if DEBUG: FILE.write("Creating table\n")
    if (not table_name) or (not columns):
          elist[0] += "Null columns or table_name"
          return elist

    #keep track of table schema
    cols = ':'.join(columns)
    key = 'schema/'+table_name

    conn = self.masterConn
    if(not conn):
     if DEBUG: FILE.write("Connection creation failed, Master: %s\n" % conn)
    if(not conn.exists(key)): 
       conn.set(key,cols) 
       if DEBUG: FILE.write("Table columns: %s ,table: %s \n" %(cols, key))
       return 1  
    else:
       elist[0] += "Table already exists"
       
       if DEBUG: FILE.write("Table creation error : %s\n" %(str(elist)))
       return elist

  # Reads are handled by slaves.   
  def get_entity(self, table_name, row_key, column_names):
	
       elist = [ERROR_DEFAULT]
       if DEBUG: FILE.write("Get the row of table %s\n" %table_name)
       if (not row_key) or (not table_name):
          elist[0] += "Null row_key or table_name"
          if DEBUG: FILE.write("Null row_key or table_name\n")
          return elist

       conn = self.slaveConn
       row_key = table_name+'/'+row_key
       data = []             

       if(not conn.exists(row_key)):
          elist[0] += "data not found for particular row and column for table name: %s on row key: %s, with columns: %s and  elist: %s"%(table_name, row_key, str(column_names), str(elist))

          if DEBUG: FILE.write("data not found for particular row and column for table name: %s on row key: %s, with columns: %s and  elist: %s \n"%(table_name, row_key, str(column_names), str(elist)))
          return elist
       data = conn.hmget(row_key,column_names)
       for d in data:
          elist.append(str(d))
       if DEBUG: FILE.write("Data retrieved:%s\n" %(str(elist)))
       return elist
	
  def get_schema(self,table_name):			 
	
      elist = [ERROR_DEFAULT]
      if DEBUG: FILE.write("get schema of table %s \n" %table_name)

      if (not table_name):
          elist[0] += "Null table_name"
          if DEBUG: FILE.write("%s \n" %(str(elist)))
          return elist

      conn = self.slaveConn
      key = 'schema/'+table_name
      if (not conn.exists(key)):
	elist[0] +="table not found" 
      else: 
        cols = conn.get(key)
        schema= cols.split(':')
        for i in schema:
         elist.append(str(i))
      if DEBUG: FILE.write("key to get table columns: %s Error: %s \n" %(key, str(elist)))
      return elist
  
  # Stored in Redis as a hash entry with key as table name+rowkey
  def put_entity(self, table_name, row_key, column_names, cell_values):

     elist = [ERROR_DEFAULT]
     if DEBUG: FILE.write("Put table %s \n"%table_name)
     if (not row_key) or (not table_name):
       elist[0] += "Null row_key or table_name"
       if DEBUG: FILE.write("%s \n" %(str(elist)))
       return elist

     if len(column_names) != len(cell_values):
       elist[0] += "Amount of columns did not equal the amount of data"
       if DEBUG: FILE.write("Column_names: %s, Cell_values: %s, Error:%s \n" %(str(column_names), str(cell_values),  str(elist)))
       return elist
    
     conn = self.masterConn
     fields = {}
     key = 'schema/'+table_name
     old_data = []
     if(not conn.exists(key)):
        self.create_table(table_name,column_names)
        columns = column_names
     else:
        columns = self.get_schema(table_name)[1:]
        old_data = self.get_entity(table_name,row_key,columns)

     for i in range(0,len(column_names)):
	fields[column_names[i]] = cell_values[i]
     if DEBUG: FILE.write("fields:%s" %(str(fields)))
     row_key = table_name+'/'+row_key
     if(conn.hmset(row_key,fields)):
       if DEBUG: FILE.write("Successful Put for row_key:%s \n" %row_key);   
     
     elist.append("0")    
     return elist
 
  def delete_table(self, table_name):
      elist = [ERROR_DEFAULT]
      if DEBUG: FILE.write("Deleting table %s \n" %table_name)
      if not table_name:
          elist[0] += "Null table_name"
          if DEBUG: FILE.write("Deleting table error:%s \n" %(str(elist)))
          return elist

      conn = self.masterConn
      if(not conn.exists('schema/'+table_name)):
          elist[0] += "Table %s does not exist." % table_name
          if DEBUG: FILE.write("Table %s does not exist. \n" % table_name)
          return elist
      pattern = table_name+'/'
      rows = conn.keys(pattern)
      for r in rows:
        conn.delete(r)
      if(conn.delete('schema/'+table_name)):
        if DEBUG: FILE.write("successful delete of table %s\n" %table_name)
      elist.append("0")
      return elist

  def delete_row(self, table_name, row_key):
      elist = [ERROR_DEFAULT]

      if (not row_key) or (not table_name):
          elist[0] += "Null row_key or table_name"
          if DEBUG: FILE.write("Row_key:%s, table_name:%s, error:%s  \n" %(row_key, table_name, str(elist)))
          return elist

      conn = self.masterConn
      row_key = table_name+'/'+row_key
      if(conn.delete(row_key)):
        if DEBUG: FILE.write("successful delete of row: %s \n" %row_key)
      elist.append("0")
      return elist

  def get_table(self, table_name, column_names = []):

      elist = [ERROR_DEFAULT]
      if DEBUG: FILE.write("Getting table data for table %s \n"%table_name)
      if (not table_name):
          elist[0] += "Null table_name"
          if DEBUG: FILE.write("Getting table data error:%s \n"%(str(elist)))
          return elist

      conn = self.slaveConn
      if(not conn.exists('schema/'+table_name)):
          if DEBUG: FILE.write("table does not exist, returns empty table\n")
          return elist
      else:
         columns = self.get_schema(table_name)[1:]
         data = []
         pattern = table_name+'/*' 
         rows = conn.keys(pattern)
      
         for r in rows:
            data.append(conn.hmget(r,columns))
         for d in data:
             for i in d:
                elist.append(str(i))
      if DEBUG: FILE.write("Table data is %s \n" %(str(elist)))
      return elist


  def __createLocalConnection(self):
    return redis.Redis(host=self.get_local_ip(), port= 6379, db=0)
    
  def __createMasterConnection(self):
    return redis.Redis(host=self.get_master_ip(), port= 6379, db=0)
     
 
