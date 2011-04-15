# Author: Navraj Chohan
#import sys
import os
import MySQLdb
#import _mysql
#import sqlalchemy.pool as pool
from dbinterface import *
import appscale_logger
import threading
import time
#MySQLdb = pool.manage(MySQLdb)
TIMEOUT = 30
# Time till next gc of connections
GC_TIME = 120
ROW_KEY = "mysql__row_key__"
ERROR_MY = "DB_ERROR:"
#DB_LOCATION = "appscale-image"
USE_DATABASE = "appscale"
DB_LOCATION = "127.0.0.1"
#DB_PORT = 3306
DEBUG = False
transDict = {}
transDict_lock = threading.Lock()
last_gc_time = 0
class DatastoreProxy(AppDBInterface):

  def __init__(self, log = appscale_logger.getLogger("datastore-mysql")):
    self.logger = log
    self.client = None
    self.transactionsOn = False
    self.tableCache = []


  def commit(self, txnid):
    elist = [ERROR_MY]
    try:
      cursor, client = self.__get_connection(txnid)
      cursor.close()
      client.commit()
      self.__close_connection(txnid) 
    except MySQLdb.Error, e:
      if DEBUG: self.logger.info(str(e.args[0]) + "--" + e.args[1])
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1]
    return elist 

  def rollback(self, txnid):
    elist = [ERROR_MY]
    try:
      cursor, client = self.__get_connection(txnid)
      cursor.close()
      client.rollback()
      self.__close_connection(txnid)
    except MySQLdb.Error, e:
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
    return elist

  def get_schema(self, table_name):
    table_name = "x" + table_name
    elist = [ERROR_MY]
    client = None
    try: 
      client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
      cursor = client.cursor()
      command = "SHOW fields FROM `" + table_name + "`"
      cursor.execute(command)
      while (1):
        row = cursor.fetchone()
        if row == None:
          break
        if row[0] != ROW_KEY:
          item =  row[0]
          # take off the first letter "x"
          item = item[1:] 
          elist.append(item)
      if DEBUG: self.logger.info(elist)
    except MySQLdb.Error, e:
      if DEBUG: print str(e.args[0]) + "--" + e.args[1] 
      elist[0] = ERROR_MY + "Unable to get schema"
    if client:
      client.commit()
      client.close()
    return elist

  def delete_table(self, table_name):
    table_name = "x" + table_name
    elist = [ERROR_MY]
    client = None
    try:
      client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
      cursor = client.cursor()
      command = "drop table `" + table_name + "`"
      if DEBUG: self.logger.info(command)
      cursor.execute(command)
    except MySQLdb.Error, e:
      elist[0] += str(e.args[0]) + "--" + e.args[1]
    if DEBUG: self.logger.info(elist)
    if client:
      client.commit()
      client.close()
    if table_name in self.tableCache:
      self.tableCache.remove(table_name)
    return elist

  def get_entity(self, table_name, row_key, column_names, txnid = 0):
    table_name = "x" + table_name
    elist = [ERROR_MY]
    client = None
    isTrans = False
    if txnid != 0 and self.transactionsOn:
      isTrans = True
    if not row_key:
      self.logger.info("Null row key")
      elist[0] += "Null row key"
      return elist

    try:
      if not isTrans:
        client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
        cursor = client.cursor()
      else:  
        cursor, client = self.__get_connection(txnid)

      command = "select "
      # Hacking on a x to make sure all columns start with a letter
      columncopy = []
      for ii in range(0, len(column_names)):
        columncopy.append("x" + column_names[ii])
      columns = ', '.join(columncopy)
      command += columns
      row_key = MySQLdb.escape_string(row_key)
      command += " from `"+ table_name + "` WHERE " + ROW_KEY + " = '" + row_key + "'"
      if DEBUG: self.logger.info(command)
      cursor.execute(command)
      result = cursor.fetchone()
      if result == None:
        if not isTrans:
          client.close()
        if len(elist) == 1:
          elist[0] += "Not found"
        return elist
      for ii in range(0, len(result)):
        if result[ii]:
          elist.append(result[ii])
        else:
          elist.append('')
    except MySQLdb.Error, e:
      if e.args[1].find("exists") == -1:
        if not isTrans:
          client.close()
        if len(elist) == 1:
          elist[0] += "Not found"
        return elist
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
    if DEBUG: self.logger.info(elist)
    
    if client and not isTrans:
      client.close()
    if len(elist) == 1:
      elist[0] += "Not found"
    return elist

  def put_entity(self, table_name, row_key, column_names, cell_values, txnid = 0):
    # Hacking on a x to make sure all columns start with a letter
    # Mysql limitation
    table_name = "x" + table_name
    if DEBUG: self.logger.info("PUT ENTITY")
    if DEBUG: self.logger.info(str(cell_values))
    if DEBUG: self.logger.info("row key: " + row_key)
    client = None
    elist = [ERROR_MY]
    if not row_key:
      self.logger.info("Null row key")
      elist[0] += "Null row key"
      return elist
    columncopy = []
    for ii in range(0, len(column_names)):
      columncopy.append("x" + column_names[ii])
    tempclient = None
    tempcursor = None
    if self.__table_exist(table_name) == 0:
      try:
        tempclient = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
        query = "CREATE TABLE IF NOT EXISTS `" + table_name + "` ( " + ROW_KEY + " CHAR(255) primary key, " + ' BLOB, '.join(columncopy) + " BLOB) ENGINE=NDBCLUSTER" 
        tempcursor = tempclient.cursor()
        if DEBUG: self.logger.info(query)
        result = tempcursor.execute(query)
        if DEBUG: self.logger.info("DONE CREATING TABLE...%s",str(result))
        self.tableCache.append(table_name)
      except MySQLdb.Error, e:
        error = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
        print error
        if tempcursor:
          tempcursor.close()
        if tempclient:
          tempclient.commit()
          tempclient.close()

    isTrans = False
    if txnid != 0 and self.transactionsOn:
      isTrans = True
    try:
      if not isTrans:
        client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
        cursor = client.cursor()
      else:  
        cursor, client = self.__get_connection(txnid)

      if len(column_names) != len(cell_values):
        elist[0] += "Error in put call |column_names| != |cell_values|"
        if not isTrans:
          client.close()
        return elist 
      values = []
      for ii in range(0, len(cell_values)):
        if cell_values[ii]:
          value = cell_values[ii]
          values.append(MySQLdb.escape_string(value))
        else:
          values.append('')

      row_key = MySQLdb.escape_string(row_key)
      command = "SELECT " + ROW_KEY + " FROM `" + table_name + "` WHERE " + ROW_KEY + " = '" + row_key + "'"
      cursor.execute(command)
      row = cursor.fetchone()
      if row == None:
        # do an insert 
        command = "INSERT INTO `" + table_name + "` (" 
        for ii in range(0, len(cell_values)):
          command += columncopy[ii]
          command += ", "
        command += ROW_KEY + ") VALUES("
        for ii in range(0, len(cell_values)):
          command += "%s, "
        command += "%s)"
        if DEBUG: self.logger.info(command)
        cursor.execute(command, tuple(cell_values + [MySQLdb.escape_string(row_key)])) 
      else:
        # do an update 
        for ii in range(0, len(cell_values)):
          command = "UPDATE `" + table_name + "` SET " 
          command += columncopy[ii] + " = %s" 
          command += " WHERE " + ROW_KEY + " = %s" 
          if DEBUG: self.logger.info(command)
          cursor.execute(command, (cell_values[ii], MySQLdb.escape_string(row_key))) 

    except MySQLdb.Error, e:
      if DEBUG: self.logger.info("ERROR FOR PUT")
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
      if DEBUG: self.logger.info(elist[0])
    elist.append("0")
    if DEBUG: self.logger.info(elist)
    if DEBUG: self.logger.info("DONE WITH PUT ENTITY")
    if client and not isTrans:  
      cursor.close()
      client.commit()
      client.close()
    return elist 

  def __table_exist(self, table_name):
    table_name = "x" + table_name
    if table_name in self.tableCache:
      return 1
    return 0

  def delete_row(self, table_name, row_key, txnid = 0):
    table_name = "x" + table_name
    if DEBUG: self.logger.info("DELETE ROW")
    client = None
 
    isTrans = False
    if txnid != 0 and self.transactionsOn:
      isTrans = True
    elist = [ERROR_MY]
    try:
      if txnid == 0 or not self.transactionsOn:
        client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
        #client.autocommit(0)
        cursor = client.cursor()
      else:  
        cursor, client = self.__get_connection(txnid)
