#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#





"""SQlite-based stub for the Python datastore API.

Entities are stored in an sqlite database in a similar fashion to the production
datastore.

Transactions are serialized through __tx_lock. Each transaction acquires it
when it begins and releases it when it commits or rolls back.
"""












import array
import itertools
import logging
import sys
import threading

from google.appengine.datastore import entity_pb
from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_stub_util
from google.appengine.datastore import sortable_pb_encoder
from google.appengine.runtime import apiproxy_errors

try:
  import pysqlite2.dbapi2 as sqlite3
except ImportError:
  import sqlite3


import __builtin__
buffer = __builtin__.buffer



entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Transaction.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Cursor.__hash__ = lambda self: hash(self.Encode())






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


    '!=': '!=',
}



_ORDER_MAP = {
    datastore_pb.Query_Order.ASCENDING: 'ASC',
    datastore_pb.Query_Order.DESCENDING: 'DESC',
}

_CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS Apps (
  app_id TEXT NOT NULL PRIMARY KEY,
  indexes BLOB);

CREATE TABLE IF NOT EXISTS Namespaces (
  app_id TEXT NOT NULL,
  name_space TEXT NOT NULL,
  PRIMARY KEY (app_id, name_space));

CREATE TABLE IF NOT EXISTS IdSeq (
  prefix TEXT NOT NULL PRIMARY KEY,
  next_id INT NOT NULL);
"""

_NAMESPACE_SCHEMA = """
CREATE TABLE "%(prefix)s!Entities" (
  __path__ BLOB NOT NULL PRIMARY KEY,
  kind TEXT NOT NULL,
  entity BLOB NOT NULL);
CREATE INDEX "%(prefix)s!EntitiesByKind" ON "%(prefix)s!Entities" (
  kind ASC,
  __path__ ASC);

CREATE TABLE "%(prefix)s!EntitiesByProperty" (
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  value BLOB NOT NULL,
  __path__ BLOB NOT NULL REFERENCES Entities,
  PRIMARY KEY(kind ASC, name ASC, value ASC, __path__ ASC) ON CONFLICT IGNORE);
CREATE INDEX "%(prefix)s!EntitiesByPropertyDesc"
  ON "%(prefix)s!EntitiesByProperty" (
  kind ASC,
  name ASC,
  value DESC,
  __path__ ASC);
CREATE INDEX "%(prefix)s!EntitiesByPropertyKey"
  ON "%(prefix)s!EntitiesByProperty" (
  __path__ ASC);

INSERT OR IGNORE INTO Apps (app_id) VALUES ('%(app_id)s');
INSERT INTO Namespaces (app_id, name_space)
  VALUES ('%(app_id)s', '%(name_space)s');
