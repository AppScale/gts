# Author: Navraj Chohan
# Author: Kowshik Prakasam

import sys
import os
import time

import helper_functions
from hypertable.thriftclient import * 
import hyperthrift.gen.ttypes as ttypes
#from hyperthrift.gen2 import *
import string
import cgi
from xml.sax import make_parser
import xml
from xml.sax import parseString
from xml.sax.handler import feature_namespaces
from xml.sax import ContentHandler
from xml.sax import saxutils
from xml.sax.handler import ContentHandler
#import sqlalchemy.pool as pool
from dbinterface import *
import appscale_logger
import threading 

THRIFT_PORT = 38080
ERROR_HT = "DB_ERROR:"
DB_LOCATION = "localhost"
NS = "/appscale"

ROOT_TAG_BEGIN="<Schema>"
ROOT_TAG_END="</Schema>"

ACCGRP_TAG_BEGIN='<AccessGroup name="default">'
ACCGRP_TAG_END="</AccessGroup>"

COLFMLY_TAG_BEGIN="<ColumnFamily>"
COLFMLY_TAG_END="</ColumnFamily>"

NAME_TAG_TEXT = "Name"

NAME_TAG_BEGIN="<"+NAME_TAG_TEXT+">"
NAME_TAG_END="</"+NAME_TAG_TEXT+">"

PROFILING = False

class HTLogger:
  def __init__(self, log):
    self.ht_lock = threading.Lock()
    self.ht_logger = log
  def debug(self, string):
    if PROFILING == True:
      self.ht_lock.acquire()
      self.ht_logger.info(string)
      self.ht_lock.release()

#ht_logger = HTLogger(log_logger)

class XmlSchemaParser(ContentHandler):
  def __init__(self, tag_name):
    self.tag_name = tag_name
    self.isName = 0
    self.attributes = []

  def clear_attributes(self):
    self.attributes = []

  def startElement(self, name, attrs):
    if name == self.tag_name:
      self.isName = 1

  def endElement(self, name):
    if name == self.tag_name:
      self.isName = 0

  def characters(self, ch):
    if self.isName == 1:
      self.attributes.append(ch)