#      cursor.execute(USE_DATABASE)
      row_key = MySQLdb.escape_string(row_key)
      query = "delete from `" + table_name + "` WHERE " + ROW_KEY + "= '" + row_key + "'" 
      if DEBUG: self.logger.info(query)
      cursor.execute(query)
    except MySQLdb.Error, e:
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
    if DEBUG: self.logger.info(elist)
    if DEBUG: self.logger.info("DELETING ROW")
    if client and not isTrans:
      client.commit()
      client.close()
    return elist

  def get_row_count(self, table_name):
    table_name = "x" + table_name
    if DEBUG: self.logger.info("GETTING ROW COUNT")
    client = None
    elist = [ERROR_MY]
    try:
      client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
      #client.autocommit(0)
      cursor = client.cursor()
#      cursor.execute(USE_DATABASE)
      query = "SELECT COUNT(*) FROM `" + table_name + "`"
      cursor.execute(query)
      count = cursor.fetchone()
      elist.append(str(count[0]))
    except MySQLdb.Error, e:
      elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
    if DEBUG: self.logger.info(elist)
    if DEBUG: self.logger.info("DONE WITH ROW COUNT")
    if client:
      cursor.close()
      client.close()
    return elist

  def get_table(self, table_name, column_names, txnid = 0):
    table_name = "x" + table_name
    if DEBUG: self.logger.info("GET TABLE")
    client = None
    elist = [ERROR_MY]
    try:
      if txnid == 0 or not self.transactionsOn:
        client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
        #client.autocommit(0)
        cursor = client.cursor()
      else:  
        cursor, client = self.__get_connection(txnid)