INSERT OR IGNORE INTO IdSeq VALUES ('%(prefix)s', 1);
"""


def ReferencePropertyToReference(refprop):
  ref = entity_pb.Reference()
  ref.set_app(refprop.app())
  if refprop.has_name_space():
    ref.set_name_space(refprop.name_space())
  for pathelem in refprop.pathelement_list():
    ref.mutable_path().add_element().CopyFrom(pathelem)
  return ref


class QueryCursor(datastore_stub_util.BaseCursor):
  """Encapsulates a database cursor and provides methods to fetch results."""

  def __init__(self, query, db_cursor):
    """Constructor.

    Args:
      query: A Query PB.
      db_cursor: An SQLite cursor returning n+2 columns. The first 2 columns
        must be the path of the entity and the entity itself, while the
        remaining columns must be the sort columns for the query.
    """
    super(QueryCursor, self).__init__(query.app())
    self.__query = query
    self.app = query.app()
    self.__cursor = db_cursor
    self.__seen = set()


    self.__position = ('', '')


    self.__next_result = (None, None)

    if (query.has_compiled_cursor() and
        query.compiled_cursor().position_size()):
      self.ResumeFromCompiledCursor(query.compiled_cursor())

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
    if self.__position[0]:
      position = cc.add_position()

      position.set_start_key(self.__position[0])

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
    if self.__query.has_end_compiled_cursor() and (
        not self.__query.end_compiled_cursor().position_list() or
        position > self.__query.end_compiled_cursor().position(0).start_key()):
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
      datastore_stub_util.PrepareSpecialPropertiesForLoad(entity)
      self.__next_result = None, None
      return entity
    return None

  def _HasNext(self):
    """Prefetches the next result and returns true if successful.

    Returns:
      A boolean that indicates if there are more results.
    """
    while self.__cursor and (
        not self.__next_result[0] or self.__next_result[0] in self.__seen):
      self.__next_result = self._GetResult()



    if self.limit is not None and len(self.__seen) >= self.limit:
      return False

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



    target_position = cc.position(0).start_key()
    if (self.__query.has_end_compiled_cursor() and target_position >=
        self.__query.end_compiled_cursor().position(0).start_key()):

      self.__position = (target_position, target_position)
      self.__cursor = None
      return


    while self.__position[1] <= target_position and self.__cursor:
      self.__next_result = self._GetResult()

  def PopulateQueryResult(self, result, count, offset):
    """Populates a QueryResult PB with results from the cursor.

    Args:
      result: out: A query_result PB.
      count: The number of results to retrieve.
      offset: The number of results to skip
    """
    limited_offset = min(offset, datastore_stub_util._MAX_QUERY_OFFSET)
    if limited_offset:
      result.set_skipped_results(self.Skip(limited_offset))

    if offset == limited_offset:
      if count > datastore_stub_util._MAXIMUM_RESULTS:
        count = datastore_stub_util._MAXIMUM_RESULTS

      result_list = result.result_list()
      while len(result_list) < count:
        entity = self._Next()
        if entity is None:
          break
        result_list.append(entity)

    result.set_keys_only(self.__query.keys_only())
    result.set_more_results(self._HasNext())
    self.PopulateCursor(result)
    self._EncodeCompiledCursor(result.mutable_compiled_cursor())


def MakeEntityForQuery(query, *path):
  """Make an entity to be returned by a pseudo-kind query.

  Args:
    query: the query which will return the entity.
    path: pairs of type/name-or-id values specifying the entity's key
  Returns:
    An entity_pb.EntityProto with app and namespace as in query and the key
    specified by path.
  """
  pseudo_pb = entity_pb.EntityProto()
  pseudo_pb.mutable_entity_group()
  pseudo_pk = pseudo_pb.mutable_key()
  pseudo_pk.set_app(query.app())
  if query.has_name_space():
    pseudo_pk.set_name_space(query.name_space())


  for i in xrange(0, len(path), 2):
    pseudo_pe = pseudo_pk.mutable_path().add_element()
    pseudo_pe.set_type(path[i])
    if isinstance(path[i + 1], basestring):
      pseudo_pe.set_name(path[i + 1])
    else:
      pseudo_pe.set_id(path[i + 1])

  return pseudo_pb


class KindPseudoKind(object):
  """Pseudo-kind for __kind__ queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__kind__'

  def __init__(self, sqlitestub):
    """Constructor.

    Initializes a __kind__ pseudo-kind definition.

    Args:
      sqlitestub: the DatastoreSqliteStub instance being served by this
          pseudo-kind.
    """
    self.sqlitestub = sqlitestub

  def Query(self, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      query: the original datastore_pb.Query
      filters: the filters from query
      orders: the orders from query

    Returns:
      A query cursor to iterate over the query results, or None if the query
      is invalid.
    """
    kind_range = datastore_stub_util.ParseKindQuery(query, filters, orders)
    conn = self.sqlitestub._GetConnection(None)
    cursor = None
    try:
      prefix = self.sqlitestub._GetTablePrefix(query)
      filters = []

      def AddExtremeFilter(extreme, inclusive, is_end):
        """Add filter for kind start/end."""
        if not is_end:
          if inclusive:
            op = datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL
          else:
            op = datastore_pb.Query_Filter.GREATER_THAN
        else:
          if inclusive:
            op = datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL
          else:
            op = datastore_pb.Query_Filter.LESS_THAN
        filters.append(('kind', op, extreme))
      kind_range.MapExtremes(AddExtremeFilter)

      params = []
      sql_filters = self.sqlitestub._CreateFilterString(filters, params)

      sql_stmt = ('SELECT kind FROM "%s!Entities" %s GROUP BY kind'
                  % (prefix, sql_filters))
      c = conn.execute(sql_stmt, params)

      kinds = []
      for row in c.fetchall():
        kind = row[0].encode('utf-8')
        kinds.append(MakeEntityForQuery(query, self.name, kind))

      cursor = datastore_stub_util.ListCursor(
          query, kinds, datastore_stub_util.CompareEntityPbByKey)
    finally:
      self.sqlitestub._ReleaseConnection(conn, None)

    return cursor


class PropertyPseudoKind(object):
  """Pseudo-kind for __property__ queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__property__'

  def __init__(self, sqlitestub):
    """Constructor.

    Initializes a __property__ pseudo-kind definition.

    Args:
      sqlitestub: the DatastoreSqliteStub instance being served by this
          pseudo-kind.
    """
    self.sqlitestub = sqlitestub

  def Query(self, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      query: the original datastore_pb.Query
      filters: the filters from query
      orders: the orders from query

    Returns:
      A query cursor to iterate over the query results, or None if the query
      is invalid.
    """
    property_range = datastore_stub_util.ParsePropertyQuery(query, filters,
                                                            orders)
    keys_only = query.keys_only()
    conn = self.sqlitestub._GetConnection(None)
    cursor = None
    try:
      prefix = self.sqlitestub._GetTablePrefix(query)
      filters = []






      def AddExtremeFilter(extreme, inclusive, is_end):
        """Add filter for kind start/end."""
        if not is_end:
          op = datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL
        else:
          op = datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL
        filters.append(('kind', op, extreme[0]))
      property_range.MapExtremes(AddExtremeFilter)


      for name in datastore_stub_util.GetInvisibleSpecialPropertyNames():
        filters.append(('name', '!=', name))

      params = []
      sql_filters = self.sqlitestub._CreateFilterString(filters, params)
      if not keys_only:




        sql_stmt = ('SELECT kind, name, value FROM "%s!EntitiesByProperty" %s '
                    'GROUP BY kind, name, substr(value, 1, 1) '
                    'ORDER BY kind, name'
                    % (prefix, sql_filters))
      else:

        sql_stmt = ('SELECT kind, name FROM "%s!EntitiesByProperty" %s '
                    'GROUP BY kind, name ORDER BY kind, name'
                    % (prefix, sql_filters))
      c = conn.execute(sql_stmt, params)

      properties = []
      kind = None
      name = None
      property_pb = None
      for row in c.fetchall():
        if not (row[0] == kind and row[1] == name):
          new_kind = row[0].encode('utf-8')
          new_name = row[1].encode('utf-8')

          if not property_range.Contains((new_kind, new_name)):
            continue
          kind = new_kind
          name = new_name

          if property_pb:
            properties.append(property_pb)
          property_pb = MakeEntityForQuery(query, KindPseudoKind.name, kind,
                                           self.name, name)

        if not keys_only:

          value_data = row[2]
          value_decoder = sortable_pb_encoder.Decoder(
              array.array('B', str(value_data)))
          raw_value_pb = entity_pb.PropertyValue()
          raw_value_pb.Merge(value_decoder)
          if raw_value_pb.has_int64value():
            tag = entity_pb.PropertyValue.kint64Value
          elif raw_value_pb.has_booleanvalue():
            tag = entity_pb.PropertyValue.kbooleanValue
          elif raw_value_pb.has_stringvalue():
            tag = entity_pb.PropertyValue.kstringValue
          elif raw_value_pb.has_doublevalue():
            tag = entity_pb.PropertyValue.kdoubleValue
          elif raw_value_pb.has_pointvalue():
            tag = entity_pb.PropertyValue.kPointValueGroup
          elif raw_value_pb.has_uservalue():
            tag = entity_pb.PropertyValue.kUserValueGroup
          elif raw_value_pb.has_referencevalue():
            tag = entity_pb.PropertyValue. kReferenceValueGroup
          else:
            tag = 0
          tag_name = datastore_stub_util._PROPERTY_TYPE_NAMES[tag]


          representation_pb = property_pb.add_property()
          representation_pb.set_name(u'property_representation')
          representation_pb.set_multiple(True)
          representation_pb.mutable_value().set_stringvalue(tag_name)

      if property_pb:
        properties.append(property_pb)

      cursor = datastore_stub_util.ListCursor(
          query, properties, datastore_stub_util.CompareEntityPbByKey)
    finally:
      self.sqlitestub._ReleaseConnection(conn, None)

    return cursor


class NamespacePseudoKind(object):
  """Pseudo-kind for __namespace__ queries.

  Provides a Query method to perform the actual query.

  Public properties:
    name: the pseudo-kind name
  """
  name = '__namespace__'

  def __init__(self, sqlitestub):
    """Constructor.

    Initializes a __namespace__ pseudo-kind definition.

    Args:
      sqlitestub: the DatastoreSqliteStub instance being served by this
          pseudo-kind.
    """
    self.sqlitestub = sqlitestub

  def Query(self, query, filters, orders):
    """Perform a query on this pseudo-kind.

    Args:
      query: the original datastore_pb.Query
      filters: the filters from query
      orders: the orders from query

    Returns:
      A query cursor to iterate over the query results, or None if the query
      is invalid.
    """
    namespace_range = datastore_stub_util.ParseNamespaceQuery(query, filters,
                                                              orders)
    app_str = query.app()

    namespace_entities = []



    namespaces = self.sqlitestub._DatastoreSqliteStub__namespaces
    for app_id, namespace in sorted(namespaces):
      if app_id == app_str and namespace_range.Contains(namespace):
        if namespace:
          ns_id = namespace
        else:
          ns_id = datastore_types._EMPTY_NAMESPACE_ID
        namespace_entities.append(MakeEntityForQuery(query, self.name, ns_id))

    return datastore_stub_util.ListCursor(
        query, namespace_entities, datastore_stub_util.CompareEntityPbByKey)


class DatastoreSqliteStub(apiproxy_stub.APIProxyStub):
  """Persistent stub for the Python datastore API.

  Stores all entities in an SQLite database. A DatastoreSqliteStub instance
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

  READ_ERROR_MSG = ('Data in %s is corrupt or a different version. '
                    'Try running with the --clear_datastore flag.\n%r')

  def __init__(self,
               app_id,
               datastore_file,
               require_indexes=False,
               verbose=False,
               service_name='datastore_v3',
               trusted=False):
    """Constructor.

    Initializes the SQLite database if necessary.

    Args:
      app_id: string
      datastore_file: string, path to sqlite database. Use None to create an
          in-memory database.
      require_indexes: bool, default False. If True, composite indexes must
          exist in index.yaml for queries that need them.
      verbose: bool, default False. If True, logs all select statements.
      service_name: Service name expected for all calls.
      trusted: bool, default False. If True, this stub allows an app to access
          the data of another app.
    """
    apiproxy_stub.APIProxyStub.__init__(self, service_name)

    assert isinstance(app_id, basestring) and app_id
    self.__app_id = app_id
    self.__datastore_file = datastore_file
    self.SetTrusted(trusted)



    self.__tx_actions = []

    self.__require_indexes = require_indexes
    self.__verbose = verbose


    self.__id_map = {}
    self.__id_lock = threading.Lock()

    self.__connection = sqlite3.connect(
        self.__datastore_file or ':memory:',
        timeout=_MAX_TIMEOUT,
        check_same_thread=False)

    self.__connection_lock = threading.RLock()

    self.__current_transaction = None
    self.__next_tx_handle = 1


    self.__tx_writes = {}

    self.__tx_deletes = set()

    self.__cursors = {}


    self.__namespaces = set()


    self.__indexes = {}
    self.__index_lock = threading.Lock()


    self.__query_history = {}


    self.__pseudo_kinds = {}
    self._RegisterPseudoKind(KindPseudoKind(self))
    self._RegisterPseudoKind(PropertyPseudoKind(self))
    self._RegisterPseudoKind(NamespacePseudoKind(self))

    try:
      self.__Init()
    except sqlite3.DatabaseError, e:
      raise datastore_errors.InternalError(self.READ_ERROR_MSG %
                                           (self.__datastore_file, e))

  def __Init(self):

    self.__connection.executescript(_CORE_SCHEMA)
    self.__connection.commit()


    c = self.__connection.execute('SELECT app_id, name_space FROM Namespaces')
    self.__namespaces = set(c.fetchall())


    c = self.__connection.execute('SELECT app_id, indexes FROM Apps')
    for app_id, index_proto in c.fetchall():
      index_map = self.__indexes.setdefault(app_id, {})
      if not index_proto:
        continue
      indexes = datastore_pb.CompositeIndices(index_proto)
      for index in indexes.index_list():
        index_map.setdefault(index.definition().entity_type(), []).append(index)

  def _RegisterPseudoKind(self, kind):
    self.__pseudo_kinds[kind.name] = kind

  def Clear(self):
    """Clears the datastore."""
    conn = self._GetConnection(None)
    try:
      c = conn.execute(
          "SELECT tbl_name FROM sqlite_master WHERE type = 'table'")
      for row in c.fetchall():
        conn.execute('DROP TABLE "%s"' % row)
      conn.commit()
    finally:
      self._ReleaseConnection(conn, None)

    self.__namespaces = set()
    self.__indexes = {}
    self.__cursors = {}
    self.__query_history = {}

    self.__Init()

  def Read(self):
    """Reads the datastore from disk.

    Noop for compatibility with file stub.
    """
    pass

  def Write(self):
    """Writes the datastore to disk.

    Noop for compatibility with file stub.
    """
    pass

  def SetTrusted(self, trusted):
    """Set/clear the trusted bit in the stub.

    This bit indicates that the app calling the stub is trusted. A
    trusted app can write to datastores of other apps.

    Args:
      trusted: boolean.
    """
    self.__trusted = trusted

  @staticmethod
  def __MakeParamList(size):
    """Returns a comma separated list of sqlite substitution parameters.

    Args:
      size: Number of parameters in returned list.
    Returns:
      A comma separated list of substitution parameters.
    """
    return ','.join('?' * size)

  @staticmethod
  def __GetEntityKind(key):
    if isinstance(key, entity_pb.EntityProto):
      key = key.key()
    return key.path().element_list()[-1].type()

  @staticmethod
  def __EncodeIndexPB(pb):
    if isinstance(pb, entity_pb.PropertyValue) and pb.has_uservalue():

      userval = entity_pb.PropertyValue()
      userval.mutable_uservalue().set_email(pb.uservalue().email())
      userval.mutable_uservalue().set_auth_domain(pb.uservalue().auth_domain())
      userval.mutable_uservalue().set_gaiaid(0)
      pb = userval
    encoder = sortable_pb_encoder.Encoder()
    pb.Output(encoder)
    return buffer(encoder.buffer().tostring())

  @staticmethod
  def __AddQueryParam(params, param):
    params.append(param)
    return len(params)

  @staticmethod
  def _CreateFilterString(filter_list, params):
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

      value_index = DatastoreSqliteStub.__AddQueryParam(params, value)
      clauses.append('%s %s :%d' % (prop, sql_op, value_index))

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
    if not self.__trusted and app_id != self.__app_id:
      raise datastore_errors.BadRequestError(
          'app %s cannot access app %s\'s data' % (self.__app_id, app_id))

  def __ValidateTransaction(self, tx):
    """Verify that this transaction exists and is valid.

    Args:
      tx: datastore_pb.Transaction

    Raises:
      datastore_errors.BadRequestError: if the tx is valid or doesn't exist.
    """
    assert isinstance(tx, datastore_pb.Transaction)
    self.__ValidateAppId(tx.app())
    if tx.handle() != self.__current_transaction:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Transaction %s not found' % tx)

  def __ValidateKey(self, key):
    """Validate this key.

    Args:
      key: entity_pb.Reference

    Raises:
      datastore_errors.BadRequestError: if the key is invalid
    """

    assert isinstance(key, entity_pb.Reference)

    self.__ValidateAppId(key.app())

    for elem in key.path().element_list():
      if elem.has_id() == elem.has_name():
        raise datastore_errors.BadRequestError(
            'each key path element should have id or name but not both: %r'
            % key)

  def _GetConnection(self, transaction):
    """Retrieves a connection to the SQLite DB.

    If a transaction is supplied, the transaction's connection is returned;
    otherwise a fresh connection is returned.

    Args:
      transaction: A Transaction PB.
    Returns:
      An SQLite connection object.
    """
    self.__connection_lock.acquire()
    request_tx = transaction and transaction.handle()
    if request_tx == 0:
      request_tx = None
    if request_tx != self.__current_transaction:


      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Only one concurrent transaction per thread is permitted.')
    return self.__connection

  def _ReleaseConnection(self, conn, transaction, rollback=False):
    """Releases a connection for use by other operations.

    If a transaction is supplied, no action is taken.

    Args:
      conn: An SQLite connection object.
      transaction: A Transaction PB.
      rollback: If True, roll back the database TX instead of committing it.
    """
    if not transaction or not transaction.has_handle():
      if rollback:
        conn.rollback()
      else:
        conn.commit()
    self.__connection_lock.release()

  def __ConfigureNamespace(self, conn, prefix, app_id, name_space):
    """Ensures the relevant tables and indexes exist.

    Args:
      conn: An SQLite database connection.
      prefix: The namespace prefix to configure.
      app_id: The app ID.
      name_space: The per-app namespace name.
    """
    format_args = {'app_id': app_id, 'name_space': name_space, 'prefix': prefix}
    conn.executescript(_NAMESPACE_SCHEMA % format_args)
    conn.commit()

  def __WriteIndexData(self, conn, app):
    """Writes index data to disk.

    Args:
      conn: An SQLite connection.
      app: The app ID to write indexes for.
    """
    indices = datastore_pb.CompositeIndices()
    for indexes in self.__indexes[app].values():
      indices.index_list().extend(indexes)

    conn.execute('UPDATE Apps SET indexes = ? WHERE app_id = ?',
                 (app, indices.Encode()))

  def _GetTablePrefix(self, data):
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
    prefix = ('%s!%s' % data).replace('"', '""')
    if data not in self.__namespaces:
      self.__namespaces.add(data)
      self.__ConfigureNamespace(self.__connection, prefix, *data)
    return prefix

  def __DeleteRows(self, conn, paths, table):
    """Deletes rows from a table.

    Args:
      conn: An SQLite connection.
      paths: Paths to delete.
      table: The table to delete from.
    Returns:
      The number of rows deleted.
    """
    c = conn.execute('DELETE FROM "%s" WHERE __path__ IN (%s)'
                     % (table, self.__MakeParamList(len(paths))),
                     paths)
    return c.rowcount

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
      prefix = self._GetTablePrefix((app_id, ns))
      return self.__DeleteRows(conn, path_strings, '%s!%s' % (prefix, table))

  def __DeleteIndexEntries(self, conn, keys):
    """Deletes entities from the index.

    Args:
      conn: An SQLite connection.
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

    entities = sorted((self._GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      conn.executemany(
          'INSERT OR REPLACE INTO "%s!Entities" VALUES (?, ?, ?)' % prefix,
          RowGenerator(group))

  def __InsertIndexEntries(self, conn, entities):
    """Inserts index entries for the supplied entities.

    Args:
      conn: A database connection.
      entities: A list of entities to create index entries for.
    """

    def RowGenerator(entities):
      for unused_prefix, e in entities:
        for p in e.property_list():
          yield (self.__GetEntityKind(e),
                 p.name(),
                 self.__EncodeIndexPB(p.value()),
                 self.__EncodeIndexPB(e.key().path()))
    entities = sorted((self._GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      conn.executemany(
          'INSERT INTO "%s!EntitiesByProperty" VALUES (?, ?, ?, ?)' % prefix,
          RowGenerator(group))

  def __AllocateIds(self, conn, prefix, size=None, max=None):
    """Allocates IDs.

    Args:
      conn: An Sqlite connection object.
      prefix: A table namespace prefix.
      size: Number of IDs to allocate.
      max: Upper bound of IDs to allocate

    Returns:
      int: The beginning of a range of size IDs
    """
    self.__id_lock.acquire()
    ret = None
    if size is not None:
      assert size > 0
      next_id, block_size = self.__id_map.get(prefix, (0, 0))
      if not block_size:


        block_size = (size / 1000 + 1) * 1000
        c = conn.execute('SELECT next_id FROM IdSeq WHERE prefix = ? LIMIT 1',
                         (prefix,))
        next_id = c.fetchone()[0]
        c = conn.execute(
            'UPDATE IdSeq SET next_id = next_id + ? WHERE prefix = ?',
            (block_size, prefix))
        assert c.rowcount == 1

      if size > block_size:

        c = conn.execute('SELECT next_id FROM IdSeq WHERE prefix = ? LIMIT 1',
                         (prefix,))
        ret = c.fetchone()[0]
        c = conn.execute(
            'UPDATE IdSeq SET next_id = next_id + ? WHERE prefix = ?',
            (size, prefix))
        assert c.rowcount == 1
      else:

        ret = next_id;
        next_id += size
        block_size -= size
        self.__id_map[prefix] = (next_id, block_size)
    else:
      c = conn.execute('SELECT next_id FROM IdSeq WHERE prefix = ? LIMIT 1',
                       (prefix,))
      ret = c.fetchone()[0]
      if max and max >= ret:
        c = conn.execute(
            'UPDATE IdSeq SET next_id = ? WHERE prefix = ?',
            (max + 1, prefix))
        assert c.rowcount == 1
    self.__id_lock.release()
    return ret

  def MakeSyncCall(self, service, call, request, response):
    """The main RPC entry point. service must be 'datastore_v3'."""
    self.AssertPbIsInitialized(request)
    try:
      apiproxy_stub.APIProxyStub.MakeSyncCall(self, service, call, request,
                                              response)
    except sqlite3.OperationalError, e:
      if e.args[0] == 'database is locked':
        raise datastore_errors.Timeout('Database is locked.')
      else:
        raise
    self.AssertPbIsInitialized(response)

  def AssertPbIsInitialized(self, pb):
    """Raises an exception if the given PB is not initialized and valid."""
    explanation = []
    assert pb.IsInitialized(explanation), explanation

    pb.Encode()

  def QueryHistory(self):
    """Returns a dict that maps Query PBs to times they've been run."""
    return dict((pb, times) for pb, times in self.__query_history.items() if
                pb.app() == self.__app_id)

  def __PutEntities(self, conn, entities):
    self.__DeleteIndexEntries(conn, [e.key() for e in entities])
    for entity in entities:
      datastore_stub_util.PrepareSpecialPropertiesForStore(entity)
    self.__InsertEntities(conn, entities)
    self.__InsertIndexEntries(conn, entities)

  def __DeleteEntities(self, conn, keys):
    self.__DeleteIndexEntries(conn, keys)
    self.__DeleteEntityRows(conn, keys, 'Entities')

  def _Dynamic_Put(self, put_request, put_response):
    conn = self._GetConnection(put_request.transaction())
    try:
      entities = put_request.entity_list()
      for entity in entities:
        self.__ValidateKey(entity.key())


        for prop in itertools.chain(entity.property_list(),
                                    entity.raw_property_list()):
          datastore_stub_util.FillUser(prop)

        assert entity.has_key()
        assert entity.key().path().element_size() > 0

        last_path = entity.key().path().element_list()[-1]
        if last_path.id() == 0 and not last_path.has_name():

          id_ = self.__AllocateIds(conn, self._GetTablePrefix(entity.key()), 1)
          last_path.set_id(id_)


          assert entity.entity_group().element_size() == 0
          group = entity.mutable_entity_group()
          root = entity.key().path().element(0)
          group.add_element().CopyFrom(root)

        else:
          assert (entity.has_entity_group() and
                  entity.entity_group().element_size() > 0)

        if put_request.transaction().handle():
          self.__tx_writes[entity.key()] = entity

          self.__tx_deletes.discard(entity.key())

      if not put_request.transaction().handle():
        self.__PutEntities(conn, entities)
      put_response.key_list().extend([e.key() for e in entities])
    finally:
      self._ReleaseConnection(conn, put_request.transaction())

  def _Dynamic_Get(self, get_request, get_response):
    conn = self._GetConnection(get_request.transaction())
    try:
      for key in get_request.key_list():
        self.__ValidateAppId(key.app())
        prefix = self._GetTablePrefix(key)
        c = conn.execute(
            'SELECT entity FROM "%s!Entities" WHERE __path__ = ?' % (prefix,),
            (self.__EncodeIndexPB(key.path()),))
        group = get_response.add_entity()
        row = c.fetchone()
        if row:
          group.mutable_entity().ParseFromString(row[0])
          datastore_stub_util.PrepareSpecialPropertiesForLoad(
              group.mutable_entity())
    finally:
      self._ReleaseConnection(conn, get_request.transaction())

  def _Dynamic_Delete(self, delete_request, delete_response):
    conn = self._GetConnection(delete_request.transaction())
    try:
      for key in delete_request.key_list():
        self.__ValidateAppId(key.app())
        if delete_request.transaction().handle():
          self.__tx_deletes.add(key)
          self.__tx_writes.pop(key, None)

      if not delete_request.transaction().handle():
        self.__DeleteEntities(conn, delete_request.key_list())
    finally:
      self._ReleaseConnection(conn, delete_request.transaction())

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
             'FROM "%s!Entities" AS Entities %s %s' % (
                 ','.join(x[0] for x in orders),
                 self._GetTablePrefix(query),
                 self._CreateFilterString(filters, params),
                 self.__CreateOrderString(orders)))
    return query, params

  def __SinglePropertyQuery(self, query, filter_info, order_info):
    """Performs queries satisfiable by the EntitiesByProperty table."""

    property_names = set(filter_info.keys())
    property_names.update(x[0] for x in order_info)
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

    prefix = self._GetTablePrefix(query)
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
        self._CreateFilterString(filters, params),
        self.__CreateOrderString(orders))
    query = ('SELECT Entities.__path__, Entities.entity, %s '
             'FROM "%s!EntitiesByProperty" AS EntitiesByProperty INNER JOIN '
             '"%s!Entities" AS Entities USING (__path__) %s %s' % format_args)
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

    prefix = self._GetTablePrefix(query)

    joins = []
    filters = []
    join_name_map = {}
    for name, filter_ops in filter_sets:
      if name == '__key__':
        for op, value in filter_ops:
          filters.append(('Entities.__path__', op, buffer(value)))
      else:
        join_name = 'ebp_%d' % (len(joins),)
        join_name_map.setdefault(name, join_name)
        joins.append(
            'INNER JOIN "%s!EntitiesByProperty" AS %s '
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
                          datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
                          amin))
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
        self._CreateFilterString(filters, params),
        self.__CreateOrderString(orders))
    query = ('SELECT Entities.__path__, Entities.entity, %s '
             'FROM "%s!Entities" AS Entities %s %s %s' % format_args)
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
    if self.__require_indexes:
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
    """Returns a query cursor for the provided query.

    Args:
      conn: The SQLite connection.
      query: A datastore_pb.Query protocol buffer.
    Returns:
      A QueryCursor object.
    """
    app_id = query.app()
    self.__ValidateAppId(app_id)

    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list())
    datastore_stub_util.ValidateQuery(query, filters, orders,
        _MAX_QUERY_COMPONENTS)
    datastore_stub_util.FillUsersInQuery(filters)

    if query.has_kind() and query.kind() in self.__pseudo_kinds:
      cursor = self.__pseudo_kinds[query.kind()].Query(query, filters, orders)
      if not cursor:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST,
            'Could not create query for pseudo-kind')
    else:
      filter_info = self.__GenerateFilterInfo(filters, query)
      order_info = self.__GenerateOrderInfo(orders)

      for strategy in DatastoreSqliteStub._QUERY_STRATEGIES:
        result = strategy(self, query, filter_info, order_info)
        if result:
          break
      else:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST,
            'No strategy found to satisfy query.')

      sql_stmt, params = result

      if self.__verbose:
        logging.info("Executing statement '%s' with arguments %r",
                     sql_stmt, [str(x) for x in params])
      db_cursor = conn.execute(sql_stmt, params)
      cursor = QueryCursor(query, db_cursor)


    clone = datastore_pb.Query()
    clone.CopyFrom(query)
    clone.clear_hint()
    clone.clear_limit()
    clone.clear_count()
    clone.clear_offset()
    self.__query_history[clone] = self.__query_history.get(clone, 0) + 1

    return cursor

  def _Dynamic_RunQuery(self, query, query_result):
    conn = self._GetConnection(query.transaction())
    try:
      cursor = self.__GetQueryCursor(conn, query)

      if query.has_count():
        count = query.count()
      elif query.has_limit():
        count = query.limit()
      else:
        count = _BATCH_SIZE

      cursor.PopulateQueryResult(query_result, count, query.offset())
      if query_result.has_cursor():
        self.__cursors[query_result.cursor().cursor()] = cursor
    finally:
      self._ReleaseConnection(conn, query.transaction())

  def _Dynamic_Next(self, next_request, query_result):
    self.__ValidateAppId(next_request.cursor().app())

    try:
      cursor = self.__cursors[next_request.cursor().cursor()]
    except KeyError:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Cursor %d not found' % next_request.cursor().cursor())

    assert cursor.app == next_request.cursor().app()

    count = _BATCH_SIZE
    if next_request.has_count():
      count = next_request.count()
    cursor.PopulateQueryResult(query_result, count, next_request.offset())
    if not query_result.has_cursor():
      del self.__cursors[next_request.cursor().cursor()]

  def _Dynamic_Count(self, query, integer64proto):
    if query.has_limit():
      query.set_limit(min(query.limit(), datastore_stub_util._MAXIMUM_RESULTS))
    else:
      query.set_limit(datastore_stub_util._MAXIMUM_RESULTS)

    conn = self._GetConnection(query.transaction())
    try:
      cursor = self.__GetQueryCursor(conn, query)
      integer64proto.set_value(cursor.Count())
    finally:
      self._ReleaseConnection(conn, query.transaction())

  def _Dynamic_BeginTransaction(self, request, transaction):
    self.__ValidateAppId(request.app())

    self.__connection_lock.acquire()
    assert self.__current_transaction is None
    handle = self.__next_tx_handle
    self.__next_tx_handle += 1

    transaction.set_app(request.app())
    transaction.set_handle(handle)
    self.__current_transaction = handle

  def _Dynamic_AddActions(self, request, _):



    if ((len(self.__tx_actions) + request.add_request_size()) >
        _MAX_ACTIONS_PER_TXN):
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Too many messages, maximum allowed %s' % _MAX_ACTIONS_PER_TXN)

    new_actions = []
    for add_request in request.add_request_list():



      self.__ValidateTransaction(add_request.transaction())
      clone = taskqueue_service_pb.TaskQueueAddRequest()
      clone.CopyFrom(add_request)
      clone.clear_transaction()
      new_actions.append(clone)

    self.__tx_actions.extend(new_actions)

  def _Dynamic_Commit(self, transaction, _):
    assert self.__current_transaction == transaction.handle()
    conn = self.__connection

    try:
      self.__PutEntities(conn, self.__tx_writes.values())
      self.__DeleteEntities(conn, self.__tx_deletes)

      for action in self.__tx_actions:
        try:
          apiproxy_stub_map.MakeSyncCall(
              'taskqueue', 'Add', action, api_base_pb.VoidProto())
        except apiproxy_errors.ApplicationError, e:
          logging.warning('Transactional task %s has been dropped, %s',
                          action, e)
    finally:
      self.__current_transaction = None
      self.__tx_actions = []
      self.__tx_writes = {}
      self.__tx_deletes = set()
      self._ReleaseConnection(conn, None)

  def _Dynamic_Rollback(self, transaction, _):
    conn = self._GetConnection(transaction)
    self.__current_transaction = None
    self.__tx_actions = []
    self.__tx_writes = {}
    self.__tx_deletes = set()
    self._ReleaseConnection(conn, None, True)

  def _Dynamic_GetSchema(self, req, schema):
    conn = self._GetConnection(None)
    try:
      prefix = self._GetTablePrefix(req)

      filters = []
      if req.has_start_kind():
        filters.append(('kind', datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
                        req.start_kind()))
      if req.has_end_kind():
        filters.append(('kind', datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL,
                        req.end_kind()))

      params = []
      if req.properties():




        sql_stmt = ('SELECT kind, name, value FROM "%s!EntitiesByProperty" %s '
                    'GROUP BY kind, name, substr(value, 1, 1) ORDER BY kind'
                    % (prefix, self._CreateFilterString(filters, params)))
      else:

        sql_stmt = ('SELECT kind FROM "%s!Entities" %s GROUP BY kind'
                    % (prefix, self._CreateFilterString(filters, params)))
      c = conn.execute(sql_stmt, params)

      kind = None
      current_name = None
      kind_pb = None
      for row in c.fetchall():
        if row[0] != kind:
          if kind_pb:
            schema.kind_list().append(kind_pb)
          kind = row[0].encode('utf-8')
          kind_pb = entity_pb.EntityProto()
          kind_pb.mutable_key().set_app('')
          kind_pb.mutable_key().mutable_path().add_element().set_type(kind)
          kind_pb.mutable_entity_group()

        if req.properties():
          name, value_data = row[1:]
          if current_name != name:
            current_name = name
            prop_pb = kind_pb.add_property()
            prop_pb.set_name(name.encode('utf-8'))
            prop_pb.set_multiple(False)

          value_decoder = sortable_pb_encoder.Decoder(
              array.array('B', str(value_data)))
          value_pb = prop_pb.mutable_value()
          value_pb.Merge(value_decoder)



          if value_pb.has_int64value():
            value_pb.set_int64value(0)
          if value_pb.has_booleanvalue():
            value_pb.set_booleanvalue(False)
          if value_pb.has_stringvalue():
            value_pb.set_stringvalue('none')
          if value_pb.has_doublevalue():
            value_pb.set_doublevalue(0.0)
          if value_pb.has_pointvalue():
            value_pb.mutable_pointvalue().set_x(0.0)
            value_pb.mutable_pointvalue().set_y(0.0)
          if value_pb.has_uservalue():
            value_pb.mutable_uservalue().set_gaiaid(0)
            value_pb.mutable_uservalue().set_email('none')
            value_pb.mutable_uservalue().set_auth_domain('none')
            value_pb.mutable_uservalue().clear_nickname()
            value_pb.mutable_uservalue().clear_obfuscated_gaiaid()
          if value_pb.has_referencevalue():
            value_pb.clear_referencevalue()
            value_pb.mutable_referencevalue().set_app('none')
            pathelem = value_pb.mutable_referencevalue().add_pathelement()
            pathelem.set_type('none')
            pathelem.set_name('none')

      if kind_pb:
        schema.kind_list().append(kind_pb)
    finally:
      self._ReleaseConnection(conn, None)

  def _Dynamic_AllocateIds(self, allocate_ids_request, allocate_ids_response):
    conn = self._GetConnection(None)
    model_key = allocate_ids_request.model_key()
    self.__ValidateAppId(model_key.app())
    if allocate_ids_request.has_size() and allocate_ids_request.has_max():
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'Both size and max cannot be set.')

    if allocate_ids_request.has_size():
      if allocate_ids_request.size() < 1:
        raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                               'Size must be greater than 0.')
      first_id = self.__AllocateIds(conn, self._GetTablePrefix(model_key),
                                    size=allocate_ids_request.size())
      allocate_ids_response.set_start(first_id)
      allocate_ids_response.set_end(first_id + allocate_ids_request.size() - 1)
    else:
      if allocate_ids_request.max() < 0:
        raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST,
            'Max must be greater than or equal to 0.')
      first_id = self.__AllocateIds(conn, self._GetTablePrefix(model_key),
                                    max=allocate_ids_request.max())
      allocate_ids_response.set_start(first_id)
      allocate_ids_response.set_end(max(allocate_ids_request.max(),
                                        first_id - 1))

    self._ReleaseConnection(conn, None)

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
    try:
      if self.__FindIndex(index):
        raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                               'Index already exists.')


      next_id = max([idx.id() for x in self.__indexes.get(app_id, {}).values()
                     for idx in x] + [0]) + 1
      index.set_id(next_id)
      id_response.set_value(next_id)


      clone = entity_pb.CompositeIndex()
      clone.CopyFrom(index)
      self.__indexes.setdefault(app_id, {}).setdefault(kind, []).append(clone)

      conn = self._GetConnection(None)
      try:
        self.__WriteIndexData(conn, app_id)
      finally:
        self._ReleaseConnection(conn, None)
    finally:
      self.__index_lock.release()

  def _Dynamic_GetIndices(self, app_str, composite_indices):
    self.__ValidateAppId(app_str.value())

    index_list = composite_indices.index_list()
    for indexes in self.__indexes.get(app_str.value(), {}).values():
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

    conn = self._GetConnection(None)
    try:
      self.__WriteIndexData(conn, app_id)
    finally:
      self._ReleaseConnection(conn, None)
    self.__index_lock.acquire()
    try:
      self.__indexes[app_id][kind].remove(my_index)
    finally:
      self.__index_lock.release()
