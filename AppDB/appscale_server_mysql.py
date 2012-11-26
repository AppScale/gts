#!/usr/bin/python
# See LICENSE file
#
# Author: 
# Navraj Chohan (nlake44@gmail.com)
import tornado.httpserver
import tornado.ioloop
import tornado.web

import array
import datetime 
import getopt
import itertools
import md5 
import MySQLdb
import os 
import random
import SOAPpy
import socket
import sys
import threading
import time
import types

from SocketServer import BaseServer
from M2Crypto import SSL
import MySQLdb.constants.CR

import appscale_datastore
import appscale_logger
from dbconstants import *

from google.appengine.api import api_base_pb
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_stub_util
from google.appengine.runtime import apiproxy_errors
from google.net.proto import ProtocolBuffer
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb
from drop_privileges import *
from zkappscale import zktransaction
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import sortable_pb_encoder
import __builtin__
buffer = __builtin__.buffer
zoo_keeper = None

# Port used if server is using encryption
DEFAULT_SSL_PORT = 8443

# Port used if no encryption is used by the server
DEFAULT_PORT = 4080

# Whether encryption is on by default
DEFAULT_ENCRYPTION = 1

# The SSL cert location
CERT_LOCATION = "/etc/appscale/certs/mycert.pem"

# The SSL private key location
KEY_LOCATION = "/etc/appscale/certs/mykey.pem"

# Where the secret key is located
SECRET_LOCATION = "/etc/appscale/secret.key"

# The length of a numerial key, padded until the key is this length
ID_KEY_LENGTH = 64

# The accessor for the datastore 
app_datastore = []

"""MySQL-based stub for the Python datastore API.
Entities are stored in a MySQL database in a similar fashion to the production
datastore. Based on Nick Johnson's SQLite stub and Typhoonae's mysql stub
"""

entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Transaction.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Cursor.__hash__ = lambda self: hash(self.Encode())

_DB_LOCATION = "127.0.0.1"

_USE_DATABASE = "appscale"

_DB_USER = "root"

_MAX_CONNECTIONS = 10

_GC_TIME = 60

_MAXIMUM_RESULTS = 1000

_MAX_QUERY_OFFSET = 1000

_MAX_QUERY_COMPONENTS = 63

_BATCH_SIZE = 20

_MAX_ACTIONS_PER_TXN = 5

_MAX_TIMEOUT = 5.0

_OPERATOR_MAP = {
    datastore_pb.Query_Filter.LESS_THAN: '<',
    datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL: '<=',
    datastore_pb.Query_Filter.EQUAL: '=',
    datastore_pb.Query_Filter.GREATER_THAN: '>',
    datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL: '>=',
}


_ORDER_MAP = {
    datastore_pb.Query_Order.ASCENDING: 'ASC',
    datastore_pb.Query_Order.DESCENDING: 'DESC',
}

# This is used for initial config
_NAMESPACE_TABLES = [ """
CREATE TABLE IF NOT EXISTS Apps (
  app_id VARCHAR(255) NOT NULL PRIMARY KEY,
  indexes VARCHAR(255)
) ENGINE=ndbcluster;
""","""
CREATE TABLE IF NOT EXISTS Namespaces (
  app_id VARCHAR(255) NOT NULL,
  name_space VARCHAR(255) NOT NULL,
  PRIMARY KEY (app_id, name_space)
) ENGINE=ndbcluster;
""","""
CREATE TABLE IF NOT EXISTS IdSeq (
  prefix VARCHAR(255) NOT NULL PRIMARY KEY,
  next_id INT(100) NOT NULL
) ENGINE=ndbcluster;
"""]

_NAMESPACE_SCHEMA = ["""
CREATE TABLE IF NOT EXISTS %(prefix)s_Entities (
  __path__ VARCHAR(255) NOT NULL PRIMARY KEY,
  kind VARCHAR(255) NOT NULL,
  entity MEDIUMBLOB NOT NULL,
  INDEX(kind),
  INDEX(__path__)
) ENGINE=ndbcluster;
""","""
CREATE TABLE IF NOT EXISTS %(prefix)s_EntitiesByProperty (
  kind VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  value VARCHAR(1024) NOT NULL,
  __path__ VARCHAR(255) NOT NULL REFERENCES Entities,
  hashed_index CHAR(32) NOT NULL,
  PRIMARY KEY(hashed_index),
  INDEX(value(32))
) ENGINE=ndbcluster;
""","""
INSERT IGNORE INTO Apps (app_id) VALUES ('%(app_id)s');
""","""
INSERT IGNORE INTO Namespaces (app_id, name_space)
  VALUES ('%(app_id)s', '%(name_space)s');
""","""
INSERT IGNORE INTO IdSeq VALUES ('%(prefix)s', 1);
"""]

def formatTableName(tableName):
    import re
    return re.sub("[^\w\d_]","",tableName)

def ReferencePropertyToReference(refprop):
  ref = entity_pb.Reference()
  ref.set_app(refprop.app())
  if refprop.has_name_space():
    ref.set_name_space(refprop.name_space())
  for pathelem in refprop.pathelement_list():
    ref.mutable_path().add_element().CopyFrom(pathelem)
  return ref


class QueryCursor(object):
  """Encapsulates a database cursor and provides methods to fetch results."""

  def __init__(self, query, db_cursor):
    """Constructor.

    Args:
      query: A Query PB.
      db_cursor: An MySQL cursor returning n+2 columns. The first 2 columns
        must be the path of the entity and the entity itself, while the
        remaining columns must be the sort columns for the query.
    """
    self.__query = query
    self.app = query.app()
    self.__cursor = db_cursor
    self.__num_results = 0
    if db_cursor:
      self.__num_results = db_cursor.rowcount
    self.__seen = set()

    self.__position = ('', '')

    self.__next_result = (None, None)

    if query.has_limit():
      self.limit = query.limit() + query.offset()
    else:
      self.limit = None

  def Count(self):
    """Counts results, up to the query's limit.

    Note this method does not deduplicate results, so the query it was generated
    from should have the 'distinct' clause applied.

    Returns:
      int: Result count.
    """
    count = 0
    if not self.__cursor:
      return count
    while self.limit is None or count < self.limit:
      row = self.__cursor.fetchone()
      if not row:
        break
      count += 1
    return count

  def _EncodeCompiledCursor(self, cc):
    """Encodes the current position in the query as a compiled cursor.

    Args:
      cc: The compiled cursor to fill out.
    """
    position = cc.add_position()
    start_key = self.__position[0] + '!' + str(self.__num_results).zfill(10)
    position.set_start_key(start_key)

  def _GetResult(self):
    """Returns the next result from the result set, without deduplication.

    Returns:
      (path, value): The path and value of the next result.
    """
    if self.__position[1]:
      self.__position = (self.__position[1], None)

    if not self.__cursor:
      return None, None
    row = self.__cursor.fetchone()
    if not row:
      self.__cursor = None
      return None, None
    path, data, position_parts = str(row[0]), row[1], row[2:]
    position = ''.join(str(x) for x in position_parts)

    if self.__query.order_list():
      direction = self.__query.order(0).direction()
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    if self.__query.has_end_compiled_cursor():
      start_key = self.__query.end_compiled_cursor().position(0).start_key()
      if direction == datastore_pb.Query_Order.ASCENDING:
        if position > start_key:
          self.__cursor = None
          return None, None
      elif direction == datastore_pb.Query_Order.DESCENDING:
        if position < start_key:
          self.__cursor = None
          return None, None

    self.__position = (self.__position[0], position)
    return path, data

  def _Next(self):
    """Fetches the next unique result from the result set.

    Returns:
      A datastore_pb.EntityProto instance.
    """
    if self._HasNext():
      self.__seen.add(self.__next_result[0])
      entity = entity_pb.EntityProto(self.__next_result[1])
      self.__next_result = None, None
      return entity
    return None

  def _HasNext(self):
    """Prefetches the next result and returns true if successful

    Returns:
      A boolean that indicates if there are more results.
    """
    while self.__cursor and (
        not self.__next_result[0] or self.__next_result[0] in self.__seen):
      self.__next_result = self._GetResult()
    if self.__next_result[0]:
      return True
    return False

  def Skip(self, count):
    """Skips the specified number of unique results.

    Args:
      count: Number of results to skip.

    Returns:
      A number indicating how many results where actually skipped.
    """
    for i in xrange(count):
      if not self._Next():
        return i
    return count

  def ResumeFromCompiledCursor(self, cc):
    """Resumes a query from a compiled cursor.

    Args:
      cc: The compiled cursor to resume from.
    """
    target_position, _ = cc.position(0).start_key().split('!')

    if self.__query.order_list():
      direction = self.__query.order(0).direction()
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    if direction == datastore_pb.Query_Order.ASCENDING:
      if (self.__query.has_end_compiled_cursor() and target_position >=
          self.__query.end_compiled_cursor().position(0).start_key()):
        self.__position = (target_position, target_position)
        self.__cursor = None
        return

      while self.__position[1] <= target_position and self.__cursor:
        self.__next_result = self._GetResult()

    elif direction == datastore_pb.Query_Order.DESCENDING:
      if (self.__query.has_end_compiled_cursor() and target_position <=
          self.__query.end_compiled_cursor().position(0).start_key()):
        self.__position = (target_position, target_position)
        self.__cursor = None
        return

      while self.__position[1] >= target_position and self.__cursor:
        self.__next_result = self._GetResult()

  def PopulateQueryResult(self, count, offset, result):
    """Populates a QueryResult PB with results from the cursor.

    Args:
      count: The number of results to retrieve.
      offset: The number of results to skip.
      result: out: A query_result PB.
    """
    limited_offset = min(offset, _MAX_QUERY_OFFSET)
    if limited_offset:
      result.set_skipped_results(self.Skip(limited_offset))

    if offset == limited_offset:
      if count > _MAXIMUM_RESULTS:
        count = _MAXIMUM_RESULTS

      result_list = result.result_list()
      while len(result_list) < count:
        if self.limit is not None and len(self.__seen) >= self.limit:
          break
        entity = self._Next()
        if entity is None:
          break
        result_list.append(entity)

    result.set_keys_only(self.__query.keys_only())
    result.set_more_results(self._HasNext())
    self._EncodeCompiledCursor(result.mutable_compiled_cursor())

