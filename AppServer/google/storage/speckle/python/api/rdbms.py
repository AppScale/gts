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




"""Python DB-API (PEP 249) interface to SQL Service.

http://www.python.org/dev/peps/pep-0249/
"""


import collections
import datetime
import exceptions
import os
import time
import types

from google.storage.speckle.proto import client_error_code_pb2
from google.storage.speckle.proto import client_pb2
from google.storage.speckle.proto import jdbc_type
from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python import api
from google.storage.speckle.python.api import converters




__path__ = api.__path__





OAUTH_CREDENTIALS_PATH = os.path.expanduser('~/.googlesql_oauth2.dat')






apilevel = '2.0'

threadsafety = 1



paramstyle = 'format'



version_info = (1, 2, 2, 'final', 0)







class Warning(StandardError, exceptions.Warning):
  pass

class Error(StandardError):
  pass

class InterfaceError(Error):
  pass

class DatabaseError(Error):
  pass

class DataError(DatabaseError):
  pass

class OperationalError(DatabaseError):
  pass

class IntegrityError(DatabaseError):
  pass

class InternalError(DatabaseError):
  pass

class ProgrammingError(DatabaseError):
  pass

class NotSupportedError(DatabaseError):
  pass

Blob = converters.Blob



def Date(year, month, day):
  return datetime.date(year, month, day)

def Time(hour, minute, second):
  return datetime.time(hour, minute, second)

def Timestamp(year, month, day, hour, minute, second):
  return datetime.datetime(year, month, day, hour, minute, second)

def DateFromTicks(ticks):
  return Date(*time.localtime(ticks)[:3])

def TimeFromTicks(ticks):
  return Time(*time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks):
  return Timestamp(*time.localtime(ticks)[:6])

def Binary(string):
  return Blob(string)


STRING = unicode
BINARY = Blob
NUMBER = float
DATETIME = datetime.datetime
ROWID = int


_PYTHON_TYPE_TO_JDBC_TYPE = {
    types.IntType: jdbc_type.INTEGER,
    types.LongType: jdbc_type.INTEGER,
    types.FloatType: jdbc_type.DOUBLE,
    types.BooleanType: jdbc_type.BOOLEAN,
    types.StringType: jdbc_type.VARCHAR,
    types.UnicodeType: jdbc_type.VARCHAR,
    datetime.date: jdbc_type.DATE,
    datetime.datetime: jdbc_type.TIMESTAMP,
    datetime.time: jdbc_type.TIME,
    converters.Blob: jdbc_type.BLOB,
    }


def _ConvertFormatToQmark(statement, args):
  """Replaces '%s' with '?'.

  The server actually supports '?' for bind parameters, but the
  MySQLdb implementation of PEP 249 uses '%s'.  Most clients don't
  bother checking the paramstyle member and just hardcode '%s' in
  their statements.  This function converts a format-style statement
  into a qmark-style statement.

  Args:
    statement: A string, a SQL statement.
    args: A sequence of arguments matching the statement's bind variables,
        if any.

  Returns:
    The converted string.
  """
  if args:
    qmarks = tuple('?' * len(args))
    return statement % qmarks
  return statement


