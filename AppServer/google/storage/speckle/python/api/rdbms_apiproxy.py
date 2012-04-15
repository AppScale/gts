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




"""SQL Service connection module for ApiProxy."""


from google.appengine.api import apiproxy_stub_map
from google.appengine.runtime import apiproxy_errors
from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python.api import rdbms

__path__ = rdbms.__path__



class ApiProxyConnection(rdbms.Connection):
  """ApiProxy specific SQL Service connection."""

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
    elif stub_method == 'GetMetadata':
      return sql_pb2.MetadataResponse()

  def MakeRequestImpl(self, stub_method, request):
    """Makes an ApiProxy request, and possibly raises an appropriate exception.

    Args:
      stub_method: A string, the name of the method to call.
      request: A protobuf; 'instance' and 'connection_id' will be set
        when available.

    Returns:
      A protobuf.

    Raises:
      OperationalError: ApiProxy failure.
    """
    response = self._CreateResponse(stub_method)
    try:
      apiproxy_stub_map.MakeSyncCall('rdbms', stub_method, request, response)
    except apiproxy_errors.ApplicationError, e:
      raise OperationalError('could not connect: ' + str(e))
    return response






apilevel = rdbms.apilevel
threadsafety = rdbms.threadsafety
paramstyle = rdbms.paramstyle


version_info = rdbms.version_info



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
