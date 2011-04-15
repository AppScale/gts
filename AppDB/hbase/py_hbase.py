#Author: Navraj Chohan

import os

import Hbase
import ttypes
import time
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from dbinterface import *
#import sqlalchemy.pool as pool
import appscale_logger
import threading
from socket import gethostname; 
PROFILING = False
ERROR_HB = "DB_ERROR:"
DB_LOCATION = gethostname()
THRIFT_PORT = 9090

class DatastoreProxy(AppDBInterface):

  def __init__(self, logger = appscale_logger.getLogger("datastore-hbase")):
    self.logger = logger
    self.lock = threading.Lock()
    self.connection = self.__createConnection()
    self.tableCache = []
    #self.pool = pool.QueuePool(self.__createConnection)

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.debug(function + ": " + str(end_time - start_time) + " s")

  def __createConnection(self):
    t = TSocket.TSocket(DB_LOCATION, THRIFT_PORT)
    #t = TSocket.TSocket(self.get_local_ip(), THRIFT_PORT)
    t = TTransport.TBufferedTransport(t)
    p = TBinaryProtocol.TBinaryProtocol(t)
    c = Hbase.Client(p)
    t.open()
    return c

  def __initConnection(self):
    self.lock.acquire()
    if self.connection:
      return self.connection
    else:
      self.connection = self.__createConnection()
      return self.connection
    #return self.pool.connect()

  def __closeConnection(self, conn):
    #conn.close()
    self.lock.release()
