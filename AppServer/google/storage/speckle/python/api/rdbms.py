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
import decimal
import exceptions
import sys
import time
import types

from google.storage.speckle.proto import client_error_code_pb2
from google.storage.speckle.proto import client_pb2
from google.storage.speckle.proto import jdbc_type
from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python import api
from google.storage.speckle.python.api import converters




__path__ = api.__path__








OAUTH_CREDENTIALS_PATH = '~/.googlesql_oauth2.dat'






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
    decimal.Decimal: jdbc_type.DECIMAL,
    }



_EXCEPTION_TO_ERROR_CODES = {
    ProgrammingError: (
        1007,
        1064,
        1102,
        1103,
        1110,
        1111,
        1112,
        1113,
        1146,
        1149,
        1179,
        ),
    DataError: (
        1265,
        1263,
        1264,
        1230,
        1171,
        1406,
        1441,
        ),
    NotSupportedError: (
        1196,
        1235,
        1289,
        1286,
        ),
    IntegrityError: (
        1062,
        1169,
        1216,
        1452,
        1217,
        1451,
        1215,
        ),
    }




_ERROR_CODE_TO_EXCEPTION = {}
for error, codes in _EXCEPTION_TO_ERROR_CODES.iteritems():
  for code in codes:
    _ERROR_CODE_TO_EXCEPTION[code] = error


def _ToDbApiException(sql_exception):
  """Returns a DB-API exception type appropriate for the given sql_exception.

  Args:
    sql_exception: The client_pb2.SqlException.

  Returns:
    The appropriate DatabaseError subclass for the error code in the given
    sql_exception.
  """
  exception = _ERROR_CODE_TO_EXCEPTION.get(sql_exception.code)
  if not exception:
    if sql_exception.code < 1000:
      exception = InternalError
    else:
      exception = OperationalError
  return exception(sql_exception.code, sql_exception.message)


def _ConvertFormatToQmark(statement, args):
  """Replaces '%s' or '%(name)s' with '?'.

  The server actually supports '?' for bind parameters, but the
  MySQLdb implementation of PEP 249 uses 'format' paramstyle (%s) when the
  given args list is a sequence, and 'pyformat' paramstyle (%(name)s) when the
  args list is a mapping.  Most clients don't bother checking the paramstyle
  member and just hardcode '%s' or '%(name)s' in their statements.  This
  function converts a (py)format-style statement into a qmark-style statement.

  Args:
    statement: A string, a SQL statement.
    args: A sequence of arguments matching the statement's bind variables,
        if any.

  Returns:
    The converted string.
  """
  if isinstance(args, dict):
    return statement % collections.defaultdict(lambda: '?')
  elif args:
    qmarks = tuple('?' * len(args))
    return statement % qmarks
  return statement


class _AccessLogger(object):
  """Simple dict-like object that records all lookup attempts.

  Attributes:
    accessed_keys: List of all lookup keys, in the order which they occurred.
  """

  def __init__(self):
    self.accessed_keys = []

  def __getitem__(self, key):
    self.accessed_keys.append(key)
    return ''


def _ConvertArgsDictToList(statement, args):
  """Convert a given args mapping to a list of positional arguments.

  Takes a statement written in 'pyformat' style which uses mapping keys from
  the given args mapping, and returns the list of args values that would be
  used for interpolation if the statement were written in a positional
  'format' style instead.

  For example, consider the following pyformat string and a mapping used for
  interpolation:

    '%(foo)s '%(bar)s' % {'foo': 1, 'bar': 2}

  Given these parameters, this function would return the following output:

    [1, 2]

  This could then be used for interpolation if the given string were instead
  expressed using a positional format style:

    '%s %s' % (1, 2)

  Args:
    statement: The statement, possibly containing pyformat style tokens.
    args: Mapping to pull values from.

  Returns:
    A list containing values from the given args mapping.
  """
  access_logger = _AccessLogger()
  statement % access_logger
  return [args[key] for key in access_logger.accessed_keys]


