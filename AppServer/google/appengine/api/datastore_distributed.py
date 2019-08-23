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

"""
AppScale modifications 

Distributed Method:
All calls are made to a datastore server for queries, gets, puts, and deletes,
index functions, transaction functions.
"""

import datetime
import logging
import os
import time
import random
import sys
import threading
import warnings

try:
  from urllib3 import HTTPConnectionPool
  from urllib3.exceptions import MaxRetryError
  POOL_CONNECTIONS = True
except ImportError:
  POOL_CONNECTIONS = False

from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.runtime import apiproxy_errors
from google.net.proto import ProtocolBuffer
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.datastore import old_datastore_stub_util

try:
  __import__('google.appengine.api.taskqueue.taskqueue_service_pb')
  taskqueue_service_pb = sys.modules.get(
      'google.appengine.api.taskqueue.taskqueue_service_pb')
except ImportError:
  from google.appengine.api.taskqueue import taskqueue_service_pb

warnings.filterwarnings('ignore', 'tempnam is a potential security risk')


entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Transaction.__hash__ = lambda self: hash(self.Encode())


_MAX_QUERY_COMPONENTS = 100


_BATCH_SIZE = 20


_MAX_ACTIONS_PER_TXN = 5


_MAX_INT_32 = 2**31-1

# The location of the file that keeps track of available load balancers.
LOAD_BALANCERS_FILE = "/etc/appscale/load_balancer_ips"

# The port on the load balancer that serves datastore requests.
PROXY_PORT = 8888


def get_random_lb_host():
  """ Selects a random host from the load balancers file.

  Returns:
    A string specifying a load balancer IP.
  """
  with open(LOAD_BALANCERS_FILE) as lb_file:
    return random.choice(line.strip() for line in lb_file)


class InternalCursor():
  """ Keeps track of where we are in a query. Used for when queries are done
  in batches.
  """
  def __init__(self, query, last_cursor, offset):
    """ Constructor.

    Args:
      query: Starting query, a datastore_pb.Query.
      last_cursor: A compiled cursor, the last from a result list.
      offset: The number of entities we've seen so far.
    """
    # Count is the limit we want to hit so we know we're done.
    self.__count = _MAX_INT_32
    if query.has_count():
      self.__count = query.count()
    elif query.has_limit():
      self.__count = query.limit()
    self.__query = query
    self.__last_cursor = last_cursor
    self.__creation = time.time()
    # Lets us know how many results we've seen so far. When
    # this hits the count we know we're done.
    self.__offset = offset

  def get_query(self):
    return self.__query

  def get_count(self):
    return self.__count

  def get_last_cursor(self):
    return self.__last_cursor

  def get_offset(self):
    return self.__offset

  def get_timestamp(self):
    return self.__creation

  def set_last_cursor(self, last_cursor):
    self.__last_cursor = last_cursor

  def set_offset(self, offset):
    self.__offset = offset