class DatastoreDistributed():
  """Persistent stub for the Python datastore API.

  Stores all entities in an MySQL database. A DatastoreDistributed instance
  handles a single app's data.
  """

  WRITE_ONLY = entity_pb.CompositeIndex.WRITE_ONLY
  READ_WRITE = entity_pb.CompositeIndex.READ_WRITE
  DELETED = entity_pb.CompositeIndex.DELETED
  ERROR = entity_pb.CompositeIndex.ERROR

  _INDEX_STATE_TRANSITIONS = {
      WRITE_ONLY: frozenset((READ_WRITE, DELETED, ERROR)),
      READ_WRITE: frozenset((DELETED,)),
      ERROR: frozenset((DELETED,)),
      DELETED: frozenset((ERROR,)),
  }

  def __init__(self):
    """
       Constructor.
    """
    self.__transDict = {}
    self.__transDict_lock = threading.Lock()
    self.__last_gc_time = 0

    self.__id_map = {}
    self.__id_lock = threading.Lock()

    self.__connection = MySQLdb.connect(host=_DB_LOCATION, db=_USE_DATABASE, user=_DB_USER)
    self.__connection_lock = threading.Lock()
    self.__cursors = {}

    self.__namespaces = set()

    self.__indexes = {}
    self.__index_lock = threading.Lock()

    try:
      self.__setupDB()
    except Exception, e:
      raise datastore_errors.InternalError('%s' % str(e))

  def __setupDB(self):
    """Initializes MySQL database and creates required tables."""
    self.__connection_lock.acquire()
    self.__connection = MySQLdb.connect(host=_DB_LOCATION, db=_USE_DATABASE, user=_DB_USER)
    cursor = self.__connection.cursor()

    for sql_command in _NAMESPACE_TABLES:
      try:
        cursor.execute(sql_command)
      except MySQLdb.IntegrityError, e:
        print "ERROR creating namespace table!"
        print str(e)
    self.__connection.commit()
    #print cursor.execute('show tables')
    #print cursor.fetchall()

    # If the tables were not created, see what apps/namespaces exist
    cursor.execute('SELECT app_id, name_space FROM Namespaces')
    self.__namespaces = set(cursor.fetchall())

    # What apps already exist?
    cursor.execute('SELECT app_id, indexes FROM Apps')
    for app_id, index_proto in cursor.fetchall():
      index_map = self.__indexes.setdefault(app_id, {})
      if not index_proto:
        continue
      indexes = datastore_pb.CompositeIndices(index_proto)
      for index in indexes.index_list():
        index_map.setdefault(index.definition().entity_type(), []).append(index)
    # TODO(nchohan)
    # Looks like we are not storing index info in self.__indexes
    # When GetIndicies are called it should return the indexes for said app
    self.__connection_lock.release() 
  def Clear(self):
    pass

  def Read(self):
    pass

  def Write(self):
    pass

  def SetTrusted(self, trusted):
    """
    A trusted app can write to datastores of other apps.
    Args:
      trusted: boolean.
    """
    self.__trusted = trusted

  @staticmethod
  def __MakeParamList(size):
    """Returns a comma separated list of MySQL substitution parameters.

    Args:
      size: Number of parameters in returned list.
    Returns:
      A comma separated list of substitution parameters.
    """
    return ','.join(['%s'] * size)

  @staticmethod
  def __GetEntityKind(key):
    if isinstance(key, entity_pb.EntityProto):
      key = key.key()
    return key.path().element_list()[-1].type()

  @staticmethod
  def __EncodeIndexPB(pb):
    def _encode_path(pb):
      path = []
      for e in pb.element_list():
        if e.has_name():
          id = e.name()
        elif e.has_id():
          id = str(e.id()).zfill(10)
        path.append('%s:%s' % (e.type(), id))
      val = '!'.join(path)
      return val

    if isinstance(pb, entity_pb.PropertyValue) and pb.has_uservalue():
      userval = entity_pb.PropertyValue()
      userval.mutable_uservalue().set_email(pb.uservalue().email())
      userval.mutable_uservalue().set_auth_domain(pb.uservalue().auth_domain())
      userval.mutable_uservalue().set_gaiaid(0)
      pb = userval

    encoder = sortable_pb_encoder.Encoder()
    pb.Output(encoder)

    if isinstance(pb, entity_pb.PropertyValue):
      return buffer(encoder.buffer().tostring())
    elif isinstance(pb, entity_pb.Path):
      return buffer(_encode_path(pb))

  @staticmethod
  def __AddQueryParam(params, param):
    params.append(param)
    return len(params)

  @staticmethod
  def __CreateFilterString(filter_list, params):
    """Transforms a filter list into an SQL WHERE clause.

    Args:
      filter_list: The list of (property, operator, value) filters
        to transform. A value_type of -1 indicates no value type comparison
        should be done.
      params: out: A list of parameters to pass to the query.
    Returns:
      An SQL 'where' clause.
    """
    clauses = []
    for prop, operator, value in filter_list:
      sql_op = _OPERATOR_MAP[operator]

      value_index = DatastoreDistributed.__AddQueryParam(params, value)
      clauses.append('%s %s %%s' % (prop, sql_op))

    filters = ' AND '.join(clauses)
    if filters:
      filters = 'WHERE ' + filters
    return filters

  @staticmethod
  def __CreateOrderString(order_list):
    """Returns an 'ORDER BY' clause from the given list of orders.

    Args:
      order_list: A list of (field, order) tuples.
    Returns:
      An SQL ORDER BY clause.
    """
    orders = ', '.join('%s %s' % (x[0], _ORDER_MAP[x[1]]) for x in order_list)
    if orders:
      orders = 'ORDER BY ' + orders
    return orders

  def __ValidateAppId(self, app_id):
    """Verify that this is the stub for app_id.

    Args:
      app_id: An application ID.

    Raises:
      datastore_errors.BadRequestError: if this is not the stub for app_id.
    """
    assert app_id

  def __ValidateTransaction(self, tx):
    """Verify that this transaction exists and is valid.

    Args:
      tx: datastore_pb.Transaction

    Raises:
      datastore_errors.BadRequestError: if the tx is valid or doesn't exist.
    """
    assert isinstance(tx, datastore_pb.Transaction)
    self.__ValidateAppId(tx.app())

  def __ValidateKey(self, key):
    """Validate this key.

    Args:
      key: entity_pb.Reference

    Raises:
      datastore_errors.BadRequestError: if the key is invalid
    """
    assert isinstance(key, entity_pb.Reference)

    self.__ValidateAppId(key.app())

  def __get_connection(self, txnid):
    conn = None
    self.__gc()

    # This gets a new connection
    if txnid == 0:
      return MySQLdb.connect(host=_DB_LOCATION, db=_USE_DATABASE, user=_DB_USER)

    self.__transDict_lock.acquire()
    if txnid in self.__transDict:
      conn, entity_group, start_time = self.__transDict[txnid]
    self.__transDict_lock.release()
    if not conn: 
      raise MySQLdb.Error(1, "Connection timed out")
    return conn

  # clean up expired connections
  def __gc(self):
    curtime = time.time()
    if curtime < self.__last_gc_time + _GC_TIME:
      return
    self.__transDict_lock.acquire()
    del_list = []
    for ii in self.__transDict:
      cu, eg, st = self.__transDict[ii]
      if st + _MAX_TIMEOUT < curtime:
        del_list.append(ii)
    # safe deletes
    del_list.reverse()
    for ii in del_list:
      del self.__transDict[ii]
    self.__transDict_lock.release()
    last_gc_time = time.time()

  def setup_transaction(self, app_id):
    # New connection 
    txn_id = zoo_keeper.getTransactionID(app_id)
    client = MySQLdb.connect(host=_DB_LOCATION, db=_USE_DATABASE, user=_DB_USER)
    #TODO is this lock a bottle neck, and is it really required?
    self.__transDict_lock.acquire()
    # entity group is set to None
    self.__transDict[txn_id] = client, None, time.time()
    self.__transDict_lock.release()
    return txn_id

  def __cleanupConnection(self, txnid):
    self.__transDict_lock.acquire()
    if txnid in self.__transDict:
      client, ent_group, start_time = self.__transDict[txnid]
      del self.__transDict[txnid]
    self.__transDict_lock.release()
    return

  def __getEntityGroup(self, transaction):
    """ Get the entity group associated with a transaction
    """
    if transaction.has_handle(): 
      txnid = transaction.handle()
      self.__transDict_lock.acquire()
      if txnid in self.__transDict:
        client, ent_group, start_time = self.__transDict[txnid]
        self.__transDict_lock.release()
        return ent_group
      self.__transDict_lock.release()
    return None 


  def __GetConnection(self, transaction):
    """Retrieves a connection to the MySQL DB.

    If a transaction is supplied, the transaction's connection is returned, else a new one

    Args:
      transaction 
    Returns:
      a connection
    """
    self.__checkConnection()
    txn_id = 0
    if transaction and transaction.has_handle(): txn_id = transaction.handle()
    return self.__get_connection(txn_id)

  def __checkConnection(self):
    self.__connection_lock.acquire()
    if self.__connection.open == 0:
      self.__connection = MySQLdb.connect(host=_DB_LOCATION, db=_USE_DATABASE, user=_DB_USER)
    self.__connection_lock.release()

  def __ReleaseConnection(self, conn, rollback=False):
    """Releases a connection for use by other operations.

       Only for non-transactional operations

    Args:
      conn: An MySQL connection object.
      transaction: A Transaction PB.
      rollback: If True, roll back the database TX instead of committing it.
    """
    if rollback:
      conn.rollback()
    else:
      conn.commit()
     
    #conn.cursor.close()
    conn.close()

  def __ConfigureNamespace(self, prefix, app_id, name_space):
    """Ensures the relevant tables and indexes exist.

    Args:
      conn: An MySQL database connection.
      prefix: The namespace prefix to configure.
      app_id: The app ID.
      name_space: The per-app namespace name.
    """
    self.__checkConnection()
    conn = self.__connection
    format_args = {'app_id': app_id, 'name_space': name_space, 'prefix': prefix}
    cursor = conn.cursor()
    for sql_command in _NAMESPACE_SCHEMA:
      try:
        cursor.execute(sql_command % format_args)
      except MySQLdb.IntegrityError, e:
        print "ERROR creating namespace!"
        print str(e)
        return False
    conn.commit()
    return True

  def __WriteIndexData(self, conn, app):
    """Writes index data to disk.

    Args:
      conn: An MySQL connection.
      app: The app ID to write indexes for.
    """
    indices = datastore_pb.CompositeIndices()
    for indexes in self.__indexes[app].values():
      indices.index_list().extend(indexes)

    cursor = conn.cursor()
    cursor.execute('UPDATE Apps SET indexes = %s WHERE app_id = %s',
                   (app, indices.Encode()))

  def __GetTablePrefix(self, data):
    """Returns the namespace prefix for a query.

    Args:
      data: An Entity, Key or Query PB, or an (app_id, ns) tuple.
    Returns:
      A valid table prefix
    """
    if isinstance(data, entity_pb.EntityProto):
      data = data.key()
    if not isinstance(data, tuple):
      data = (data.app(), data.name_space())
    prefix = ('%s_%s' % data).replace('"', '""')
    prefix = formatTableName(prefix)
    if data not in self.__namespaces:
      if self.__ConfigureNamespace(prefix, *data): 
        self.__namespaces.add(data)
    return prefix

  def __DeleteRows(self, conn, paths, table):
    """Deletes rows from a table.

    Args:
      conn: An MySQL connection.
      paths: Paths to delete.
      table: The table to delete from.
    Returns:
      The number of rows deleted.
    """
    cursor = conn.cursor()
    sql_command = 'DELETE FROM %s WHERE __path__ IN (%s)'%(table, self.__MakeParamList(len(paths)))
    cursor.execute(sql_command, paths)
    return cursor.rowcount

  def __DeleteEntityRows(self, conn, keys, table):
    """Deletes rows from the specified table that index the keys provided.

    Args:
      conn: A database connection.
      keys: A list of keys to delete index entries for.
      table: The table to delete from.
    Returns:
      The number of rows deleted.
    """
    keys = sorted((x.app(), x.name_space(), x) for x in keys)
    for (app_id, ns), group in itertools.groupby(keys, lambda x: x[:2]):
      path_strings = [self.__EncodeIndexPB(x[2].path()) for x in group]
      prefix = self.__GetTablePrefix((app_id, ns))
      return self.__DeleteRows(conn, path_strings, '%s_%s' % (prefix, table))

  def __DeleteIndexEntries(self, conn, keys):
    """Deletes entities from the index.

    Args:
      conn: An MySQL connection.
      keys: A list of keys to delete.
    """
    self.__DeleteEntityRows(conn, keys, 'EntitiesByProperty')

  def __InsertEntities(self, conn, entities):
    """Inserts or updates entities in the DB.

    Args:
      conn: A database connection.
      entities: A list of entities to store.
    """

    def RowGenerator(entities):
      for unused_prefix, e in entities:
        yield (self.__EncodeIndexPB(e.key().path()),
               self.__GetEntityKind(e),
               buffer(e.Encode()))

    entities = sorted((self.__GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      cursor = conn.cursor()
      group_rows = RowGenerator(group)
      cursor.executemany(
          'REPLACE INTO %s_Entities VALUES (%%s, %%s, %%s)' % prefix,
          tuple(group_rows))

  def __InsertIndexEntries(self, conn, entities):
    """Inserts index entries for the supplied entities.

    Args:
      conn: A database connection.
      entities: A list of entities to create index entries for.
    """
    def RowGenerator(entities):
      all_rows = []
      for unused_prefix, e in entities:
        for p in e.property_list():
          p_vals = [self.__GetEntityKind(e), p.name(), self.__EncodeIndexPB(p.value()), self.__EncodeIndexPB(e.key().path())]

          hashed_index = md5.new(''.join(p_vals[:2]))
          hashed_index.update(p_vals[2]) #buffer values cannot be joined into a string
          hashed_index.update(p_vals[3])
          p_vals.append( hashed_index.hexdigest() )
          all_rows.append(p_vals)
      return tuple(ii for ii in all_rows)

    entities = sorted((self.__GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      cursor = conn.cursor()
      group_rows = RowGenerator(group)
      cursor.executemany(
        """INSERT INTO %s_EntitiesByProperty (kind, name, value, __path__, hashed_index) VALUES (%%s, %%s, %%s, %%s, %%s)""" % prefix, group_rows)

  def __AllocateIds(self, conn, prefix, size=None, max=None):
    """Allocates IDs.

    Args:
      conn: A MySQL connection object.
      prefix: A table namespace prefix.
      size: Number of IDs to allocate.
      max: Upper bound of IDs to allocate.

    Returns:
      int: The beginning of a range of size IDs
    """
    self.__id_lock.acquire()
    ret = None
    cursor = conn.cursor()
    if size is not None:
      assert size > 0
      next_id, block_size = self.__id_map.get(prefix, (0, 0))
      if not block_size:
        block_size = (size / 1000 + 1) * 1000
        # Potential race condition here with assigning the same id to 
        # multiple appengines
        cursor.execute('SELECT next_id FROM IdSeq WHERE prefix = %s LIMIT 1',
                       prefix)
        next_id = cursor.fetchone()[0]
        #@if next_id:
         # check if there was a row, if not create it 
        
        cursor.execute(
            'UPDATE IdSeq SET next_id = next_id + %s WHERE prefix = %s',
            (block_size, prefix))
        assert int(cursor.rowcount) == 1

      if size > block_size:
        cursor.execute('SELECT next_id FROM IdSeq WHERE prefix = %s LIMIT 1',
                       (prefix,))
        ret = cursor.fetchone()[0]
        cursor.execute(
            'UPDATE IdSeq SET next_id = next_id + %s WHERE prefix = %s',
            (size, prefix))
        assert int(cursor.rowcount) == 1
      else:
        ret = next_id;
        next_id += size
        block_size -= size
        self.__id_map[prefix] = (next_id, block_size)
    else:
      cursor.execute('SELECT next_id FROM IdSeq WHERE prefix = %s LIMIT 1',
                       (prefix,))
      ret = cursor.fetchone()[0]
      if max and max >= ret:
        cursor.execute(
            'UPDATE IdSeq SET next_id = %s WHERE prefix = %s',
            (max + 1, prefix))
        assert int(cursor.rowcount) == 1
    self.__id_lock.release()
    return ret

  def __AcquireLockForEntityGroup(self, app_id, conn, txn_id, entity_group='', timeout=30):
    """Acquire a lock for a specified entity group. Only get it if not already locked.

    Args:
      conn: A MySQL connection.
      entity_group: An entity group.
      timeout: Number of seconds till a lock expires.
    """
    self.__transDict_lock.acquire()
    eg_on_record = None #eg is short for entity_group
    if txn_id in self.__transDict:
      conn, eg_on_record, start_time = self.__transDict[txn_id]
    if eg_on_record == None:
      self.__transDict[txn_id] = conn, entity_group, time.time()
      self.__transDict_lock.release()
    else: # Already set
      self.__transDict_lock.release()
      return 

    cursor = conn.cursor()
    lock_str = app_id + '_' + entity_group
    cursor.execute("SELECT GET_LOCK('%s', %i);" % (lock_str, timeout))
    conn.commit()

  def __ReleaseLockForEntityGroup(self, app_id, entity_group=''):
    """Release transaction lock if present.

    Args:
      app_id
      entity_group: An entity group.
    """
    self.__checkConnection()
    cursor = self.__connection.cursor()
    lock_str = app_id + '_' + entity_group
    cursor.execute("SELECT RELEASE_LOCK('%s');" % lock_str)
    self.__connection.commit()

  @staticmethod
  def __ExtractEntityGroupFromKeys(app_id, keys):
    """Extracts entity group."""
    path = keys[0].path()
    element_list = path.element_list()
    def __getRootKey(app_id, ancestor_list):
      key = app_id # mysql cannot have \ as the first char in the row key
      a = ancestor_list[0]
      key += "/"

      # append _ if the name is a number, prevents collisions of key names
      if a.has_type():
        key += a.type()
      else:
        return None

      if a.has_id():
        zero_padded_id = ("0" * (ID_KEY_LENGTH - len(str(a.id())))) + str(a.id())
        key += ":" + zero_padded_id
      elif a.has_name():
        if a.name().isdigit():
          key += ":__key__" + a.name()
        else:
          key += ":" + a.name()
      else:
        return None

      return key
    return __getRootKey(app_id, element_list)   

  def AssertPbIsInitialized(self, pb):
    """Raises an exception if the given PB is not initialized and valid."""
    explanation = []
    assert pb.IsInitialized(explanation), explanation
    pb.Encode()

  def QueryHistory(self):
    """Returns a dict that maps Query PBs to times they've been run."""
    return []
          

  def __PutEntities(self, conn, entities):
    self.__DeleteIndexEntries(conn, [e.key() for e in entities])
    self.__InsertEntities(conn, entities)
    self.__InsertIndexEntries(conn, entities)

  def __DeleteEntities(self, conn, keys):
    self.__DeleteIndexEntries(conn, keys)
    self.__DeleteEntityRows(conn, keys, 'Entities')

  def _Dynamic_Put(self, app_id, put_request, put_response):
    conn = self.__GetConnection(put_request.transaction())
    try:
      entities = put_request.entity_list()
      keys = [e.key() for e in entities]
      if put_request.has_transaction():
        entity_group = self.__ExtractEntityGroupFromKeys(app_id, keys)
        txn_id = put_request.transaction().handle()
        self.__AcquireLockForEntityGroup(app_id, conn, txn_id, entity_group)
      for entity in entities:
        self.__ValidateKey(entity.key())

        for prop in itertools.chain(entity.property_list(),
                                    entity.raw_property_list()):
          if prop.value().has_uservalue():
            uid = md5.new(prop.value().uservalue().email().lower()).digest()
            uid = '1' + ''.join(['%02d' % ord(x) for x in uid])[:20]
            prop.mutable_value().mutable_uservalue().set_obfuscated_gaiaid(uid)

        assert entity.has_key()
        assert entity.key().path().element_size() > 0

        last_path = entity.key().path().element_list()[-1]
        if last_path.id() == 0 and not last_path.has_name():
          id_ = self.__AllocateIds(conn, self.__GetTablePrefix(entity.key()), 1)
          last_path.set_id(id_)

          assert entity.entity_group().element_size() == 0
          group = entity.mutable_entity_group()
          root = entity.key().path().element(0)
          group.add_element().CopyFrom(root)

        else:
          assert (entity.has_entity_group() and
                  entity.entity_group().element_size() > 0)

      self.__PutEntities(conn, entities)
      put_response.key_list().extend([e.key() for e in entities])
    except Exception, e:
      print str(e)
    finally:
      if not put_request.has_transaction():
        self.__ReleaseConnection(conn)

  def _Dynamic_Get(self, app_id, get_request, get_response):
    conn = self.__GetConnection(get_request.transaction())
    try:
      keys = get_request.key_list()
      if get_request.has_transaction():
          entity_group = self.__ExtractEntityGroupFromKeys(app_id, keys)
          txn_id = get_request.transaction().handle()
          self.__AcquireLockForEntityGroup(app_id, conn, txn_id, entity_group)
      for key in keys:
        self.__ValidateAppId(key.app())
        prefix = self.__GetTablePrefix(key)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT entity FROM %s_Entities WHERE __path__ = %%s'%prefix,
            (self.__EncodeIndexPB(key.path()),))
        group = get_response.add_entity()
        row = cursor.fetchone()
        if row:
          group.mutable_entity().ParseFromString(row[0])
    finally:
      if not get_request.has_transaction():
        self.__ReleaseConnection(conn)

  def _Dynamic_Delete(self, app_id, delete_request, delete_response):
    conn = self.__GetConnection(delete_request.transaction())
    try:
      keys = delete_request.key_list()
      if delete_request.has_transaction():
        entity_group = self.__ExtractEntityGroupFromKeys(app_id, keys)
        txn_id = delete_request.transaction().handle()
        self.__AcquireLockForEntityGroup(app_id, conn, txn_id, entity_group)
      self.__DeleteEntities(conn, delete_request.key_list())
    finally:
      if not delete_request.has_transaction():
        self.__ReleaseConnection(conn)
  def __GenerateFilterInfo(self, filters, query):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
      query: The query to generate filter info for.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """
    filter_info = {}
    for filt in filters:
      assert filt.property_size() == 1
      prop = filt.property(0)
      value = prop.value()
      if prop.name() == '__key__':
        value = ReferencePropertyToReference(value.referencevalue())
        assert value.app() == query.app()
        assert value.name_space() == query.name_space()
        value = value.path()
      filter_info.setdefault(prop.name(), []).append(
          (filt.op(), self.__EncodeIndexPB(value)))
    return filter_info

  def __GenerateOrderInfo(self, orders):
    """Transform a list of orders into a more usable form.

    Args:
      orders: A list of order PBs.
    Returns:
      A list of (property, direction) tuples.
    """
    orders = [(order.property(), order.direction()) for order in orders]
    if orders and orders[-1] == ('__key__', datastore_pb.Query_Order.ASCENDING):
      orders.pop()
    return orders

  def __GetPrefixRange(self, prefix):
    """Returns a (min, max) range that encompasses the given prefix.

    Args:
      prefix: A string prefix to filter for. Must be a PB encodable using
        __EncodeIndexPB.
    Returns:
      (min, max): Start and end string values to filter on.
    """
    ancestor_min = self.__EncodeIndexPB(prefix)
    ancestor_max = buffer(str(ancestor_min) + '\xfb\xff\xff\xff\x89')
    return ancestor_min, ancestor_max

  def  __KindQuery(self, query, filter_info, order_info):
    """Performs kind only, kind and ancestor, and ancestor only queries."""
    if not (set(filter_info.keys()) |
            set(x[0] for x in order_info)).issubset(['__key__']):
      return None
    if len(order_info) > 1:
      return None

    filters = []
    filters.extend(('__path__', op, value) for op, value
                   in filter_info.get('__key__', []))
    if query.has_kind():
      filters.append(('kind', datastore_pb.Query_Filter.EQUAL, query.kind()))
    if query.has_ancestor():
      amin, amax = self.__GetPrefixRange(query.ancestor().path())
      filters.append(('__path__',
                      datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL, amin))
      filters.append(('__path__', datastore_pb.Query_Filter.LESS_THAN, amax))

    if order_info:
      orders = [('__path__', order_info[0][1])]
    else:
      orders = [('__path__', datastore_pb.Query_Order.ASCENDING)]

    params = []
    query = ('SELECT Entities.__path__, Entities.entity, %s '
             'FROM %s_Entities AS Entities %s %s' % (
                 ','.join(x[0] for x in orders),
                 self.__GetTablePrefix(query),
                 self.__CreateFilterString(filters, params),
                 self.__CreateOrderString(orders)))
    return query, params

  def __SinglePropertyQuery(self, query, filter_info, order_info):
    """Performs queries satisfiable by the EntitiesByProperty table."""
    property_names = set(filter_info.keys())
    property_names.update(x[0] for x in order_info)
    property_names.discard('__key__')
    if len(property_names) != 1:
      return None

    property_name = property_names.pop()
    filter_ops = filter_info.get(property_name, [])

    if len([1 for o, _ in filter_ops
            if o == datastore_pb.Query_Filter.EQUAL]) > 1:
      return None

    if len(order_info) > 1 or (order_info and order_info[0][0] == '__key__'):
      return None

    if query.has_ancestor():
      return None

    if not query.has_kind():
      return None

    prefix = self.__GetTablePrefix(query)
    filters = []
    filters.append(('EntitiesByProperty.kind',
                    datastore_pb.Query_Filter.EQUAL, query.kind()))
    filters.append(('name', datastore_pb.Query_Filter.EQUAL, property_name))
    for op, value in filter_ops:
      if property_name == '__key__':
        filters.append(('EntitiesByProperty.__path__', op, value))
      else:
        filters.append(('value', op, value))

    orders = [('EntitiesByProperty.kind', datastore_pb.Query_Order.ASCENDING),
              ('name', datastore_pb.Query_Order.ASCENDING)]
    if order_info:
      orders.append(('value', order_info[0][1]))
    else:
      orders.append(('value', datastore_pb.Query_Order.ASCENDING))
    orders.append(('EntitiesByProperty.__path__',
                   datastore_pb.Query_Order.ASCENDING))

    params = []
    format_args = (
        ','.join(x[0] for x in orders[2:]),
        prefix,
        prefix,
        self.__CreateFilterString(filters, params),
        self.__CreateOrderString(orders))
    query = ('SELECT Entities.__path__, Entities.entity, %s '
             'FROM %s_EntitiesByProperty AS EntitiesByProperty INNER JOIN '
             "%s_Entities AS Entities USING (__path__) %s %s" % format_args)
    return query, params

  def __StarSchemaQueryPlan(self, query, filter_info, order_info):
    """Executes a query using a 'star schema' based on EntitiesByProperty.

    A 'star schema' is a join between an objects table (Entities) and multiple
    instances of a facts table (EntitiesByProperty). Ideally, this will result
    in a merge join if the only filters are inequalities and the sort orders
    match those in the index for the facts table; otherwise, the DB will do its
    best to satisfy the query efficiently.

    Args:
      query: The datastore_pb.Query PB.
      filter_info: A dict mapping properties filtered on to (op, value) tuples.
      order_info: A list of (property, direction) tuples.
    Returns:
      (query, params): An SQL query string and list of parameters for it.
    """
    filter_sets = []
    for name, filter_ops in filter_info.items():
      filter_sets.extend((name, [x]) for x in filter_ops
                         if x[0] == datastore_pb.Query_Filter.EQUAL)
      ineq_ops = [x for x in filter_ops
                  if x[0] != datastore_pb.Query_Filter.EQUAL]
      if ineq_ops:
        filter_sets.append((name, ineq_ops))

    for prop, _ in order_info:
      if prop == '__key__':
        continue
      if prop not in filter_info:
        filter_sets.append((prop, []))

    prefix = self.__GetTablePrefix(query)

    joins = []
    filters = []
    join_name_map = {}
    for name, filter_ops in filter_sets:
      join_name = 'ebp_%d' % (len(joins),)
      join_name_map.setdefault(name, join_name)
      joins.append(
          'INNER JOIN %s_EntitiesByProperty AS %s '
          'ON Entities.__path__ = %s.__path__'
          % (prefix, join_name, join_name))
      filters.append(('%s.kind' % join_name, datastore_pb.Query_Filter.EQUAL,
                      query.kind()))
      filters.append(('%s.name' % join_name, datastore_pb.Query_Filter.EQUAL,
                      name))
      for op, value in filter_ops:
        filters.append(('%s.value' % join_name, op, buffer(value)))
      if query.has_ancestor():
        amin, amax = self.__GetPrefixRange(query.ancestor().path())
        filters.append(('%s.__path__' % join_name,
                        datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL, amin))
        filters.append(('%s.__path__' % join_name,
                        datastore_pb.Query_Filter.LESS_THAN, amax))

    orders = []
    for prop, order in order_info:
      if prop == '__key__':
        orders.append(('Entities.__path__', order))
      else:
        prop = '%s.value' % (join_name_map[prop],)
        orders.append((prop, order))
    if not order_info or order_info[-1][0] != '__key__':
      orders.append(('Entities.__path__', datastore_pb.Query_Order.ASCENDING))

    params = []
    format_args = (
        ','.join(x[0] for x in orders),
        prefix,
        ' '.join(joins),
        self.__CreateFilterString(filters, params),
        self.__CreateOrderString(orders))
    query = ('SELECT Entities.__path__, Entities.entity, %s '
             'FROM %s_Entities AS Entities %s %s %s' % format_args)
    return query, params

  def __MergeJoinQuery(self, query, filter_info, order_info):
    if order_info:
      return None
    if query.has_ancestor():
      return None
    if not query.has_kind():
      return None
    for filter_ops in filter_info.values():
      for op, _ in filter_ops:
        if op != datastore_pb.Query_Filter.EQUAL:
          return None

    return self.__StarSchemaQueryPlan(query, filter_info, order_info)

  def __LastResortQuery(self, query, filter_info, order_info):
    """Last resort query plan that executes queries requring composite indexes.

    Args:
      query: The datastore_pb.Query PB.
      filter_info: A dict mapping properties filtered on to (op, value) tuples.
      order_info: A list of (property, direction) tuples.
    Returns:
      (query, params): An SQL query string and list of parameters for it.
    """
    index = self.__FindIndexForQuery(query)
    if not index:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.NEED_INDEX,
          'This query requires a composite index that is not defined. '
          'You must update the index.yaml file in your application root.')
    return self.__StarSchemaQueryPlan(query, filter_info, order_info)

  def __FindIndexForQuery(self, query):
    """Finds an index that can be used to satisfy the provided query.

    Args:
      query: A datastore_pb.Query PB.
    Returns:
      An entity_pb.CompositeIndex PB, if a suitable index exists; otherwise None
    """
    unused_required, kind, ancestor, props, num_eq_filters = (
        datastore_index.CompositeIndexForQuery(query))
    required_key = (kind, ancestor, props)
    indexes = self.__indexes.get(query.app(), {}).get(kind, [])

    eq_filters_set = set(props[:num_eq_filters])
    remaining_filters = props[num_eq_filters:]
    for index in indexes:
      definition = datastore_index.ProtoToIndexDefinition(index)
      index_key = datastore_index.IndexToKey(definition)
      if required_key == index_key:
        return index
      if num_eq_filters > 1 and (kind, ancestor) == index_key[:2]:
        this_props = index_key[2]
        this_eq_filters_set = set(this_props[:num_eq_filters])
        this_remaining_filters = this_props[num_eq_filters:]
        if (eq_filters_set == this_eq_filters_set and
            remaining_filters == this_remaining_filters):
          return index

  _QUERY_STRATEGIES = [
      __KindQuery,
      __SinglePropertyQuery,
      __MergeJoinQuery,
      __LastResortQuery,
  ]

  def __GetQueryCursor(self, conn, query):
    """Returns an MySQL query cursor for the provided query.

    Args:
      conn: The MySQL connection.
      query: A datastore_pb.Query protocol buffer.
    Returns:
      A QueryCursor object.
    """
    if query.has_transaction() and not query.has_ancestor():
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Only ancestor queries are allowed inside transactions.')

    num_components = len(query.filter_list()) + len(query.order_list())
    if query.has_ancestor():
      num_components += 1
    if num_components > _MAX_QUERY_COMPONENTS:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          ('query is too large. may not have more than %s filters'
           ' + sort orders ancestor total' % _MAX_QUERY_COMPONENTS))

    app_id = query.app()
    self.__ValidateAppId(app_id)

    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list())

    filter_info = self.__GenerateFilterInfo(filters, query)
    order_info = self.__GenerateOrderInfo(orders)

    for strategy in DatastoreDistributed._QUERY_STRATEGIES:
      result = strategy(self, query, filter_info, order_info)
      if result:
        break
    else:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'No strategy found to satisfy query.')

    sql_stmt, params = result

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      start_key, n = query.compiled_cursor().position(0).start_key().split('!')
      new_offset = int(n)
      query.set_offset(new_offset)
      query.set_limit(query.limit() + new_offset)

    if query.has_limit() and query.limit() and query.has_offset():
      sql_stmt += ' LIMIT %i, %i' % (query.offset(), query.limit())
      query.set_offset(0)
    elif query.has_limit() and query.limit() and not query.has_offset():
      sql_stmt += ' LIMIT %i' % query.limit()

    db_cursor = conn.cursor()
    try:
      db_cursor.execute(sql_stmt, params)
    except Exception, e:
      db_cursor = None
    cursor = QueryCursor(query, db_cursor)
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor.ResumeFromCompiledCursor(query.compiled_cursor())

    clone = datastore_pb.Query()
    clone.CopyFrom(query)
    clone.clear_hint()
    clone.clear_limit()
    clone.clear_count()
    clone.clear_offset()

    return cursor

  def _Dynamic_Run_Query(self, app_id, query, query_result):
    conn = self.__GetConnection(query.transaction())
    try:
      cursor = self.__GetQueryCursor(conn, query)

      # reuse zk transaction id code for cursors also
      cursor_id = zoo_keeper.getTransactionID(app_id + "___cursor_id___")

      cursor_pb = query_result.mutable_cursor()
      cursor_pb.set_app(query.app())
      cursor_pb.set_cursor(cursor_id)

      if query.has_count():
        count = query.count()
      elif query.has_limit():
        count = query.limit()
      else:
        count = _BATCH_SIZE

      cursor.PopulateQueryResult(count, query.offset(), query_result)
      self.__cursors[cursor_pb] = cursor
    finally: 
      if not query.has_transaction():
        self.__ReleaseConnection(conn)

  def _Dynamic_Next(self, next_request, query_result):
    self.__ValidateAppId(next_request.cursor().app())

    try:
      cursor = self.__cursors[next_request.cursor()]
      # remove the reference
      self.__cursors[next_request.cursor()] = None
    except KeyError:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Cursor %d not found' % next_request.cursor().cursor())

    assert cursor.app == next_request.cursor().app()

    count = _BATCH_SIZE
    if next_request.has_count():
      count = next_request.count()
    cursor.PopulateQueryResult(count, next_request.offset(), query_result)

  def _Dynamic_Count(self, query, integer64proto):
    if query.has_limit():
      query.set_limit(min(query.limit(), _MAXIMUM_RESULTS))
    else:
      query.set_limit(_MAXIMUM_RESULTS)

    conn = self.__GetConnection(query.transaction())
    try:
      cursor = self.__GetQueryCursor(conn, query)
      integer64proto.set_value(cursor.Count())
    finally:
      if not query.has_transaction or not query.transaction.has_handle():
        self.__ReleaseConnection(conn)

  def _Dynamic_Commit(self, app_id, transaction, _):
    conn = self.__GetConnection(transaction)
    self.__ReleaseConnection(conn)
    entity_group = self.__getEntityGroup(transaction)
    self.__ReleaseLockForEntityGroup(app_id, entity_group)
    self.__cleanupConnection(transaction.handle())

  def _Dynamic_Rollback(self, app_id, transaction, _):
    conn = self.__GetConnection(transaction)
    self.__ReleaseConnection(conn, rollback=True)
    entity_group = self.__getEntityGroup(transaction)
    self.__ReleaseLockForEntityGroup(app_id, entity_group)
    self.__cleanupConnection(transaction.handle())

  def _Dynamic_AllocateIds(self, allocate_ids_request, allocate_ids_response):
    conn = self.__GetConnection(None)
    model_key = allocate_ids_request.model_key()
    self.__ValidateAppId(model_key.app())
    if allocate_ids_request.has_size() and allocate_ids_request.has_max():
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Both size and max cannot be set.')

    if allocate_ids_request.has_size():
      if allocate_ids_request.size() < 1:
        raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                               'Size must be greater than 0.')
      first_id = self.__AllocateIds(conn, self.__GetTablePrefix(model_key),
                                    size=allocate_ids_request.size())
      allocate_ids_response.set_start(first_id)
      allocate_ids_response.set_end(first_id + allocate_ids_request.size() - 1)
    else:
      if allocate_ids_request.max() < 0:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST,
            'Max must be greater than or equal to 0.')
      first_id = self.__AllocateIds(conn, self.__GetTablePrefix(model_key),
                                    max=allocate_ids_request.max())
      allocate_ids_response.set_start(first_id)
      allocate_ids_response.set_end(max(allocate_ids_request.max(),
                                        first_id - 1))

    self.__ReleaseConnection(conn)

  def __FindIndex(self, index):
    """Finds an existing index by definition.

    Args:
      index: entity_pb.CompositeIndex

    Returns:
      entity_pb.CompositeIndex, if it exists; otherwise None
    """
    app_indexes = self.__indexes.get(index.app_id(), {})
    for stored_index in app_indexes.get(index.definition().entity_type(), []):
      if index.definition() == stored_index.definition():
        return stored_index

    return None

  def _Dynamic_CreateIndex(self, index, id_response):
    app_id = index.app_id()
    kind = index.definition().entity_type()

    self.__ValidateAppId(app_id)
    if index.id() != 0:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'New index id must be 0.')

    self.__index_lock.acquire()

    # If it already exists, just return the index id
    if self.__FindIndex(index):
      self.__index_lock.release()
      id_response.set_value(self.__FindIndex(index))
      return 

    try:
        #raise apiproxy_errors.ApplicationError(
        #                          datastore_pb.Error.PERMISSION_DENIED,
        #                          'Index already exists.')
      
      next_id = max([idx.id() for x in self.__indexes.get(app_id, {}).values()
                     for idx in x] + [0]) + 1
      index.set_id(next_id)
      id_response.set_value(next_id)

      clone = entity_pb.CompositeIndex()
      clone.CopyFrom(index)
      self.__indexes.setdefault(app_id, {}).setdefault(kind, []).append(clone)

      conn = self.__GetConnection(None)
      try:
        self.__WriteIndexData(conn, app_id)
      finally:
        self.__ReleaseConnection(conn)
    except Exception, e:
      print str(e)
    finally:
      self.__index_lock.release()

  def _Dynamic_GetIndices(self, app_str, composite_indices):
    self.__ValidateAppId(app_str)

    index_list = composite_indices.index_list()
    for indexes in self.__indexes.get(app_str, {}).values():
      index_list.extend(indexes)

  def _Dynamic_UpdateIndex(self, index, _):
    self.__ValidateAppId(index.app_id())
    my_index = self.__FindIndex(index)
    if not my_index:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             "Index doesn't exist.")
    elif (index.state() != my_index.state() and
          index.state() not in self._INDEX_STATE_TRANSITIONS[my_index.state()]):
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Cannot move index state from %s to %s' %
          (entity_pb.CompositeIndex.State_Name(my_index.state()),
           (entity_pb.CompositeIndex.State_Name(index.state()))))

    self.__index_lock.acquire()
    try:
      my_index.set_state(index.state())
    finally:
      self.__index_lock.release()

  def _Dynamic_DeleteIndex(self, index, _):
    app_id = index.app_id()
    kind = index.definition().entity_type()
    self.__ValidateAppId(app_id)

    my_index = self.__FindIndex(index)
    if not my_index:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             "Index doesn't exist.")

    conn = self.__GetConnection(None)
    try:
      self.__WriteIndexData(conn, app_id)
    finally:
      self.__ReleaseConnection(conn)
    self.__index_lock.acquire()
    try:
      self.__indexes[app_id][kind].remove(my_index)
    finally:
      self.__index_lock.release()




logger = appscale_logger.getLogger("pb_server")

class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """
  @tornado.web.asynchronous
  def get(self):
    self.write("{'status':'up'}")
    self.finish() 
  # remote api request
  # sends back a response 
  def remote_request(self, app_id, http_request_data):
    apirequest = remote_api_pb.Request()
    apirequest.ParseFromString(http_request_data)
    apiresponse = remote_api_pb.Response()
    response = None
    errcode = 0
    errdetail = ""
    apperror_pb = None

    if not apirequest.has_method(): 
      errcode = datastore_pb.Error.BAD_REQUEST
      errdetail = "Method was not set in request"
      apirequest.set_method("NOT_FOUND")
    if not apirequest.has_request():
      errcode = datastore_pb.Error.BAD_REQUEST
      errdetail = "Request missing in call"
      apirequest.set_method("NOT_FOUND")
      apirequest.clear_request()
    method = apirequest.method()
    http_request_data = apirequest.request()
    if method == "Put":
      response, errcode, errdetail = self.put_request(app_id, 
                                                 http_request_data)
    elif method == "Get":
      response, errcode, errdetail = self.get_request(app_id, 
                                                 http_request_data)
    elif method == "Delete": 
      response, errcode, errdetail = self.delete_request(app_id, 
                                                    http_request_data)
    elif method == "RunQuery":
      response, errcode, errdetail = self.run_query(app_id, 
                                          http_request_data)
    elif method == "BeginTransaction":
      response, errcode, errdetail = self.begin_transaction_request(app_id, 
                                                      http_request_data)
    elif method == "Commit":
      response, errcode, errdetail = self.commit_transaction_request(app_id, 
                                                      http_request_data)
    elif method == "Rollback":
      response, errcode, errdetail = self.rollback_transaction_request(app_id, 
                                                        http_request_data)
    elif method == "AllocateIds":
      response, errcode, errdetail = self.allocate_ids_request(app_id, 
                                                http_request_data)
    elif method == "CreateIndex":
      response, errcode, errdetail = self.create_index(app_id, http_request_data)
    elif method == "GetIndices":
      response, errcode, errdetail = self.get_indices(app_id, http_request_data)

    elif method == "UpdateIndex":
      response, errcode, errdetail = self.update_index(app_id, http_request_data)
    elif method == "DeleteIndex":
      response, errcode, errdetail = self.delete_index(app_id, http_request_data)
    elif method == "Next":
      response, errcode, errdetail = self.next(app_id, http_request_data)
    elif method == "Count":
      response, errcode, errdetail = self.count(app_id, http_request_data)
    else:
      errcode = datastore_pb.Error.BAD_REQUEST 
      errdetail = "Unknown datastore message" 
      logger.debug(errdetail)
    
      
    apiresponse.set_response(response)
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)
    if errcode != 0:
      print "REPLY",method," AT TIME",time.time()
      print "errcode:",errcode
      print "errdetail:",errdetail
    self.write(apiresponse.Encode() )    

  def create_index(self, app_id, http_request_data):
    index = entity_pb.CompositeIndex(http_request_data)
    integer = api_base_pb.Integer64Proto()
    try:
      app_datastore._Dynamic_CreateIndex(index, integer)
    except Exception, e:
      print str(e)
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))
    return (integer.Encode(), 0, "")

  def get_indices(self, app_id, http_request_data):
    composite_indices = datastore_pb.CompositeIndices()
    try:
      app_datastore._Dynamic_GetIndices(app_id, composite_indices)
    except Exception, e:
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))
    return (composite_indices.Encode(), 0, "")

  def update_index(self, app_id, http_request_data):
    index = entity_pb.CompositeIndex(http_request_data)
    void_resp = api_base_pb.VoidProto()
    try:
      app_datastore._Dynamic_UpdateIndex(index, void_resp) 
    except Exception, e:
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))
    return (void_resp.Encode(), 0, "")

  def delete_index(self, app_id, http_request_data):
    index = entity_pb.Index(http_request_data)
    void_resp = api_base_pb.VoidProto().Encode()
    try:
      app_datastore._Dynamic_DeleteIndex(index, void_resp) 
    except Exception, e:
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))

    return (void_resp.Encode(), 0, "")

  def next(self, app_id, http_request_data):
    next_req = datastore_pb.NextRequest(http_request_data)
    next_res = datastore_pb.QueryResult()
    try:
      app_datastore._Dynamic_Next(next_req, next_res)
    except Exception, e:
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))
    return (next_res.Encode(), 0, "")

  def count(self, app_id, http_request_data):
    query = datastore_pb.Query(http_request_data)
    count = api_base_pb.Integer64Proto()
    
    try:
      app_datastore._Dynamic_Count(query, count)
    except Exception, e:
      return (api_base_pb.VoidProto().Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              str(e))
    return (count.Encode(), 0, "")


  def run_query(self, app_id, http_request_data):
    query = datastore_pb.Query(http_request_data)
    # Pack Results into a clone of QueryResult #
    clone_qr_pb = datastore_pb.QueryResult()
    app_datastore._Dynamic_Run_Query(app_id, query, clone_qr_pb)
    #logger.debug("QUERY_RESULT: %s" % clone_qr_pb)
    return (clone_qr_pb.Encode(), 0, "")


  def begin_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction()
    handle = 0
    #print "Begin Trans Handle:",handle
    handle = app_datastore.setup_transaction(app_id)
    transaction_pb.set_app(app_id)
    transaction_pb.set_handle(handle)
    return (transaction_pb.Encode(), 0, "")

  def commit_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction(http_request_data)
    txn_id = transaction_pb.handle() 
    commitres_pb = datastore_pb.CommitResponse()
    try:
      zoo_keeper.releaseLock(app_id, txn_id)
      app_datastore._Dynamic_Commit(app_id, transaction_pb, commitres_pb)
    except:
      return (commitres_pb.Encode(), datastore_pb.Error.PERMISSION_DENIED, "Unable to commit for this transaction")  
    return (commitres_pb.Encode(), 0, "")

  def rollback_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction(http_request_data)
    handle = transaction_pb.handle() 
    try:
      zoo_keeper.releaseLock(app_id, handle)
      app_datastore._Dynamic_Rollback(app_id, transaction_pb, None)
    except Exception, e:
      print str(e)
      return(api_base_pb.VoidProto().Encode(), datastore_pb.Error.PERMISSION_DENIED, "Unable to rollback for this transaction")
    print "Transaction with handle %d was roll backed"%handle
    return (api_base_pb.VoidProto().Encode(), 0, "")


  def allocate_ids_request(self, app_id, http_request_data): # kowshik
    global app_datastore
    #logger.info("inside allocate_ids_request handler")
    request = datastore_pb.AllocateIdsRequest(http_request_data)
    response = datastore_pb.AllocateIdsResponse()
    app_datastore._Dynamic_AllocateIds(request, response)
    return (response.Encode(), 0, "")

  def put_request(self, app_id, http_request_data):
    global app_datastore
    start_time = time.time() 
    putreq_pb = datastore_pb.PutRequest(http_request_data)
    logger.debug("RECEIVED PUT_REQUEST %s" % putreq_pb)
    putresp_pb = datastore_pb.PutResponse( )
    app_datastore._Dynamic_Put(app_id, putreq_pb, putresp_pb)
    return (putresp_pb.Encode(), 0, "")


  def get_request(self, app_id, http_request_data):
    global app_datastore
    getreq_pb = datastore_pb.GetRequest(http_request_data)
    logger.debug("GET_REQUEST: %s" % getreq_pb)
    getresp_pb = datastore_pb.GetResponse()
    app_datastore._Dynamic_Get(app_id, getreq_pb, getresp_pb)
    return (getresp_pb.Encode(), 0, "")

  def delete_request(self, app_id, http_request_data):
    global app_datastore
    logger.debug("DeleteRequest Received...")
    delreq_pb = datastore_pb.DeleteRequest( http_request_data )
    logger.debug("DELETE_REQUEST: %s" % delreq_pb)
    delresp_pb = api_base_pb.VoidProto() 
    app_datastore._Dynamic_Delete(app_id, delreq_pb, delresp_pb)
    return (delresp_pb.Encode(), 0, "")

  def void_proto(self, app_id, http_request_data):
    resp_pb = api_base_pb.VoidProto() 
    print "Got void"
    logger.debug("VOID_RESPONSE: %s to void" % resp_pb)
    return (resp_pb.Encode(), 0, "" )
  
  def str_proto(self, app_id, http_request_data):
    str_pb = api_base_pb.StringProto( http_request_data )
    composite_pb = datastore_pb.CompositeIndices()
    print "Got a string proto"
    print str_pb
    logger.debug("String proto received: %s"%str_pb)
    logger.debug("CompositeIndex response to string: %s" % composite_pb)
    return (composite_pb.Encode(), 0, "" )    
  
  def int64_proto(self, app_id, http_request_data):
    int64_pb = api_base_pb.Integer64Proto( http_request_data ) 
    resp_pb = api_base_pb.VoidProto()
    print "Got a int 64"
    print int64_pb
    logger.debug("Int64 proto received: %s"%int64_pb)
    logger.debug("VOID_RESPONSE to int64: %s" % resp_pb)
    return (resp_pb.Encode(), 0, "")
 
  def compositeindex_proto(self, app_id, http_request_data):
    compindex_pb = entity_pb.CompositeIndex( http_request_data)
    resp_pb = api_base_pb.VoidProto()
    print "Got Composite Index"
    #print compindex_pb
    logger.debug("CompositeIndex proto recieved: %s"%str(compindex_pb))
    logger.debug("VOID_RESPONSE to composite index: %s" % resp_pb)
    return (resp_pb.Encode(), 0, "")

  ##############
  # OTHER TYPE #
  ##############
  def unknown_request(self, app_id, http_request_data, pb_type):
    logger.debug("Received Unknown Protocol Buffer %s" % pb_type )
    print "ERROR: Received Unknown Protocol Buffer <" + pb_type +">.",
    print "Nothing has been implemented to handle this Protocol Buffer type."
    print "http request data:"
    print http_request_data 
    print "http done"
    self.void_proto(app_id, http_request_data)

  
  #########################
  # POST Request Handling #
  #########################
  @tornado.web.asynchronous
  def post( self ):
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data  = app_data.split(':')

    if len(app_data) == 4:
      app_id, user_email, nick_name, auth_domain = app_data
      os.environ['AUTH_DOMAIN'] = auth_domain
      os.environ['USER_EMAIL'] = user_email
      os.environ['USER_NICKNAME'] = nick_name
      os.environ['APPLICATION_ID'] = app_id 
    elif len(app_data) == 1:
      app_id = app_data[0]
      os.environ['APPLICATION_ID'] = app_id 
    else:
      logger.debug("UNABLE TO EXTRACT APPLICATION DATA")
      return

    # Default HTTP Response Data #

    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)
    self.finish()    

    