class Cursor(object):

  def __init__(self, conn, use_dict_cursor=False, fetch_size=None):
    """Initializer.

    Args:
      conn: A Connection object.
      use_dict_cursor: Optional boolean to convert each row of results into a
          dictionary. Defaults to False.
      fetch_size: An integer, batch size to fetch the result set from server if
      streaming. Defaults to None.
    """
    self._conn = conn
    self._open = True
    self._use_dict_cursor = use_dict_cursor
    self._fetch_size = fetch_size
    self.arraysize = 1
    self._executed = None
    self.lastrowid = None
    self._Reset()

  def _Reset(self):

    self._description = None
    self._rows = collections.deque()
    self._rowcount = -1
    self._statement_id = -1
    self._more_rows = None
    self._more_results = None

  @property
  def description(self):
    return self._description

  @property
  def rowcount(self):
    if self._more_rows:
      return -1
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

  def _AddBindVariablesToRequest(self, statement, args, bind_variable_factory,
                                 direction=client_pb2.BindVariableProto.IN):
    """Add args to the request BindVariableProto list.

    Args:
      statement: The SQL statement.
      args: Sequence of arguments to turn into BindVariableProtos.
      bind_variable_factory: A callable which returns new BindVariableProtos.
      direction: The direction to set for all variables in the request.

    Raises:
      InterfaceError: Unknown type used as a bind variable.
    """
    if isinstance(args, dict):
      args = _ConvertArgsDictToList(statement, args)

    for i, arg in enumerate(args):
      bv = bind_variable_factory()
      bv.position = i + 1
      bv.direction = direction
      if arg is None:
        bv.type = jdbc_type.NULL
      else:
        try:
          bv.type, bv.value = self._EncodeVariable(arg)
        except TypeError:
          raise InterfaceError('unknown type %s for arg %d' % (type(arg), i))

  def _DoExec(self, request):
    """Send an ExecRequest and handle the response.

    Args:
      request: The sql_pb2.ExecRequest to send.

    Returns:
      The client_pb2.ResultProto returned by the server.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    if self._fetch_size:
      request.options.fetch_size = self._fetch_size
    response = self._conn.MakeRequest('Exec', request)
    return self._HandleResult(response.result)

  def _GetDescription(self, result):
    """Returns a list of tuples describing the columns in the result set.

    Args:
      result: The client_pb2.ResultProto to process.

    Returns:
      A sequence of sequences describing the columns in the result set. Returns
      None if column description is not present in the result proto.
    """
    if not result.rows.columns:

      return None
    return [(column.label, column.type, column.display_size, None,
             column.precision, column.scale, column.nullable)
            for column in result.rows.columns]

  def _HandleResult(self, result):
    """Handle the ResultProto from an Exec/ExecOp call.

    Args:
      result: The client_pb2.ResultProto to handle.

    Returns:
      The given client_pb2.ResultProto.

    Raises:
      DatabaseError: A SQL exception occurred.
    """
    if result.HasField('rows'):
      description = self._GetDescription(result)
      if description:
        self._description = description
      if not self._rows:


        self._rows = collections.deque()
      new_rows = self._GetRows(result)
      if new_rows is not None:
        if self._rowcount == -1:
          self._rowcount = len(new_rows)
        else:
          self._rowcount += len(new_rows)
        self._rows.extend(new_rows)
    elif result.HasField('rows_updated'):
      self._rowcount = result.rows_updated

    if result.generated_keys:
      self.lastrowid = long(result.generated_keys[-1])

    if result.HasField('statement_id'):
      self._statement_id = result.statement_id

    self._more_rows = result.more_rows
    self._more_results = result.more_results
    return result

  def _GetRows(self, result):
    """Returns a sequence of sequences containing the result set.

    Args:
      result: The client_pb2.ResultProto to process.

    Returns:
      A sequence of sequences, or an empty sequence when result set is empty.
      Returns None if result set is not present.
    """
    if not result.rows.tuples:

      return None
    assert self._description, 'Column descriptions do not exist.'
    column_names = [col[0] for col in self._description]
    rows = []
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
      rows.append(row)
    return rows

  def execute(self, statement, args=None):
    """Prepares and executes a database operation (query or command).

    Args:
      statement: A string, a SQL statement.
      args: A sequence or mapping of arguments matching the statement's bind
        variables, if any.

    Raises:
      InterfaceError: Unknown type used as a bind variable.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()
    self._Reset()

    request = sql_pb2.ExecRequest()
    request.options.include_generated_keys = True
    if args is not None:

      if not hasattr(args, '__iter__'):
        args = [args]
      self._AddBindVariablesToRequest(
          statement, args, request.bind_variable.add)
    request.statement = _ConvertFormatToQmark(statement, args)
    self._DoExec(request)
    self._executed = request.statement

  def executemany(self, statement, seq_of_args):
    """Prepares and executes a database operation for given parameter sequences.

    Args:
      statement: A string, a SQL statement.
      seq_of_args: A sequence, each entry of which is a sequence or mapping of
        arguments matching the statement's bind variables, if any.

    Raises:
      InterfaceError: Unknown type used as a bind variable.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()
    self._Reset()

    request = sql_pb2.ExecRequest()
    request.options.include_generated_keys = True

    args = None
    for args in seq_of_args:

      if not hasattr(args, '__iter__'):
        args = [args]
      bbv = request.batch.batch_bind_variable.add()
      self._AddBindVariablesToRequest(
          statement, args, bbv.bind_variable.add)
    request.statement = _ConvertFormatToQmark(statement, args)
    result = self._DoExec(request)
    self._executed = request.statement
    self._rowcount = sum(result.batch_rows_updated)

  def _FetchMoreRows(self):
    """Fetches more rows from the server for a previously executed statement."""
    request = sql_pb2.ExecRequest()
    request.statement_id = self._statement_id
    self._DoExec(request)

  def callproc(self, procname, args=()):
    """Calls a stored database procedure with the given name.

    Args:
      procname: A string, the name of the stored procedure.
      args: A sequence of parameters to use with the procedure.

    Returns:
      A modified copy of the given input args. Input parameters are left
      untouched, output and input/output parameters replaced with possibly new
      values.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()
    self._Reset()

    request = sql_pb2.ExecRequest()
    request.statement_type = sql_pb2.ExecRequest.CALLABLE_STATEMENT
    request.statement = 'CALL %s(%s)' % (procname, ','.join('?' * len(args)))




    self._AddBindVariablesToRequest(
        request.statement, args, request.bind_variable.add,
        direction=client_pb2.BindVariableProto.INOUT)
    result = self._DoExec(request)
    self._executed = request.statement


    return_args = list(args[:])
    for var in result.output_variable:
      return_args[var.position - 1] = self._DecodeVariable(var.type, var.value)
    return tuple(return_args)

  def nextset(self):
    """Advance to the next result set.

    Returns:
      True if there was an available set to advance to, otherwise, None.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()
    self._CheckExecuted('nextset() called before execute')



    self._rows = collections.deque()
    self._rowcount = -1
    if not self._more_results:
      return None

    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.NEXT_RESULT
    request.op.statement_id = self._statement_id
    self._HandleResult(self._conn.MakeRequest('ExecOp', request).result)
    return True

  def fetchone(self):
    """Fetches the next row of a query result set.

    Returns:
      A sequence, or None when no more data is available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    self._CheckExecuted('fetchone() called before execute')
    if not self._rows and self._more_rows:
      self._FetchMoreRows()
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
    self._CheckExecuted('fetchmany() called before execute')
    if size is None:
      size = self.arraysize
    while self._more_rows and size > len(self._rows):
      self._FetchMoreRows()

    if size >= len(self._rows):
      rows = self._rows
      self._rows = collections.deque()
      return tuple(rows)
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
    self._CheckExecuted('fetchall() called before execute')
    while self._more_rows:
      self._FetchMoreRows()
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

  def _CheckExecuted(self, msg):
    if not self._executed:
      raise InternalError(msg)

  def __iter__(self):
    return iter(self.fetchone, None)


class Connection(object):

  def __init__(self, dsn, instance, database=None, user='root', password=None,
               deadline_seconds=60.0, conv=None,
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
      TypeError: Invalid value provided for instance.
    """



    self._dsn = dsn
    if not instance:
      raise TypeError('Invalid value for instance (%s)' % instance)
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
    try:
      self.MakeRequest('CloseConnection', request)
    except DatabaseError:


      pass
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
      raise _ToDbApiException(response.sql_exception)
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
      raise _ToDbApiException(sql_exception)
    if time.clock() >= absolute_deadline_seconds:
      raise _ToDbApiException(sql_exception)
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
        raise _ToDbApiException(response.sql_exception)

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
      raise _ToDbApiException(response.sql_exception)
    return response

  def MakeRequestImpl(self, unused_stub_method, unused_request):
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
