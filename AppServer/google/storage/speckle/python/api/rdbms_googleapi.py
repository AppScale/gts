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




"""Speckle connection module for Google API."""




import logging
import os

import google

try:
  import apiclient
except ImportError:



  try:
    import google_sql
    google_sql.fix_sys_path(google_sql.GOOGLE_SQL_EXTRA_PATHS)
  except ImportError:
    logging.warning(
        'Attempt to automatically load Google Cloud SQL dependencies failed! '
        'Ensure that the App Engine SDK directory has been added to your '
        'PYTHONPATH when using this backend.')

from apiclient import errors
from apiclient import http
from apiclient import model
import httplib2
from oauth2client import client
from oauth2client import file as oauth_file

from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python.api import rdbms

__path__ = rdbms.__path__


CLIENT_ID = '877927577750.apps.googleusercontent.com'
CLIENT_SECRET = '7nBqns87ugMSNBrOM1FdHMK6'
USER_AGENT = 'Google SQL Service/1.0'


def GetFlow(state=None):
  """Get a client.OAuth2WebServerFlow for performing OAuth 2.0 authentication.

  Args:
    state: Value to use for the OAuth 2.0 state parameter.

  Returns:
    A client.OAuth2WebServerFlow instance populated with default values for
    getting access to the SQL Service over Google API.
  """
  return client.OAuth2WebServerFlow(
      client_id=CLIENT_ID,
      client_secret=CLIENT_SECRET,
      scope='https://www.googleapis.com/auth/sqlservice',
      user_agent=USER_AGENT,
      state=state)


class RdbmsGoogleApiClient(object):
  """A Google API client for rdbms."""

  def __init__(self, api_url='https://www.googleapis.com/sql/v1/',
               oauth_credentials_path=None, oauth_storage=None,
               developer_key=None):
    """Constructs an RdbmsGoogleApiClient.

    Args:
      api_url: The base of the URL for the rdbms Google API.
      oauth_credentials_path: The filesystem path to use for OAuth 2.0
          credentials storage.
      oauth_storage: A client.Storage instance to use for OAuth 2.0 credential
          storage instead of the default file based storage.
      developer_key: A Google APIs developer key to use when connecting to the
          SQL service.
    """
    self._api_url = api_url
    self._developer_key = developer_key
    if oauth_storage is None:
      if oauth_credentials_path is None:


        oauth_credentials_path = os.path.expanduser(
            rdbms.OAUTH_CREDENTIALS_PATH)
      oauth_storage = oauth_file.Storage(oauth_credentials_path)
    credentials = oauth_storage.get()
    if credentials is None or credentials.invalid:





      from oauth2client import tools
      credentials = tools.run(GetFlow(), oauth_storage)
    self._transport = credentials.authorize(httplib2.Http())

  def OpenConnection(self, request):
    return self._MakeRequest(
        'jdbc/openConnection', request, sql_pb2.OpenConnectionResponse)

  def CloseConnection(self, request):
    return self._MakeRequest(
        'jdbc/closeConnection', request, sql_pb2.CloseConnectionResponse)

  def Exec(self, request):
    return self._MakeRequest('jdbc/exec', request, sql_pb2.ExecResponse)

  def ExecOp(self, request):
    return self._MakeRequest('jdbc/execOp', request, sql_pb2.ExecOpResponse)

  def GetMetadata(self, request):
    return self._MakeRequest(
        'jdbc/getMetadata', request, sql_pb2.MetadataResponse)

  def _MakeRequest(self, method, request, response_class):
    """Executes a request to the Google API server.

    Args:
      method: The method to invoke.
      request: The request protocol buffer from sql_pb2.
      response_class: The response protocol buffer class from sql_pb2.

    Returns:
      A protocol buffer instance of the given response_class type.
    """
    pb_model = model.ProtocolBufferModel(response_class)
    query_params = {}
    if self._developer_key:
      query_params['key'] = self._developer_key
    headers, unused_params, query, body = pb_model.request(
        {}, {}, query_params, request)
    request = http.HttpRequest(
        self._transport, pb_model.response, self._api_url + method + query,
        method='POST', body=body, headers=headers)
    return request.execute()


class GoogleApiConnection(rdbms.Connection):
  """Google API specific rdbms connection."""

  def __init__(self, *args, **kwargs):
    """Constructs a GoogleApiConnection.

    In addition to all of the arguments taken by rdbms.Connection.__init__, this
    also accepts the following optional keyword arguments:

    oauth_credentials_path: The filesystem path to the file used for OAuth 2.0
        credential storage.
    oauth_storage: A client.Storage instance to use for OAuth 2.0 credential
        storage instead of the default file based storage.
    developer_key: A Google APIs developer key to use when connecting to the SQL
        service.

    Args:
      args: Positional arguments to pass to parent method.
      kwargs: Keyword arguments to pass to parent method.
    """
    self._oauth_credentials_path = kwargs.pop('oauth_credentials_path', None)
    self._oauth_storage = kwargs.pop('oauth_storage', None)
    self._developer_key = kwargs.pop('developer_key', None)
    super(GoogleApiConnection, self).__init__(*args, **kwargs)

  def SetupClient(self):
    """Opens a Google API connection to rdbms."""
    kwargs = {'developer_key': self._developer_key,
              'oauth_storage': self._oauth_storage}
    if self._dsn:
      kwargs['api_url'] = self._dsn
    if self._oauth_credentials_path:
      kwargs['oauth_credentials_path'] = self._oauth_credentials_path
    self._client = RdbmsGoogleApiClient(**kwargs)

  def MakeRequestImpl(self, stub_method, request):
    """Makes a Google API request, and possibly raises an appropriate exception.

    Args:
      stub_method: A string, the name of the method to call.
      request: A protobuf; 'instance' and 'connection_id' will be set
        when available.

    Returns:
      A protobuf.

    Raises:
      OperationalError: httplib2 transport failure, or non 2xx http response.
    """
    try:
      response = getattr(self._client, stub_method)(request)
    except (errors.Error, client.Error, httplib2.HttpLib2Error), e:
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

connect = GoogleApiConnection