def usage():
  print "AppScale Server" 
  print
  print "Options:"
  print "\t--certificate=<path-to-ssl-certificate>"
  print "\t--a=<soap server hostname> "
  print "\t--key for using keys from the soap server"
  print "\t--type=<hypertable, hbase, cassandra, mysql, mongodb>"
  print "\t--secret=<secrete to soap server>"
  print "\t--blocksize=<key-block-size>"
  print "\t--no_encryption"
def main(argv):
  global app_datastore
  global logFilePtr
  global zoo_keeper
  cert_file = CERT_LOCATION
  key_file = KEY_LOCATION
  db_type = "hypertable"
  port = DEFAULT_SSL_PORT
  isEncrypted = True
  try:
    opts, args = getopt.getopt( argv, "c:t:l:s:b:a:k:p:n:z:", 
                               ["certificate=", 
                                "type=", 
                                "log=", 
                                "secret=", 
                                "blocksize=", 
                                "soap=", 
                                "key", 
                                "port", 
                                "no_encryption",
                                "zoo_keeper"] )
  except getopt.GetoptError:
    usage()
    sys.exit(1)
  for opt, arg in opts:
    if opt in ("-c", "--certificate"):
      cert_file = arg
      print "Using cert..."
    elif  opt in ("-t", "--type"):
      db_type = arg
      print "Datastore type: ",db_type 
    elif opt in ("-s", "--secret"):
      print "Secret set..."
    elif opt in ("-l", "--log"):
      pass
    elif opt in ("-b", "--blocksize"):
      pass
    elif opt in ("-a", "--soap"):
      pass
    elif opt in ("-p", "--port"):
      port = int(arg)
    elif opt in ("-n", "--no_encryption"):
      isEncrypted = False
    elif opt in ("-z", "--zoo_keeper"):
      zoo_keeper_locations = arg      

  app_datastore = DatastoreDistributed()

  zoo_keeper = zktransaction.ZKTransaction(zoo_keeper_locations)

  if port == DEFAULT_SSL_PORT and not isEncrypted:
    port = DEFAULT_PORT
  pb_application = tornado.web.Application([
    (r"/*", MainHandler),
  ])
  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(port) 
  if not db_type == "timesten":
    # Stop running as root, security purposes #
    drop_privileges()

  while 1:
    try:
      # Start Server #
      tornado.ioloop.IOLoop.instance().start()
    except SSL.SSLError:
      logger.debug("\n\nUnexcepted input for AppScale-Secure-Server")
    except KeyboardInterrupt:
      print "Server interrupted by user, terminating..."
      exit(1)

if __name__ == '__main__':
  #cProfile.run("main(sys.argv[1:])")
  main(sys.argv[1:])


