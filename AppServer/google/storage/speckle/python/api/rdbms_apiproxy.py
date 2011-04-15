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




"""Speckle connection module for ApiProxy."""


from google.appengine.api import apiproxy_stub_map
from google.appengine.runtime import apiproxy_errors
from google.storage.speckle.proto import client_pb2
from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python.api import rdbms


class ApiProxyConnection(rdbms.Connection):
  """ApiProxy specific Speckle connection."""

  def OpenConnection(self):
    """Opens an ApiProxy connection to speckle."""
    request = sql_pb2.OpenConnectionRequest()
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

    response = self.MakeRequest('OpenConnection', request)

    self._connection_id = response.connection_id

    if self._database:
      request = sql_pb2.ExecOpRequest()
      request.op.type = client_pb2.OpProto.SET_CATALOG
      request.op.catalog = self._database
      self.MakeRequest('ExecOp', request)

  def _CreateResponse(self, stub_method):
    """Creates the protocol buffer response object for stub_method."""

    if stub_method == 'OpenConnection':
      return sql_pb2.OpenConnectionResponse()
    elif stub_method == 'CloseConnection':
      return sql_pb2.CloseConnectionResponse()
    elif stub_method == 'Exec':
      return sql_pb2.ExecResponse()
    elif stub_method == 'ExecOp':
      return sql_pb2.ExecOpResponse()
    elif stub_method == 'Metadata':
      return sql_pb2.MetadataResponse()

  def MakeRequest(self, stub_method, request):
    """Makes an ApiProxy request, and possibly raises an appropriate exception.

    Args:
      stub_method: A string, the name of the method to call.
      request: A protobuf; 'instance' and 'connection_id' will be set
        when available.

    Returns:
      A protobuf.

    Raises:
      OperationalError: ApiProxy failure.
      DatabaseError: Error from Speckle server.
    """
    if self._instance:
      request.instance = self._instance
    if self._connection_id is not None:
      request.connection_id = self._connection_id

    response = self._CreateResponse(stub_method)

    try:
      apiproxy_stub_map.MakeSyncCall('rdbms', stub_method, request, response)
    except apiproxy_errors.ApplicationError, e:
      raise OperationalError('could not connect: ' + str(e))
    if (hasattr(response, 'sql_exception') and
        response.HasField('sql_exception')):
      raise DatabaseError('%d: %s' % (response.sql_exception.code,
                                      response.sql_exception.message))
    return response






apilevel = rdbms.apilevel
threadsafety = rdbms.threadsafety
paramstyle = rdbms.paramstyle




Binary = rdbms.Binary
Date = rdbms.Date
Time = rdbms.Time
Timestamp = rdbms.Timestamp
DateFromTicks = rdbms.DateFromTicks
TimeFromTicks = rdbms.TimeFromTicks
TimestampFromTicks = rdbms.TimestampFromTicks

STRING = rdbms.STRING
BINARY = rdbms.BINARY
NUMBER = rdbms.NUMBER
DATETIME = rdbms.DATETIME
ROWID = rdbms.ROWID


Warning = rdbms.Warning
Error = rdbms.Error
InterfaceError = rdbms.InterfaceError
DatabaseError = rdbms.DatabaseError
DataError = rdbms.DataError
OperationalError = rdbms.OperationalError
IntegrityError = rdbms.IntegrityError
InternalError = rdbms.InternalError
ProgrammingError = rdbms.ProgrammingError
NotSupportedError = rdbms.NotSupportedError

connect = ApiProxyConnection