#      cursor.execute(USE_DATABASE)
      # Hacking on a letter to make sure all columns start with a letter
      columncopy = []
      for ii in range(0, len(column_names)):
        columncopy.append("x" + column_names[ii])

      command = "select " + ', '.join(columncopy) + " from `" + table_name + "`"
      if DEBUG: self.logger.info(command)
      cursor.execute(command)
      while (1): 
        row = cursor.fetchone()
        if row == None:
          break
        for ii in range(0, len(row)):
          if DEBUG: self.logger.info(str(row))
          #elist += [row[ii]]
          if row[ii]:
            #elist += [base64.b64decode(row[ii])]
            elist.append(row[ii])
          else:
            elist.append('')
    except MySQLdb.Error, e:
      # Return nothing if the table has not been created 
      if "doesn't exist" in e.args[1]:
        pass
      else: 
        elist[0] = ERROR_MY + str(e.args[0]) + "--" + e.args[1] 
        if DEBUG: self.logger.info(str(elist[0]))
    if DEBUG: self.logger.info(str(elist))
    if DEBUG: self.logger.info("DONE GETTING TABLE")
    if client:
      if not self.transactionsOn or txnid == 0:
        cursor.close()
        client.close()
    return elist

  def __query_table(self, table_name):
    table_name = "x" + table_name
    client = self.__get_connection()
    cursor = client.cursor()
    cursor.execute("select * from `" + table_name + "`")
    elist = []
    while (1):
      row = cursor.fetchone()  
      if row == None:
        break
      elist.append(row)
    if cursor:
      cursor.close()
    if client:
      client.commit()
      client.close()
    return elist

  def __get_connection(self, txnid):
    client = None
    cursor = None
    self.__gc()
    
    transDict_lock.acquire()
    if txnid in transDict:
      cursor, client, start_time = transDict[txnid] 
    transDict_lock.release()
    if not client:
      raise MySQLdb.Error(1, "Connection timed out")
    return cursor, client 

  # clean up expired connections
  def __gc(self):
    global last_gc_time
    curtime = time.time()
    if curtime < last_gc_time + GC_TIME:
      return
    transDict_lock.acquire()
    del_list = []
    for ii in transDict:
      cu, cl, st = transDict[ii]
      if st + TIMEOUT < curtime:
        del_list.append(ii)    
    # safe deletes
    del_list.reverse()
    for ii in del_list:
      del transDict[ii]
    transDict_lock.release()
    last_gc_time = time.time() 

  def setupTransaction(self, txnid):
    self.transactionsOn = True
    # New connection 
    client = MySQLdb.connect(host=DB_LOCATION, db=USE_DATABASE)
    #client.autocommit(0)
    cursor = client.cursor()
    transDict_lock.acquire()
    transDict[txnid] = cursor, client, time.time()
    transDict_lock.release()

  def __close_connection(self, txnid):
    transDict_lock.acquire()
    if txnid in transDict:
      cursor, client, start_time = transDict[txnid]
      cursor.close()
      client.close()
      del transDict[txnid]
    transDict_lock.release()
    return 


