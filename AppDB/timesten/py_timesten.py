# Author Mayuri Karra
# This file contains all the functions required for accessing TimesTen
# We used the pyodbc module for talking to TimesTen datastore
# Modified: Yoshi <nomura@pobox.com>

import os,sys

import pyodbc
import sqlalchemy.pool as pool
from dbinterface import *
import appscale_logger

ROW_KEY = "timesten__row_key__"
ERROR_TT = "DB_ERROR:"
DB_CONN_STRING = "dsn=TT_tt70"
KEY_SIZE = 512
BLOB_SIZE = 1000000

DEBUG_PRINT_SQL = False

class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-timesten")):
    self.logger = logger
    self.pool = pool.QueuePool(self.__create_connection)

  def __create_connection(self):
    con = pyodbc.connect(DB_CONN_STRING)
    con.autocommit = True
    return con

  def get_connection(self):
    return self.pool.connect()

  def close_connection(self, conn):
    if conn:
      conn.close()

  '''
      get_schema returns the schema of the given table
      Argument description
          table_name : the given table
      Return value description
          returns the schema of the given table in a list
  '''
  def get_schema(self, table_name):
    self.logger.debug("beginning get_schema: %s " % table_name)
    elist = [ERROR_TT]
    client = None
    try:

      # Opening a connection and a cursor
      client = self.get_connection()
      cursor = client.cursor()

      # Since TimesTen does not have an equivalent SQL for mysql SHOW FIELDS FROM (which retrieves schema)
      # , we have to do a join of sys.tables and sys.columns tables which are system tables
      # available in TimesTen. There is apparently no simple way of retrieving schema
      command = "SELECT COLNAME, COLTYPE, COLLEN FROM sys.columns c, sys.tables t WHERE  t.tblid=c.id AND  t.tblname =  UPPER ('%s');" % table_name
      cursor.execute(command)

      # Now we iterate throw the result from the above join and print the name, type 
      # of columns  The code is a bit cumbersome, but so long as TimesTen does not 
      # support a direct SQL for describing a schema 

      rowcount = 0
      for row in cursor.fetchall():
        rowname = row[0].strip().lower()
        if rowname != ROW_KEY:
          elist.append(rowname)
          rowcount += 1
      if rowcount == 0:
        elist = [ERROR_TT + "Unable to get schema"]

      self.logger.debug(elist)

    except pyodbc.Error, e:
      elist = [ERROR_TT + "Unable to get schema"]
    self.logger.debug("done with get_schema  " + table_name)
    self.close_connection(client)
    return elist

  '''
    __table_exist (table_name) function definition                              
      Helper function used by other functions. It tests if the given table exists
      It looks into the SYS.TABLES table for the given table name                 

      Argument description
          table_name	: name of the table

      Return value
          0 : if the table does not exist
          1 : if the table exists
  '''

  def __table_exist(self, table_name):
    self.logger.debug("checking if " + table_name + " table exists ")
    client = None
    try:
          client = self.get_connection()
          cursor = client.cursor()
          command = "SELECT COUNT(*) FROM sys.tables WHERE tblname = UPPER('%s')" % table_name
          if DEBUG_PRINT_SQL: self.logger.debug(command)
          cursor.execute(command)
          row = cursor.fetchone()
          if (row[0] == 1):
            self.logger.debug("Table " + table_name + " exists ")
          else:
            self.logger.debug("Table " + table_name + " does not exist")

    except pyodbc.Error, e:
      self.logger.debug(ERROR_TT + str(e.args[0]) + "--" + e.args[1])
      self.logger.debug("done with __table_exist ")
      self.close_connection(client)
      return False

    self.logger.debug("done with __table_exist")
    self.close_connection(client)
    return row[0]

  '''
      put_entity function adds a new entry to the given table. If the table does
      not exist, it creates the table. If the row exists, it updates the columns

      Argument description
          table_name   : Name of the table to insert the row into
          row_key      : key
          column_names : Names of the columns
          cell_values  : Values of the columns

      Return description
          list with error message : If the put_entity function fails
          empty list 		: If the put_entity function succeeds
  '''   

  def put_entity(self, table_name, row_key, column_names, cell_values):
    self.logger.debug("beginning put_entity (%s, %s)" % (table_name, row_key))
    self.logger.debug(column_names)
    self.logger.debug(cell_values)
    elist = [ERROR_TT]

    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()

      # Some sanity checking
      if len(column_names) != len(cell_values):
        elist[0] += "Error in put call |column_names| != |cell_values|"
        self.close_connection(client)
        return elist

      # Check if the table exist
      if not self.__table_exist (table_name):
        self.create_table(table_name, column_names)

      # Add all the column values to the list
      values = []
      for ii in range(0, len(cell_values)):
        values.append(pyodbc.Binary (cell_values [ii]))


      # Query the database for the existance of the row
      command = "SELECT " + ROW_KEY + " FROM " + table_name + " WHERE " + ROW_KEY + " = ?"
      cursor.execute(command, tuple ([row_key]))
      row = cursor.fetchone()

      # Check if the row does not exist. If it does not, do an insert
      if row == None:
        # do an insert 
        command = "INSERT INTO " + table_name + " ("
        for ii in range(0, len(cell_values)):
          command += column_names[ii]
          command += ", "
        command += ROW_KEY + ") VALUES("

        for ii in range(0, len(cell_values)):
          command += "?, "
        command += "?)";

        if DEBUG_PRINT_SQL: self.logger.debug(command)
        cursor.execute(command, tuple (values+[row_key]))
      else:
        # do an update 
        command = "UPDATE " + table_name + " SET "
        for ii in range(0, len(cell_values) - 1):
          command += column_names[ii] + " = ?, "
        command += column_names[len(cell_values)-1] + " = ? WHERE " + ROW_KEY + " = ?" 

        if DEBUG_PRINT_SQL: self.logger.debug(command)
        cursor.execute(command, tuple (values + [row_key]))

    except pyodbc.Error, e:
      self.logger.debug("ERROR FOR PUT")
      elist = [ERROR_TT + "put_entity: " + str(e.args[0]) + "--" + e.args[1]]
      elist.append("0")
      self.logger.debug(elist[0])
      self.close_connection(client)
      return elist

    elist.append("0")

    self.logger.debug("done with put_entity (" + table_name + "," + row_key +")")

    self.close_connection(client)
    return elist

  '''
      get_entity function searches for an entry in the given table. It returns
      the required columns

      Argument description
          table_name   : Name of the table to get the row from
          row_key      : key
          column_names : Names of the columns
          cell_values  : Values of the columns

      Return description
          list of the values if the row exists
          empty list if the row does not exist
  '''   

  def get_entity(self, table_name, row_key, column_names):
    self.logger.debug("beginning get_entity (%s, %s)" % (table_name, row_key))
    self.logger.debug("column_names: ")
    self.logger.debug(column_names)
    elist = [ERROR_TT]
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      command = "select " 
      columns = ', '.join(column_names)
      command += columns
      command += " from "+ table_name + " WHERE " + ROW_KEY + " = ?" 
      if DEBUG_PRINT_SQL: self.logger.debug(command)
      cursor.execute(command, tuple ([row_key]))
      result = cursor.fetchone()

      if result == None:
        elist[0] += " entity is not exist."
        self.close_connection(client)
        return elist

      for ii in range(0, len(result)):
        if result[ii]:
          elist.append(str(result[ii]))
        else:
          elist.append('')
    except pyodbc.Error, e:
      elist = [ERROR_TT + "get_entity: " + str(e.args[0]) + "--" + str(e.args[1])]
  #    if e.args[1].find("exists") == -1:
      self.close_connection(client)
      return elist

    self.logger.debug("done with get_entity returned value is " + str (len(column_names)))
    for ii in range(0, len(column_names)):
      self.logger.debug("%s: %s" % (column_names [ii], elist[ii+1]))

    self.close_connection(client)
    return elist


  '''
      get_table returns all entries in the given table. It returns
      the required columns

      Argument description
          table_name   : Name of the table
          column_names : Names of the columns

      Return description
          list of rows 
  '''


  def get_table(self, table_name, column_names):
    self.logger.debug("beginning get_table " + table_name)
    elist = [ERROR_TT]
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      command = "select " + ', '.join(column_names) + " from " + table_name
      self.logger.debug(command)
      cursor.execute(command)
      while (1):
        row = cursor.fetchone()
        if row == None:
          break
        for ii in range(0, len(row)):
          if row[ii]:
            elist.append(str(row[ii]))
          else:
            elist.append('')
    except pyodbc.Error, e:
      elist = [ERROR_TT + "get_table: " + str(e.args[0]) + "--" + e.args[1]]
      self.logger.debug(elist[0])
    self.logger.debug("done with get_table " + table_name)
    self.close_connection(client)
    return elist

  '''
      delete_row deletes a row with the given key in the given table
      It errors out if the delete fails for several reasons

      Argument description:
          table_name : Name of the input table
          row_key    : value of the key

     Return description:
          list with an error message if it fails
          other wise, the input key

  '''

  def delete_row(self, table_name, row_key):
    self.logger.debug("beginning delete_row (" + table_name + ", " + row_key + ")" )
    elist = [ERROR_TT]
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      query = "delete from " + table_name + " where "+ ROW_KEY + "= ?"
      if DEBUG_PRINT_SQL: self.logger.debug(query)
      cursor.execute(query, tuple ([row_key]))
    except pyodbc.Error, e:
      elist = [ERROR_TT + "Row with the key " + row_key + " in table " + table_name + " does not exist"]
    self.logger.debug("done with delete_row (" + table_name + ", " + row_key + ")" )
    self.close_connection(client)
    return elist


  '''
      get_row_count returns the number of rows in the given table

      Argument description:
          table_name : Name of the table

      Return description:
          list containing the count if the table exists
          otherwise the list containing the error
  '''

  def get_row_count(self, table_name):
    self.logger.debug("beginning get_row_count (%s)" % table_name)
    elist = [ERROR_TT]
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      query = "SELECT COUNT(*) FROM " + table_name
      cursor.execute(query)
      count = cursor.fetchone()
      elist.append(count[0])
    except pyodbc.Error, e:
      elist = [ERROR_TT + "get_row_count: " + str(e.args[0]) + "--" + e.args[1]]
    self.logger.debug("done with get_row_count (" + table_name + ") returned value is " )
    self.logger.debug(elist)
    self.close_connection(client)
    return elist

  def delete_table(self, table_name):
    elist = [ERROR_TT]
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      command = "DROP TABLE %s;" % table_name
      self.logger.debug(command)
      cursor.execute(command)
    except pyodbc.Error, e:
      elist = [ERROR_TT + "fail to delete table: " + str(e.args[0]) + "--" + str(e.args[1])]
    self.close_connection(client)
    return elist

  def create_table(self, tablename, columns):
    if self.__table_exist(tablename):
      return True
    client = None
    try:
      client = self.get_connection()
      cursor = client.cursor()
      command = "CREATE TABLE " + tablename + " ( " + ROW_KEY + " CHAR(" + str(KEY_SIZE) + ") primary key, " + " VARBINARY (" + str(BLOB_SIZE) + "), ".join(columns) + " VARBINARY (" + str(BLOB_SIZE) + "));"
      self.logger.debug(command)
      cursor.execute(command)
#      client.commit()
    except pyodbc.Error, e:
      self.logger.debug(e.args[1])
      self.close_connection(client)
      return False
    self.close_connection(client)
    return True