class DatastoreProxy(AppDBInterface):

  def __init__(self, logger = appscale_logger.getLogger("datastore-hypertable")):
    self.logger = logger
    #self.pool = pool.QueuePool(self.__createConnection)
    #self.conn = ThriftClient(self.get_local_ip(), THRIFT_PORT)
    #self.ns = self.conn.open_namespace(NS)
    self.conn = None
    self.tableCache = []
    self.lock = threading.Lock()

  def __initConnection(self, create_ns=False):
    self.lock.acquire()
    if not self.conn:
      self.conn = ThriftClient(self.get_local_ip(), THRIFT_PORT)
      try:
        if create_ns and not self.conn.namespace_exists(NS):
          self.conn.namespace_create(NS)
      except Exception, e:
        print "Unable to create namepsace"
        print e
      self.ns = self.conn.namespace_open(NS)
    # self.ns = self.conn.open_namespace(NS)
    #if PROFILING:
    #  self.logger.debug("HT InitConnection: %s"%str(endtime - starttime))
    return self.conn

  def __closeConnection(self, conn):
    #if conn:
    self.lock.release()
    #conn.close_namespace(self.ns)
    #conn.close() 

  # tag is the xml tag which holds the schema attributes
  def getListFromXMLSchema(self, table, tag):
    parser = make_parser()

    #parser = setFeature(feature_namespaces, 0)
    dh = XmlSchemaParser(tag)
    dh.clear_attributes()
    parser.setContentHandler(dh)

    elist = [ERROR_HT]
    client = None
    try:
      client = self.__initConnection()
      res = client.hql_query(self.ns, "describe table " + table) 
    except:
      elist[0] += "IO Error"
      self.__closeConnection(client)
      return elist

    res = res.results

    schema = res 
    xml.sax.parseString(schema[0], dh)

    # items are not strings, need to convert them
    for ii in range(0, len(dh.attributes)):
      dh.attributes[ii] = str(dh.attributes[ii])
    elist += dh.attributes
    self.__closeConnection(client)
    return elist

  def get_schema(self, table_name):
    # Hypertable returns the results in XML form, so a function is needed to
    # convert it to an array
    return self.getListFromXMLSchema(table_name, NAME_TAG_TEXT)

  # For the column names of a table, this method returns
  # an xml string representing the columns, which can 
  # then be used with hypertable's thrift api
  def __constructSchemaXml(self, column_names):
    schema_xml = ''.join([ROOT_TAG_BEGIN, ACCGRP_TAG_BEGIN]) 
    for col_name in column_names:
      schema_xml += ''.join([COLFMLY_TAG_BEGIN, NAME_TAG_BEGIN, col_name, NAME_TAG_END, COLFMLY_TAG_END])
    schema_xml += ''.join([ACCGRP_TAG_END, ROOT_TAG_END])
    return schema_xml

  #Creates a table. If successful, returns a list of tables in the current hypertable namespace
  # Make sure not to open multiple connections if there is already a connection hold the lock
  def create_table(self, table_name, column_names):
    client=None
    table_names = None
    try:
      if not client:
        client = self.__initConnection(create_ns=True)
    except Exception, e:
      print str(e)
      if client:
        self.__closeConnection(client)
      return str(e)

    try:
      table_schema_xml = self.__constructSchemaXml(column_names)    
      client.create_table(self.ns,table_name,table_schema_xml)
      table_names = client.get_tables(self.ns)
      self.__closeConnection(client)
    except Exception, e:
      print str(e)
      if client:
        self.__closeConnection(client)
      return str(e)
    
    return table_names
    
  def get_entity(self, table_name, row_key, column_names):
    starttime = time.time()
    elist = [ERROR_HT]

    client = None
    try:
      client = self.__initConnection()
    # need to try this way for new interface (was having problems with deletes)
    #for ii in column_names:
    #   elist.append(client.get_cell(self.ns, table_name, row_key, ii))
      result = client.hql_query(self.ns, "select * from " + table_name + " where ROW = \"" + row_key + "\" REVS = 1")
      for name in column_names:
        for ii in range(0, len(result.cells)):
          if name == result.cells[ii].key.column_family:
            elist.append(result.cells[ii].value)
            break
    except:
      elist[0] += "Not Found"
    endtime = time.time() 
    if PROFILING:
      self.logger.debug("HT GET: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    if len(elist) == 1:
      elist[0] += "Not Found"
    return elist

  def delete_table(self, table_name):
    starttime = time.time()
    elist = [ERROR_HT]
    client = self.__initConnection()
    if self.__table_exist(table_name, client):
      try:
        client.drop_table(self.ns, table_name, 1)
      except:
        elist[0] += "Error deleting table" 
    else:
      elist[0] += "Table not found"
    endtime = time.time()
    if PROFILING:
      self.logger.debug("HT DELETE_TABLE: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    if table_name in self.tableCache:
      self.tableCache.remove(table_name)
    return elist

  def put_entity(self, table_name, row_key, column_names, cell_values):
    starttime = time.time()
    elist = [ERROR_HT]

    if len(column_names) != len(cell_values):
      elist[0] += "Error in put call |column_names| != |cell_values|"
      return elist

    client = self.__initConnection()
    if not self.__table_exist(table_name, client):
      table_schema = self.__constructSchemaXml(column_names)
      try:
        ret = client.create_table(self.ns, table_name, table_schema)
      except Exception, e:
        file = open("/tmp/hyper_exception_log","a")
        file.write(str(e))
        file.write("at put entity create table\n")
        file.close()
   
    try: 
      mutator = client.mutator_open(self.ns, table_name, 0, 0)
      cell_list = []
      for ii in range(0, len(column_names)):
        cell = ttypes.Cell() 
        keyflag = ttypes.KeyFlag()
        #255 is insert
        key = ttypes.Key(row=row_key, column_family=column_names[ii], 
                         flag=255)
        cell.key = key 
        cell.value =  cell_values[ii]
        cell_list.append(cell)
      client.mutator_set_cells(mutator, cell_list)
      client.mutator_close(mutator)
      
    except Exception, e:
      file = open("/tmp/hyper_exception_log","a")
      file.write(str(e))
      file.write("at trying to put the object\n")
      file.close()
      elist[0] += "Error in put call"  
      print e
    elist.append("0")
    endtime = time.time()
    if PROFILING:
      self.logger.debug("HT PUT: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    return elist 

  def __table_exist(self, table_name,client):
    starttime = time.time()
    if table_name in self.tableCache:
      return True

    try: 
      tables = client.get_tables(self.ns)
    except:
      return False

    self.tableCache = tables
    ret = False
    for ii in tables:
      if table_name == ii:
        ret = True
    return ret

  def delete_row(self, table_name, row_id):
    starttime = time.time()
    elist = [ERROR_HT]
    client = None
    try:
      client = self.__initConnection()
      query = "delete * from " + table_name + " where ROW=\""+ row_id + "\""
      client.hql_query(self.ns,query)
    except:
      elist[0] += "Not Found"
    endtime = time.time()
    if PROFILING: 
      self.logger.debug("HT DELETE: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    return elist

  def get_row_count(self, table_name):
    starttime = time.time()
    elist = [ERROR_HT]
    value = 0
    try: 
      res = self.get_schema(table_name) 
      error = res[0]
      if error != ERROR_HT:
        elist[0] += error
        return elist

      column_names = res[1:]
      table = self.get_table(table_name, column_names)
      value = (len(table) - 1)/len(column_names)
      elist += [value]
    except:
      elist += [0]
    endtime = time.time()
    if PROFILING:
      self.logger.debug("HT GETROWCOUNT: %s"%str(endtime - starttime))

    return elist

  def get_table(self, table_name, column_names):
    starttime = time.time()
    elist = [ERROR_HT]
    client = None
    try:
      client = self.__initConnection()
      res = client.hql_query(self.ns, "select * from " + table_name + " REVS = 1" )
      res = res.cells
      for ii in range(0, len(res)):
        if res[ii].key.column_family in column_names:
          elist += [res[ii].value]
    except:
      pass
    endtime = time.time()
    if PROFILING:
      self.logger.debug("HT GET_TABLE: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    return elist

  def __query_table(self, table_name):
    client = self.__initConnection()
    ret = client.hql_query(self.ns, "select * from " + table_name + " REVS = 1")
    self.__closeConnection(client)
    return ret

  def run_query(self, table_name, column_names, limit, offset, startrow, endrow, getOnlyKeys, start_inclusive, end_inclusive):
    starttime = time.time() 
    elist = [ERROR_HT]
    client = None
    try:
      client = self.__initConnection()
      row_intervals = [ttypes.RowInterval(startrow, start_inclusive, endrow, end_inclusive)]
      cell_intervals =  None
      include_deletes = 0
      scan_spec = ttypes.ScanSpec(row_intervals, cell_intervals, include_deletes, 1, limit + offset, 0, None, column_names)
      count = 0
      cells = client.get_cells(self.ns, table_name, scan_spec)
      for cell in cells:
        count = count + 1
        if count > offset:
          if getOnlyKeys:
            elist += [cell.row_key] 
          else:
            elist += [cell.value]
    except:
      elist[0] += "Exception thrown while running a scanner"  
    endtime = time.time()
    if PROFILING:
      self.logger.debug("HT RUN_QUERY: %s"%str(endtime - starttime))
    self.__closeConnection(client)
    return elist