class Cursor(object):

  def __init__(self, conn, use_dict_cursor=False):
    """Initializer.

    Args:
      conn: A Connection object.
      use_dict_cursor: Optional boolean to convert each row of results into a
          dictionary. Defaults to False.
    """
    self._conn = conn
    self._description = None
    self._rowcount = -1
    self.arraysize = 1
    self._open = True
    self.lastrowid = None
    self._use_dict_cursor = use_dict_cursor

  @property
  def description(self):
    return self._description

  @property
  def rowcount(self):
    return self._rowcount

  def close(self):
    """Marks the cursor as unusable for further operations."""
    self._CheckOpen()
    self._open = False

  def _GetJdbcTypeForArg(self, arg):
    """Get the JDBC type which corresponds to the given Python object type."""
    arg_jdbc_type = _PYTHON_TYPE_TO_JDBC_TYPE.get(type(arg))
    if arg_jdbc_type:
      return arg_jdbc_type


    for python_t, jdbc_t in _PYTHON_TYPE_TO_JDBC_TYPE.items():
      if isinstance(arg, python_t):
        return jdbc_t



    try:
      return self._GetJdbcTypeForArg(arg[0])
    except TypeError:


      raise TypeError('unknown type')


  def _EncodeVariable(self, arg):
    """Converts a variable to a type and value.

    Args:
      arg: Any tuple, string, numeric, or datetime object.

    Returns:
      A (int, str) tuple, representing a JDBC type and encoded value.

    Raises:
      TypeError: The argument is not a recognized type.
    """
    arg_jdbc_type = self._GetJdbcTypeForArg(arg)
    value = self._conn.encoders[type(arg)](arg, self._conn.encoders)
    return arg_jdbc_type, value

  def _DecodeVariable(self, datatype, value):
    """Converts a type and value to a variable.

    Args:
      datatype: An integer.
      value: A string.

    Returns:
      An object of some appropriate type.

    Raises:
      InterfaceError: datatype is not a recognized JDBC type.
      ValueError: The value could not be parsed.
    """

    converter = self._conn.converter.get(datatype)
    if converter is None:
      raise InterfaceError('unknown JDBC type %d' % datatype)
    return converter(value)

  def execute(self, statement, args=None):
    """Prepares and executes a database operation (query or command).

    Args:
      statement: A string, a SQL statement.
      args: A sequence of arguments matching the statement's bind variables,
        if any.

    Raises:
      InterfaceError: Unknown type used as a bind variable.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()

    request = sql_pb2.ExecRequest()
    request.options.include_generated_keys = True
    if args is not None:

      if not hasattr(args, '__iter__'):
        args = [args]
      for i, arg in enumerate(args):
        bv = request.bind_variable.add()
        bv.position = i + 1
        if arg is None:
          bv.type = jdbc_type.NULL
        else:
          try:
            bv.type, bv.value = self._EncodeVariable(arg)
          except TypeError:
            raise InterfaceError('unknown type %s for arg %d' % (type(arg), i))
    request.statement = _ConvertFormatToQmark(statement, args)

    response = self._conn.MakeRequest('Exec', request)
    result = response.result
    if result.HasField('sql_exception'):
      raise DatabaseError('%d: %s' % (result.sql_exception.code,
                                      result.sql_exception.message))

    self._rows = collections.deque()
    if result.rows.columns:
      self._description = []
      for column in result.rows.columns:
        self._description.append(
            (column.label, column.type, column.display_size, None,
             column.precision, column.scale, column.nullable))
    else:
      self._description = None

    if result.rows.tuples:
      assert self._description, 'Column descriptions do not exist.'
      column_names = [col[0] for col in self._description]
      self._rowcount = len(result.rows.tuples)
      for tuple_proto in result.rows.tuples:
        row = []
        nulls = set(tuple_proto.nulls)
        value_index = 0
        for i, column_descr in enumerate(self._description):
          if i in nulls:
            row.append(None)
          else:
            row.append(self._DecodeVariable(column_descr[1],
                                            tuple_proto.values[value_index]))
            value_index += 1
        if self._use_dict_cursor:
          assert len(column_names) == len(row)
          row = dict(zip(column_names, row))
        else:
          row = tuple(row)
        self._rows.append(row)
    else:
      self._rowcount = result.rows_updated

    if result.generated_keys:
      self.lastrowid = long(result.generated_keys[-1])

  def executemany(self, statement, seq_of_args):
    """Calls execute() for each value of seq_of_args.

    Args:
      statement: A string, a SQL statement.
      seq_of_args: A sequence, each entry of which is a sequence of arguments
        matching the statement's bind variables, if any.
    """
    self._CheckOpen()
    rowcount = 0
    for args in seq_of_args:
      self.execute(statement, args)
      rowcount += self.rowcount
    self._rowcount = rowcount

  def fetchone(self):
    """Fetches the next row of a query result set.

    Returns:
      A sequence, or None when no more data is available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchone() called before execute')
    try:
      return self._rows.popleft()
    except IndexError:
      return None

  def fetchmany(self, size=None):
    """Fetches the next set of rows of a query result.

    Args:
      size: The maximum number of rows to return; by default, self.arraysize.

    Returns:
      A sequence of sequences, or an empty sequence when no more data is
      available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchmany() called before execute')
    if size is None:
      size = self.arraysize
    if size >= len(self._rows):
      return self.fetchall()
    else:
      result = []
      for _ in xrange(size):
        result.append(self._rows.popleft())
      return tuple(result)

  def fetchall(self):
    """Fetches all remaining rows of a query result.

    Returns:
      A sequence of sequences, or an empty sequence when no more data is
      available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchall() called before execute')
    rows = self._rows
    self._rows = collections.deque()
    return tuple(rows)

  def setinputsizes(self, unused_sizes):
    self._CheckOpen()


  def setoutputsize(self, unused_size, unused_column=None):
    self._CheckOpen()


  def _CheckOpen(self):
    self._conn.CheckOpen()
    if not self._open:
      raise InternalError('cursor has been closed')

  def __iter__(self):
    return iter(self.fetchone, None)