#    self.transport.close()
#    self.client = None
#    self.transport = None
#    self.protocol = None

  def get_schema(self, table_name):
    st = time.time()
    elist = [ERROR_HB] 
    if not table_name:
      return elist
    client = None
    try:
      client = self.__initConnection()
      keys = (client.getColumnDescriptors(table_name)).keys()
      # Last character has ":" for version 89 and up, remove it
      for index, ii in enumerate(keys):
        keys[index] = ii[:-1] 
      elist.extend(keys)
    except ttypes.IOError, io:
      elist[0] += "Get Schema IO Error--" + io.message
    """except Exception, e:
    print type(e)
    elist[0] = elist[0] + str(e) # append the error
    """
    self.__closeConnection(client)
    et = time.time()
    self.logTiming("HB GET SCHEMA", st, et)
    return elist

  def get_row_count(self, table_name):
    st = time.time()
    elist = [ERROR_HB]
    value = 0

    if not table_name:
      elist.append(value)
      return elist

    client = None
    try:
      client = self.__initConnection()
      column_names = client.getColumnDescriptors(table_name)
      keys = column_names.keys()
      # Last character has ":" for version 89 and up, remove it
      for index, ii in enumerate(keys):
        keys[index] = ii[:-1] 
 
      table = self.get_table(table_name, keys)
      value = (len(table) - 1)/(len(keys))
      elist.append(value)
    except ttypes.IOError, io:
      elist[0] = elist[0] + "Row Count. IO Error--" + io.message
      value = 0
    self.__closeConnection(client)
    et = time.time()
    self.logTiming("HB ROWCOUNT", st, et)
    return elist

  def create_table(self, table_name, column_names):
    client = self.__initConnection()
    columnlist = []
    for ii in column_names:
      col = ttypes.ColumnDescriptor()
      col.name = ii + ":"
      col.maxVersions = 3
      columnlist.append(col)
    client.createTable(table_name, columnlist)
    ret = client.getTableNames()
    self.__closeConnection(client)
    return ret

  def put_entity(self, table_name, row_key, column_names, cell_values):
    st = time.time()
    elist = [ERROR_HB]
    if (not row_key) or (not table_name):
      elist[0] += "Null row_key or table_name" 
      return elist
    client = None
    try:
      if len(column_names) != len(cell_values):
        ttypes.IOError( "Number of values does not match the number of columns")
      client = self.__initConnection()
      if self.__table_exist(table_name, client) == 0:
        columnlist = []
        for ii in column_names:
          col = ttypes.ColumnDescriptor()
          col.name = ii + ":"
          col.maxVersions = 3
          columnlist.append(col)

        client.createTable(table_name, columnlist)

      for ii in range(0,len(column_names)):
        m = ttypes.Mutation()
        m.column = column_names[ii] + ":"
        m.value = cell_values[ii]
        mutations = []
        mutations.append(m)
        client.mutateRow(table_name, row_key, mutations)
    except ttypes.IOError, io:
      if io:
        elist[0] += str(io) # append the error
      else: 
        elist[0] += "IO Error"
    #print "exception type: IOError"
    except ttypes.IllegalArgument, ia:
      elist[0] = elist[0] + str(ia) # append the error
      print "exception type: Illegal Argument"
    # append result
    elist.append("0")
    self.__closeConnection(client)
    et = time.time()
    self.logTiming("HB PUT", st, et)
    return elist

  def get_row(self, table_name, row_key, max_versions = 1):
    st = time.time()
    elist = [ERROR_HB] 
    if not table_name:
      elist[0] += "Null table_name" 
      return elist
    if not row_key:
      elist[0] += "Null row key"  
      return elist
    client = None
    try:
      client = self.__initConnection() 
      row = client.getRow(table_name, row_key)
      keys = row.keys()
      for ii in keys:
        elist.append(row[ii].value)
    except ttypes.IOError, io:
      if io.message:
        elist[0] += io.message
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB GETROW", st, et)
    return elist

  def delete_table(self, table_name):
    st = time.time()
    elist = [ERROR_HB] 
    if not table_name:
      elist[0] += "Null table_name" 
      return elist
    client = None
    try:
      client = self.__initConnection() 
      client.disableTable(table_name)
      client.deleteTable(table_name)
    except ttypes.IOError, io:
      elist[0] += io.message
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB DELETE", st, et)
    if table_name in self.tableCache:
      self.tableCache.remove(table_name)
    return elist

  def get_entity(self, table_name, row_key, column_names):
    st = time.time()
    elist = [ERROR_HB] 

    if not table_name:
      elist[0] += "Null table_name" 
      return elist
    if not row_key:
      elist[0] += "Null row key"  
      return elist
    client = None
    try:
      client = self.__initConnection() 
      column_list = []
      for ii in column_names:
        column_list.append(ii + ":") 
        cells = client.getRowWithColumns(table_name, row_key, column_list)
      if cells:
        for ii in column_list:
          elist.append(cells[0].columns[ii].value)
      else:
        elist[0] += "NotFound"
    except ttypes.IOError, io:
      elist[0] += "IO Error--" + io.message
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB GETENT", st, et)
    return elist

  def delete_row(self, table_name, row_key):
    st = time.time()
    elist = [ERROR_HB] 
    if (not row_key) or (not table_name):
      elist[0] += "Null row_key or table_name" 
      return elist
    client = None
    try: 
      "del"
      client = self.__initConnection()
      client.deleteAllRow(table_name, row_key)
    except ttypes.IOError, io:
      if io.message:
        elist[0] += "IO Error--" + io.message
      else: 
        elist[0] += "IO Error"
    except Exception, e:
      elist[0] = elist[0] + str(e) # append the error
  
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB DELETEROW", st, et)
    return elist

  def get_table(self, table_name, column_names = []):
    st = time.time()
    elist = [ERROR_HB]
    if not table_name:
      elist[0] += "Null table_name" 
      return elist
    client = None
    try: 
      client = self.__initConnection()
      columnNames = []
      for col in column_names:
        columnNames.append(col + ":")
      scanner = client.scannerOpen(table_name, "", columnNames) 
      r = client.scannerGet(scanner)
      while r:
        for c in columnNames:
          try:
            elist.append((r[0].columns[c]).value)
          except:
            pass # ignore key errors
        r = client.scannerGet(scanner)
      client.scannerClose(scanner) 
    except ttypes.IOError, io:
      if io.message:
        if io.message == table_name:
          pass # Return an empty table
        else:
          elist[0] += "IO Error--" + str(io.message)
      else:
        elist[0] += "IOError"
    except ttypes.IllegalArgument, e:
      if e.message:
        elist[0] += "IllegalArgument--" + str(e.message)
      else:
        elist[0] += "IllegalArgument"
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB GETTABLE", st, et)
    return elist  

  def run_query(self, table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, start_inclusive, end_inclusive ):
    st = time.time()
    scanner_id = 0
    elist = [ERROR_HB]
    client = None
    try: 
      client = self.__initConnection()
      columns = []
      for ii in column_names:
        columns.append(ii + ":")
      max_char = unichr(127)
      endrow_key = endrow + max_char
      if endrow:
        scanner_id = client.scannerOpenWithStop(table_name, startrow, endrow_key, columns) 
      else: 
        scanner_id = client.scannerOpen(table_name, startrow, columns)
 
      count = 0
      r = client.scannerGet(scanner_id)
      while r:
        count = count + 1
        if count > (limit + offset):
          client.scannerClose(scanner_id)
          scanner_id = -1
          break
        if count > offset:  
          if (start_inclusive == 0) and (startrow == r[0].row):
            # don't include this in the results, and subtract 1 from count
            #__printRow(r[0])
            count = count - 1
          elif (end_inclusive == 0) and (endrow == r[0].row):
            # don't include this in the results, and subtract 1 from count
            #__printRow(r[0])
            count = count - 1
          elif getOnlyKeys:
            #print "KEY ONLY"
            elist.append(r[0].row)
          else:
            for column in columns:
              #print "Adding data"
              elist.append(r[0].columns[column].value)
        r = client.scannerGet(scanner_id)
      if scanner_id != -1:
        client.scannerClose(scanner_id)
    except ttypes.IOError, io:
      if io.message:
        elist[0] += io.message # append the error
      else:
        elist[0] += "IO Error"
    except ttypes.IllegalArgument, ia:
      elist[0] = elist[0] + ia.message # append the error
      print "exception type: Illegal Argument " + ia.message
    self.__closeConnection(client)
    et = time.time() 
    self.logTiming("HB RUN QUERY", st, et)
    return elist

#  def __close_connection(self, transport):
#    transport.close()
#    return

  def __table_exist(self, table_name, client):
    ret = False
    try:
      if table_name in self.tableCache:
        return True
      tables = client.getTableNames()
      self.tableCache = tables
      if table_name in tables:
        ret = True
    except:
      ret = False
    return ret

  # takes a list of column names
  def __column_dict(self, column_names):
    column_dict = []
    if isinstance(column_names, list) == 0:
      raise "Only deals with list"
    for column in column_names:
      entry = ttypes.ColumnDescriptor({'name':column + ':'})
    column_dict.append(entry)
    return column_dict

  def __printRow(self, entry):
    print entry
    print "row: " + entry.row + ", cols:",
    for k in sorted(entry.columns):
      print k + " => " + entry.columns[k].value,
    print