class DatastoreDistributed(apiproxy_stub.APIProxyStub):
  """ A central server hooks up to a db and communicates via protocol 
      buffers.

  """
  THREADSAFE = True

  _ACCEPTS_REQUEST_ID = True

  _PROPERTY_TYPE_TAGS = {
    datastore_types.Blob: entity_pb.PropertyValue.kstringValue,
    bool: entity_pb.PropertyValue.kbooleanValue,
    datastore_types.Category: entity_pb.PropertyValue.kstringValue,
    datetime.datetime: entity_pb.PropertyValue.kint64Value,
    datastore_types.Email: entity_pb.PropertyValue.kstringValue,
    float: entity_pb.PropertyValue.kdoubleValue,
    datastore_types.GeoPt: entity_pb.PropertyValue.kPointValueGroup,
    datastore_types.IM: entity_pb.PropertyValue.kstringValue,
    int: entity_pb.PropertyValue.kint64Value,
    datastore_types.Key: entity_pb.PropertyValue.kReferenceValueGroup,
    datastore_types.Link: entity_pb.PropertyValue.kstringValue,
    long: entity_pb.PropertyValue.kint64Value,
    datastore_types.PhoneNumber: entity_pb.PropertyValue.kstringValue,
    datastore_types.PostalAddress: entity_pb.PropertyValue.kstringValue,
    datastore_types.Rating: entity_pb.PropertyValue.kint64Value,
    str: entity_pb.PropertyValue.kstringValue,
    datastore_types.Text: entity_pb.PropertyValue.kstringValue,
    type(None): 0,
    unicode: entity_pb.PropertyValue.kstringValue,
    users.User: entity_pb.PropertyValue.kUserValueGroup,
    }

  def __init__(self,
               app_id,
               datastore_location,
               service_name='datastore_v3',
               trusted=False):
    """Constructor.

    Args:
      app_id: string
      datastore_location: location of datastore server
      service_name: Service name expected for all calls.
      trusted: bool, default False.  If True, this stub allows an app to
        access the data of another app.
    """
    super(DatastoreDistributed, self).__init__(service_name)

    # TODO lock any use of these global variables
    assert isinstance(app_id, basestring) and app_id != ''
    self.project_id = app_id
    self.__datastore_location = datastore_location

    self._ds_pool = None
    if POOL_CONNECTIONS:
      host, port = datastore_location.split(':')
      port = int(port)
      self._ds_pool = HTTPConnectionPool(host, port, maxsize=8)

    self._service_id = os.environ.get('CURRENT_MODULE_ID', 'default')
    self._version_id = os.environ.get('CURRENT_VERSION_ID', 'v1').split('.')[0]

    self.SetTrusted(trusted)

    self.__queries = {}

    self.__tx_actions = {}

    self.__cursor_id = 1
    self.__cursor_lock = threading.Lock()

  def __getCursorID(self):
    """ Gets a cursor identifier. """
    self.__cursor_lock.acquire()
    self.__cursor_id += 1
    cursor_id = self.__cursor_id
    self.__cursor_lock.release()
    return cursor_id 

  def Clear(self):
    """ Clears the datastore by deleting all currently stored entities and
    queries. """
    pass

  def SetTrusted(self, trusted):
    """Set/clear the trusted bit in the stub.

    This bit indicates that the app calling the stub is trusted. A
    trusted app can write to datastores of other apps.

    Args:
      trusted: boolean.
    """
    self.__trusted = trusted

  def __ValidateAppId(self, app_id):
    """Verify that this is the stub for app_id.

    Args:
      app_id: An application ID.

    Raises:
      datastore_errors.BadRequestError: if this is not the stub for app_id.
    """
    assert app_id
    if not self.__trusted and app_id != self.project_id:
      raise datastore_errors.BadRequestError(
          'app %s cannot access app %s\'s data' % (self.project_id, app_id))

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
          'each key path element should have id or name but not both: %r' % key)

  def _AppIdNamespaceKindForKey(self, key):
    """ Get (app, kind) tuple from given key.

    The (app, kind) tuple is used as an index into several internal
    dictionaries, e.g. __entities.

    Args:
      key: entity_pb.Reference

    Returns:
      Tuple (app, kind), both are unicode strings.
    """
    last_path = key.path().element_list()[-1]
    return (datastore_types.EncodeAppIdNamespace(key.app(), key.name_space()),
        last_path.type())

  READ_PB_EXCEPTIONS = (ProtocolBuffer.ProtocolBufferDecodeError, LookupError,
                        TypeError, ValueError)
  READ_ERROR_MSG = ('Data in %s is corrupt or a different version. '
                    'Try running with the --clear_datastore flag.\n%r')
  READ_PY250_MSG = ('Are you using FloatProperty and/or GeoPtProperty? '
                    'Unfortunately loading float values from the datastore '
                    'file does not work with Python 2.5.0. '
                    'Please upgrade to a newer Python 2.5 release or use '
                    'the --clear_datastore flag.\n')

  def Read(self):
    """ Does Nothing    """
    return

  def Write(self):
    """ Does Nothing   """
    return 

  def Flush(self):
    """ Does Nothing  """
    return

  def MakeSyncCall(self, service, call, request, response, request_id=None):
    """ The main RPC entry point. service must be 'datastore_v3'.
    """
    self.assertPbIsInitialized(request)
    super(DatastoreDistributed, self).MakeSyncCall(service,
                                                call,
                                                request,
                                                response,
                                                request_id)
    self.assertPbIsInitialized(response)

  def assertPbIsInitialized(self, pb):
    """Raises an exception if the given PB is not initialized and valid."""
    explanation = []
    assert pb.IsInitialized(explanation), explanation
    pb.Encode()

  def QueryHistory(self):
    """Returns a dict that maps Query PBs to times they've been run."""
    return []

  def _maybeSetDefaultAuthDomain(self):
    """ Sets default auth domain if not set. """
    auth_domain = os.environ.get("AUTH_DOMAIN")
    if not auth_domain:
      os.environ['AUTH_DOMAIN'] = "appscale.com"

  def _request_with_pool(self, api_request, tag, retries=2):
    """AppScale: Make datastore request with pool to reduce connections. """
    payload = api_request.Encode()
    headers = {'Content-Length': len(payload),
               'ProtocolBufferType': 'Request',
               'AppData': tag,
               'Module': self._service_id,
               'Version': self._version_id}
    try:
      http_response = self._ds_pool.request('POST', '/', body=payload,
                                            headers=headers)
    except MaxRetryError:
      if retries == 0:
        raise

      logging.exception('Failed to make datastore call')
      self._ds_pool = HTTPConnectionPool(get_random_lb_host(), PROXY_PORT,
                                         maxsize=8)
      backoff_ms = 500 * 3 ** (2 - retries)  # 0.5s, 1.5s, 4.5s
      time.sleep(float(backoff_ms) / 1000)
      return self._request_with_pool(payload, headers, retries - 1)

    if http_response.status != 200:
      raise apiproxy_errors.ApplicationError(
        datastore_pb.Error.INTERNAL_ERROR, 'Unhandled datastore error')

    return remote_api_pb.Response(http_response.data)

  def _request_from_sandbox(self, api_request, tag):
    """ AppScale: Make datastore request within sandbox constraints. """
    api_response = remote_api_pb.Response()
    try:
      api_request.sendCommand(self.__datastore_location, tag, api_response)
    except ProtocolBuffer.ProtocolBufferReturnError:
      # Since this is not within the context of the API server, raise a
      # runtime exception.
      raise datastore_errors.InternalError('Unhandled datastore error')

    return api_response

  def _RemoteSend(self, request, response, method, request_id=None):
    """Sends a request remotely to the datstore server. """
    tag = self.project_id
    self._maybeSetDefaultAuthDomain() 
    user = users.GetCurrentUser()
    if user != None:
      tag += ":" + user.email()
      tag += ":" + user.nickname()
      tag += ":" + user.auth_domain()
    api_request = remote_api_pb.Request()
    api_request.set_method(method)
    api_request.set_service_name("datastore_v3")
    api_request.set_request(request.Encode())
    if request_id is not None:
      api_request.set_request_id(request_id)

    if POOL_CONNECTIONS:
      api_response = self._request_with_pool(api_request, tag)
    else:
      api_response = self._request_from_sandbox(api_request, tag)

    if api_response.has_application_error():
      error_pb = api_response.application_error()
      logging.error(error_pb.detail())
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())

    if api_response.has_exception():
      raise api_response.exception()

    response.ParseFromString(api_response.response())

  def _Dynamic_Put(self, put_request, put_response, request_id=None):
    """Send a put request to the datastore server. """
    put_request.set_trusted(self.__trusted)
    self._RemoteSend(put_request, put_response, "Put", request_id)
    return put_response 

  def _Dynamic_Get(self, get_request, get_response, request_id=None):
    """Send a get request to the datastore server. """
    self._RemoteSend(get_request, get_response, "Get", request_id)
    return get_response


  def _Dynamic_Delete(self, delete_request, delete_response, request_id=None):
    """Send a delete request to the datastore server. 
  
    Args:
      delete_request: datastore_pb.DeleteRequest.
      delete_response: datastore_pb.DeleteResponse.
      request_id: A string specifying the request ID.
    Returns:
      A datastore_pb.DeleteResponse from the AppScale datastore server.
    """
    delete_request.set_trusted(self.__trusted)
    self._RemoteSend(delete_request, delete_response, "Delete", request_id)
    return delete_response

  def _Dynamic_RunQuery(self, query, query_result, request_id=None):
    """Send a query request to the datastore server. """
    if query.has_transaction():
      if not query.has_ancestor():
        raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Only ancestor queries are allowed inside transactions.')
    (filters, orders) = datastore_index.Normalize(query.filter_list(),
                                                  query.order_list(), [])
    
    old_datastore_stub_util.FillUsersInQuery(filters)

    if not query.has_app():
      query.set_app(self.project_id)
    self.__ValidateAppId(query.app())

    self._RemoteSend(query, query_result, "RunQuery", request_id)
    results = query_result.result_list()
    for result in results:
      old_datastore_stub_util.PrepareSpecialPropertiesForLoad(result)

    last_cursor = None
    if query_result.has_compiled_cursor():
      last_cursor = query_result.compiled_cursor()

    if query_result.more_results():
      new_cursor = InternalCursor(query, last_cursor, len(results))
      cursor_id = self.__getCursorID()
      cursor = query_result.mutable_cursor()
      cursor.set_app(self.project_id)
      cursor.set_cursor(cursor_id)
      self.__queries[cursor_id] = new_cursor

    if query.compile():
      compiled_query = query_result.mutable_compiled_query()
      compiled_query.set_keys_only(query.keys_only())
      compiled_query.mutable_primaryscan().set_index_name(query.Encode())

  def _Dynamic_Next(self, next_request, query_result, request_id=None):
    """Get the next set of entities from a previously run query. """
    self.__ValidateAppId(next_request.cursor().app())

    cursor_handle = next_request.cursor().cursor()
    if cursor_handle not in self.__queries:
      raise apiproxy_errors.ApplicationError(
            datastore_pb.Error.BAD_REQUEST, 
            'Cursor %d not found' % cursor_handle)
 
    internal_cursor = self.__queries.get(cursor_handle)
    last_cursor = internal_cursor.get_last_cursor()
    query = internal_cursor.get_query()

    if not last_cursor:
      query_result.set_more_results(False)
      if next_request.compile():
        compiled_query = query_result.mutable_compiled_query()
        compiled_query.set_keys_only(query.keys_only())
        compiled_query.mutable_primaryscan().set_index_name(query.Encode())
      del self.__queries[cursor_handle]
      return

    if query.has_limit() and internal_cursor.get_offset() >= query.limit():
      query_result.set_more_results(False)
      query_result.mutable_compiled_cursor().CopyFrom(last_cursor)
      if next_request.compile():
        compiled_query = query_result.mutable_compiled_query()
        compiled_query.set_keys_only(query.keys_only())
        compiled_query.mutable_primaryscan().set_index_name(query.Encode())
      del self.__queries[cursor_handle]
      return

    if query.has_limit():
      max_remaining_results = query.limit() - internal_cursor.get_offset()
    else:
      max_remaining_results = sys.maxint

    if next_request.has_count():
      count = min(next_request.count(), max_remaining_results)
    else:
      count = min(_BATCH_SIZE, max_remaining_results)

    query.set_count(count)
    if next_request.has_offset():
      query.set_offset(next_request.offset())
    if next_request.has_compile():
      query.set_compile(next_request.compile())

    # Remove any offset since first RunQuery deals with it.
    query.clear_offset()

    query.mutable_compiled_cursor().CopyFrom(last_cursor)

    self._RemoteSend(query, query_result, "RunQuery", request_id)
    results = query_result.result_list()
    for result in results:
      old_datastore_stub_util.PrepareSpecialPropertiesForLoad(result)

    if len(results) > 0:
      if query_result.has_compiled_cursor():
        last_cursor = query_result.compiled_cursor()
        internal_cursor.set_last_cursor(last_cursor)
      offset = internal_cursor.get_offset()
      internal_cursor.set_offset(offset + len(results))
      query_result.set_more_results(internal_cursor.get_offset() < \
        internal_cursor.get_count())
    else:
      query_result.mutable_compiled_cursor().CopyFrom(last_cursor)
      query_result.set_more_results(False)
  
    if query.compile():
      compiled_query = query_result.mutable_compiled_query()
      compiled_query.set_keys_only(query.keys_only())
      compiled_query.mutable_primaryscan().set_index_name(query.Encode())
   
    if not query_result.more_results():
      del self.__queries[cursor_handle]
    else:
      cursor = query_result.mutable_cursor()                                    
      cursor.set_app(self.project_id)
      cursor.set_cursor(cursor_handle)

  def _Dynamic_Count(self, query, integer64proto, request_id=None):
    """Get the number of entities for a query. """
    query_result = datastore_pb.QueryResult()
    self._Dynamic_RunQuery(query, query_result, request_id)
    count = query_result.result_size()
    integer64proto.set_value(count)

  def _Dynamic_BeginTransaction(self, request, transaction, request_id=None):
    """Send a begin transaction request from the datastore server. """
    request.set_app(self.project_id)
    self._RemoteSend(request, transaction, "BeginTransaction", request_id)
    self.__tx_actions[transaction.handle()] = []
    return transaction

  def _Dynamic_AddActions(self, request, response, request_id=None):
    """Associates the creation of one or more tasks with a transaction.

    Args:
      request: A taskqueue_service_pb.TaskQueueBulkAddRequest containing the
          tasks that should be created when the transaction is comitted.
      response: A taskqueue_service_pb.TaskQueueBulkAddResponse.
      request_id: A string specifying the request ID.
    """
    # These are not used, but they are required for the method signature.
    del response, request_id

    transaction = request.add_request_list()[0].transaction()
    txn_actions = self.__tx_actions[transaction.handle()]
    if ((len(txn_actions) + request.add_request_size()) >
        _MAX_ACTIONS_PER_TXN):
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Too many messages, maximum allowed %s' % _MAX_ACTIONS_PER_TXN)

    new_actions = []
    for add_request in request.add_request_list():
      clone = taskqueue_service_pb.TaskQueueAddRequest()
      clone.CopyFrom(add_request)
      clone.clear_transaction()
      new_actions.append(clone)

    txn_actions.extend(new_actions)


  def _Dynamic_Commit(self, transaction, transaction_response,
                      request_id=None):
    """ Send a transaction request to commit a transaction to the 
        datastore server. """
    transaction.set_app(self.project_id)

    self._RemoteSend(transaction, transaction_response, "Commit", request_id)

    response = taskqueue_service_pb.TaskQueueAddResponse()
    try:
      for action in self.__tx_actions[transaction.handle()]:
        try:
          apiproxy_stub_map.MakeSyncCall(
              'taskqueue', 'Add', action, response)
        except apiproxy_errors.ApplicationError, e:
          logging.warning('Transactional task %s has been dropped, %s',
                          action, e)

    finally:
      try:
        del self.__tx_actions[transaction.handle()]
      except KeyError:
        pass
   
  def _Dynamic_Rollback(self, transaction, transaction_response,
                        request_id=None):
    """ Send a rollback request to the datastore server. """
    transaction.set_app(self.project_id)

    try:
      del self.__tx_actions[transaction.handle()]
    except KeyError:
      pass

    self._RemoteSend(transaction, transaction_response, "Rollback", request_id)
 
    return transaction_response

  def _Dynamic_GetSchema(self, req, schema, request_id=None):
    """ Get the schema of a particular kind of entity. """
    # This is not used, but it is required for the method signature.
    del request_id

    app_str = req.app()
    self.__ValidateAppId(app_str)
    schema.set_more_results(False)

  def _Dynamic_AllocateIds(self, request, response, request_id=None):
    """Send a request for allocation of IDs to the datastore server. """
    self._RemoteSend(request, response, "AllocateIds", request_id)
    return response

  def _Dynamic_CreateIndex(self, index, id_response, request_id=None):
    """ Create a new index. Currently stubbed out."""
    if index.id() != 0:
      raise apiproxy_errors.ApplicationError(datastore_pb.Error.BAD_REQUEST,
                                             'New index id must be 0.')
    self._RemoteSend(index, id_response, "CreateIndex", request_id)
    return id_response

  def _Dynamic_GetIndices(self, app_str, composite_indices, request_id=None):
    """ Gets the indices of the current app.

    Args:
      app_str: A api_base_pb.StringProto, the application identifier.
      composite_indices: datastore_pb.CompositeIndices protocol buffer.
      request_id: A string specifying the request ID.

    Returns:
      A datastore_pb.CompositesIndices containing the current indexes 
      used by this application.
    """
    self._RemoteSend(app_str, composite_indices, "GetIndices", request_id)
    return composite_indices

  def _Dynamic_UpdateIndex(self, index, void, request_id=None):
    """ Updates the indices of the current app. Tells the AppScale datastore
      server to build out the new index with existing data.

    Args:
      index: A datastore_pb.CompositeIndex, the composite index to update.
      void: A entity_pb.VoidProto.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(index, void, "UpdateIndex", request_id)
    return
    
  def _Dynamic_DeleteIndex(self, index, void, request_id=None):
    """ Deletes an index of the current app.

    Args:
      index: A entity_pb.CompositeIndex, the composite index to delete.
      void: A entity_pb.VoidProto.
      request_id: A string specifying the request ID.
    Returns:
      A entity_pb.VoidProto. 
    """
    self._RemoteSend(index, void, "DeleteIndex", request_id)
    return void

  def _SetupIndexes(self, _open=open):
    """ In AppScale, this initialization is not needed.
   
    Args:
      _open: Function used to open a file.
    """
    pass