class Connection(object):

  def __init__(self, dsn, instance, database=None, user='root', password=None,
               deadline_seconds=30.0, conv=None,
               query_deadline_seconds=86400.0, retry_interval_seconds=30.0):
    """Creates a new SQL Service connection.

    Args:
      dsn: A string, the SQL Service job path or host:port.
      instance: A string, the SQL Service instance name, often a username.
      database: A string, semantics defined by the backend.
      user: A string, database user name.
      password: A string, database password.
      deadline_seconds: A float, request deadline in seconds.
      conv: A dict, maps types to a conversion function. See converters.py.
      query_deadline_seconds: A float, query deadline in seconds.
      retry_interval_seconds: A float, seconds to wait between each retry.
    Raises:
      OperationalError: Transport failure.
      DatabaseError: Error from SQL Service server.
    """



    self._dsn = dsn
    self._instance = instance
    self._database = database
    self._user = user
    self._password = password
    self._deadline_seconds = deadline_seconds
    self._connection_id = None
    self._idempotent_request_id = 0
    if not conv:
      conv = converters.conversions
    self._query_deadline_seconds = query_deadline_seconds
    self._retry_interval_seconds = retry_interval_seconds
    self.converter = {}
    self.encoders = {}
    for key, value in conv.items():
      if isinstance(key, int):
        self.converter[key] = value
      else:
        self.encoders[key] = value

    self.OpenConnection()

  def OpenConnection(self):
    """Opens a connection to SQL Service."""
    request = sql_pb2.OpenConnectionRequest()
    request.client_type = client_pb2.CLIENT_TYPE_PYTHON_DBAPI
    prop = request.property.add()
    prop.key = 'autoCommit'
    prop.value = 'false'
    if self._user:
      prop = request.property.add()
      prop.key = 'user'
      prop.value = self._user
    if self._password:
      prop = request.property.add()
      prop.key = 'password'
      prop.value = self._password
    if self._database:
      prop = request.property.add()
      prop.key = 'database'
      prop.value = self._database

    self.SetupClient()
    response = self.MakeRequest('OpenConnection', request)
    self._connection_id = response.connection_id

  def SetupClient(self):
    """Setup a transport client to communicate with rdbms.

    This is a template method to provide subclasses with a hook to perform any
    necessary client initialization while opening a connection to rdbms.
    """
    pass

  def close(self):
    """Makes the connection and all its cursors unusable.

    The connection will be unusable from this point forward; an Error
    (or subclass) exception will be raised if any operation is attempted
    with the connection.
    """
    self.CheckOpen()
    request = sql_pb2.CloseConnectionRequest()
    self.MakeRequest('CloseConnection', request)
    self._connection_id = None

  def CheckOpen(self):
    if self._connection_id is None:
      raise InternalError('connection has been closed')

  def commit(self):
    """Commits any pending transaction to the database.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.COMMIT
    self.MakeRequest('ExecOp', request)

  def rollback(self):
    """Rolls back any pending transaction to the database.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.ROLLBACK
    self.MakeRequest('ExecOp', request)

  def autocommit(self, value):
    """Changes whether there is an implicit commit after each statement.

    By default, transactions must be explicitly committed.

    Args:
      value: A boolean.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.SET_AUTO_COMMIT
    request.op.auto_commit = value
    self.MakeRequest('ExecOp', request)

  def cursor(self, **kwargs):
    """Returns a cursor for the current connection.

    Args:
      **kwargs: Optional keyword args to pass into cursor.

    Returns:
      A Cursor object.
    """
    return Cursor(self, **kwargs)

  def MakeRequest(self, stub_method, request):
    """Makes an ApiProxy request, and possibly raises an appropriate exception.

    Args:
      stub_method: A string, the name of the method to call.
      request: A protobuf; 'instance' and 'connection_id' will be set
        when available.

    Returns:
      A protobuf.

    Raises:
      DatabaseError: Error from SQL Service server.
    """
    if self._instance:
      request.instance = self._instance
    if self._connection_id is not None:
      request.connection_id = self._connection_id
    if stub_method in ('Exec', 'ExecOp', 'GetMetadata'):
      self._idempotent_request_id += 1
      request.request_id = self._idempotent_request_id
      response = self._MakeRetriableRequest(stub_method, request)
    else:
      response = self.MakeRequestImpl(stub_method, request)

    if (hasattr(response, 'sql_exception') and
        response.HasField('sql_exception')):
      raise DatabaseError('%d: %s' % (response.sql_exception.code,
                                      response.sql_exception.message))
    return response

  def _MakeRetriableRequest(self, stub_method, request):
    """Makes a retriable request.

    Args:
      stub_method: A string, the name of the method to call.
      request: A protobuf.

    Returns:
      A protobuf.

    Raises:
      DatabaseError: Error from SQL Service server.
    """
    absolute_deadline_seconds = time.clock() + self._query_deadline_seconds
    response = self.MakeRequestImpl(stub_method, request)
    if not response.HasField('sql_exception'):
      return response
    sql_exception = response.sql_exception
    if (sql_exception.application_error_code !=
        client_error_code_pb2.SqlServiceClientError.ERROR_TIMEOUT):
      raise DatabaseError('%d: %s' % (sql_exception.code,
                                      sql_exception.message))
    if time.clock() >= absolute_deadline_seconds:
      raise DatabaseError('%d: %s' % (sql_exception.code,
                                      sql_exception.message))
    return self._Retry(stub_method, request.request_id,
                       absolute_deadline_seconds)

  def _Retry(self, stub_method, request_id, absolute_deadline_seconds):
    """Retries request with the given request id.

    Continues to retry until either the deadline has expired or the response
    has been received.

    Args:
      stub_method: A string, the name of the original method that triggered the
                   retry.
      request_id: An integer, the request id used in the original request
      absolute_deadline_seconds: An integer, absolute deadline in seconds.

    Returns:
      A protobuf.

    Raises:
      DatabaseError: If the ExecOpResponse contains a SqlException that it not
                     related to retry.
      InternalError: If the ExceOpResponse is not valid.
    """
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.RETRY
    request.op.request_id = request_id
    request.connection_id = self._connection_id
    request.instance = self._instance
    while True:
      seconds_remaining = absolute_deadline_seconds - time.clock()
      if seconds_remaining <= 0:
        raise InternalError('Request [%d] timed out' % (request_id))
      time.sleep(min(self._retry_interval_seconds, seconds_remaining))
      self._idempotent_request_id += 1
      request.request_id = self._idempotent_request_id
      response = self.MakeRequestImpl('ExecOp', request)
      if not response.HasField('sql_exception'):
        return self._ConvertCachedResponse(stub_method, response)
      sql_exception = response.sql_exception
      if (sql_exception.application_error_code !=
          client_error_code_pb2.SqlServiceClientError.ERROR_RESPONSE_PENDING):
        raise DatabaseError('%d: %s' % (response.sql_exception.code,
                                        response.sql_exception.message))

  def _ConvertCachedResponse(self, stub_method, exec_op_response):
    """Converts the cached response or RPC error.

    Args:
      stub_method: A string, the name of the original method that triggered the
                   retry.
      exec_op_response: A protobuf, the retry response that contains either the
                        RPC error or the cached response.

    Returns:
      A protobuf, the cached response.

    Raises:
      DatabaseError: If the cached response contains SqlException.
      InternalError: If a cached RpcErrorProto exists.
    """
    if exec_op_response.HasField('cached_rpc_error'):
      raise InternalError('%d: %s' % (
          exec_op_response.cached_rpc_error.error_code,
          exec_op_response.cached_rpc_error.error_message))
    if not exec_op_response.HasField('cached_payload'):
      raise InternalError('Invalid exec op response for retry request')
    if stub_method == 'Exec':
      response = sql_pb2.ExecResponse()
    elif stub_method == 'ExecOp':
      response = sql_pb2.ExecOpResponse()
    elif stub_method == 'GetMetadata':
      response = sql_pb2.MetadataResponse()
    else:
      raise InternalError('Found unexpected stub_method: %s' % (stub_method))
    response.ParseFromString(exec_op_response.cached_payload)
    if response.HasField('sql_exception'):
      raise DatabaseError('%d: %s' % (response.sql_exception.code,
                                      response.sql_exception.message))
    return response

  def MakeRequestImpl(self, stub_method, request):
    raise InternalError('No transport defined. Try using rdbms_[transport]')

  def get_server_info(self):
    """Returns a string that represents the server version number.

    Non-standard; Provided for API compatibility with MySQLdb.

    Returns:
      The server version number string.
    """
    self.CheckOpen()
    request = sql_pb2.MetadataRequest()
    request.metadata = client_pb2.METADATATYPE_DATABASE_METADATA_BASIC
    response = self.MakeRequest('GetMetadata', request)
    return response.jdbc_database_metadata.database_product_version

  def ping(self, reconnect=False):
    """Checks whether or not the connection to the server is working.

    If it has gone down, an automatic reconnection is attempted.

    This function can be used by clients that remain idle for a long while, to
    check whether or not the server has closed the connection and reconnect if
    necessary.

    Non-standard. You should assume that ping() performs an implicit rollback;
    use only when starting a new transaction.  You have been warned.

    Args:
      reconnect: Whether to perform an automatic reconnection.

    Raises:
      DatabaseError: The connection to the server is not working.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.PING
    try:
      self.MakeRequest('ExecOp', request)
    except DatabaseError:
      if not reconnect:
        raise


      self._connection_id = None
      self.OpenConnection()




  Warning = Warning
  Error = Error
  InterfaceError = InterfaceError
  DatabaseError = DatabaseError
  DataError = DataError
  OperationalError = OperationalError
  IntegrityError = IntegrityError
  InternalError = InternalError
  ProgrammingError = ProgrammingError
  NotSupportedError = NotSupportedError

connect = Connection
