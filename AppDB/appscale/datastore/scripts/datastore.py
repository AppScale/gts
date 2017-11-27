# See LICENSE file
#
"""
This web service interfaces with the datastore. It takes protocol buffer
requests from AppServers and responds according to the type of request its
given (Put, Get, Delete, Query, etc).
"""
import argparse
import json
import logging
import os
import sys
import threading
import time
import tornado.httpserver
import tornado.web

from appscale.admin.utils import retry_data_watch_coroutine
from appscale.common import appscale_info
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from kazoo.client import KazooState
from kazoo.exceptions import NodeExistsError
from tornado import gen
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.options import options
from .. import dbconstants
from ..appscale_datastore_batch import DatastoreFactory
from ..datastore_distributed import DatastoreDistributed
from ..utils import (clean_app_id,
                     logger,
                     UnprocessedQueryResult)
from ..zkappscale import zktransaction

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import api_base_pb
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_v4_pb
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb

# Global for accessing the datastore. An instance of DatastoreDistributed.
datastore_access = None

# A record of active datastore servers.
datastore_servers = set()

# The ZooKeeper path where this server registers its availability.
server_node = None

# ZooKeeper global variable for locking
zookeeper = None

# Determines whether or not to allow datastore writes. Note: After enabling,
# datastore processes must be restarted and the groomer must be stopped.
READ_ONLY = False

# Global stats.
STATS = {}

# The ZooKeeper path where a list of active datastore servers is stored.
DATASTORE_SERVERS_NODE = '/appscale/datastore/servers'


class ClearHandler(tornado.web.RequestHandler):
  """ Defines what to do when the webserver receives a /clear HTTP request. """
  def set_default_headers(self):
    """ Instructs clients to close the connection after each response. """
    self.set_header('Connection', 'close')

  @tornado.web.asynchronous
  def post(self):
    """ Handles POST requests for clearing datastore server stats. """
    global STATS
    STATS = {}
    self.write({"message": "Statistics for this server cleared."})
    self.finish()


class ReadOnlyHandler(tornado.web.RequestHandler):
  """ Handles requests to check or set read-only mode. """
  def set_default_headers(self):
    """ Instructs clients to close the connection after each response. """
    self.set_header('Connection', 'close')

  @tornado.web.asynchronous
  def post(self):
    """ Handle requests to turn read-only mode on or off. """
    global READ_ONLY

    payload = self.request.body
    data = json.loads(payload)
    if 'readOnly' not in data:
      self.set_status(dbconstants.HTTP_BAD_REQUEST)

    if data['readOnly']:
      READ_ONLY = True
      message = 'Write operations now disabled.'
    else:
      READ_ONLY = False
      message = 'Write operations now enabled.'

    logger.info(message)
    self.write({'message': message})
    self.finish()


class ReserveKeysHandler(tornado.web.RequestHandler):
  """ Handles v4 AllocateIds requests from other servers. """
  def post(self):
    """ Prevents the provided IDs from being re-allocated. """
    project_id = self.request.headers['appdata']
    request = datastore_v4_pb.AllocateIdsRequest(self.request.body)
    ids = [key.path_element_list()[-1].id() for key in request.reserve_list()]
    datastore_access.reserve_ids(project_id, ids)


class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """
  def set_default_headers(self):
    """ Instructs clients to close the connection after each response. """
    self.set_header('Connection', 'close')

  def unknown_request(self, app_id, http_request_data, pb_type):
    """ Function which handles unknown protocol buffers.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer
    Raises:
      Raises exception.
    """ 
    raise NotImplementedError("Unknown request of operation {0}" \
      .format(pb_type))
  
  @gen.coroutine
  def post(self):
    """ Function which handles POST requests. Data of the request is
        the request from the AppServer in an encoded protocol buffer
        format.
    """
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data = app_data.split(':')

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
      raise gen.Return()

    # If the application identifier has the HRD string prepened, remove it.
    app_id = clean_app_id(app_id)

    if pb_type == "Request":
      yield self.remote_request(app_id, http_request_data,
                                service_id=request.headers.get('Module'),
                                version_id=request.headers.get('Version'))
    else:
      self.unknown_request(app_id, http_request_data, pb_type)

  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
        up in json.
    """
    self.write(json.dumps(STATS))
    self.finish() 

  @gen.coroutine
  def remote_request(self, app_id, http_request_data, service_id, version_id):
    """ Receives a remote request to which it should give the correct 
        response. The http_request_data holds an encoded protocol buffer
        of a certain type. Each type has a particular response type. 
    
    Args:
      app_id: The application ID that is sending this request.
      http_request_data: Encoded protocol buffer.
      service_id: A string specifying the client's service ID.
      version_id: A string specifying the client's version ID.
    """
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
    start = time.time()

    request_log = method
    if apirequest.has_request_id():
      request_log += ': {}'.format(apirequest.request_id())
    logger.debug(request_log)

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
      response, errcode, errdetail = self.run_query(http_request_data)
    elif method == "BeginTransaction":
      response, errcode, errdetail = self.begin_transaction_request(
                                                      app_id, http_request_data)
    elif method == "Commit":
      response, errcode, errdetail = self.commit_transaction_request(
                                                      app_id,
                                                      http_request_data)
    elif method == "Rollback":
      response, errcode, errdetail = self.rollback_transaction_request( 
                                                        app_id,
                                                        http_request_data)
    elif method == "AllocateIds":
      response, errcode, errdetail = self.allocate_ids_request(
                                                        app_id,
                                                        http_request_data)
    elif method == "CreateIndex":
      response, errcode, errdetail = self.create_index_request(app_id,
                                                        http_request_data)
    elif method == "GetIndices":
      response, errcode, errdetail = self.get_indices_request(app_id)
    elif method == "UpdateIndex":
      response, errcode, errdetail = self.update_index_request(app_id,
        http_request_data)
    elif method == "DeleteIndex":
      response, errcode, errdetail = self.delete_index_request(app_id, 
                                                       http_request_data)
    elif method == 'AddActions':
      response, errcode, errdetail = self.add_actions_request(
        app_id, http_request_data, service_id, version_id)
    elif method == 'datastore_v4.AllocateIds':
      response, errcode, errdetail = yield self.v4_allocate_ids_request(
        app_id, http_request_data)
    else:
      errcode = datastore_pb.Error.BAD_REQUEST 
      errdetail = "Unknown datastore message" 

    time_taken = time.time() - start
    if method in STATS:
      if errcode in STATS[method]:
        prev_req, pre_time = STATS[method][errcode]
        STATS[method][errcode] = prev_req + 1, pre_time + time_taken
      else:
        STATS[method][errcode] = (1, time_taken)
    else:
      STATS[method] = {}
      STATS[method][errcode] = (1, time_taken)

    apiresponse.set_response(response)
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    self.write(apiresponse.Encode())

  def begin_transaction_request(self, app_id, http_request_data):
    """ Handles the intial request to start a transaction. Replies with 
        a unique identifier to handle this transaction in future requests.
  
    Args:
      app_id: The application ID requesting the transaction.
      http_request_data: The encoded request.
    Returns:
      An encoded transaction protocol buffer with a unique handler.
    """
    global datastore_access
    begin_transaction_req_pb = datastore_pb.BeginTransactionRequest(
      http_request_data)
    multiple_eg = False
    if begin_transaction_req_pb.has_allow_multiple_eg():
      multiple_eg = bool(begin_transaction_req_pb.allow_multiple_eg())

    handle = None
    transaction_pb = datastore_pb.Transaction()

    if READ_ONLY:
      logger.warning('Unable to begin transaction in read-only mode: {}'.
        format(begin_transaction_req_pb))
      return (transaction_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      handle = datastore_access.setup_transaction(app_id, multiple_eg)
    except (zktransaction.ZKInternalException,
            dbconstants.AppScaleDBConnectionError) as error:
      logger.exception('Unable to begin transaction')
      return (transaction_pb.Encode(), datastore_pb.Error.INTERNAL_ERROR,
              str(error))

    transaction_pb.set_app(app_id)
    transaction_pb.set_handle(handle)
    return (transaction_pb.Encode(), 0, "")

  def commit_transaction_request(self, app_id, http_request_data):
    """ Handles the commit phase of a transaction.

    Args:
      app_id: The application ID requesting the transaction commit.
      http_request_data: The encoded request of datastore_pb.Transaction.
    Returns:
      An encoded protocol buffer commit response.
    """
    global datastore_access

    if READ_ONLY:
      commitres_pb = datastore_pb.CommitResponse()
      transaction_pb = datastore_pb.Transaction(http_request_data)
      logger.warning('Unable to commit in read-only mode: {}'.
        format(transaction_pb))
      return (commitres_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    return datastore_access.commit_transaction(app_id, http_request_data)

  def rollback_transaction_request(self, app_id, http_request_data):
    """ Handles the rollback phase of a transaction.

    Args:
      app_id: The application ID requesting the rollback.
      http_request_data: The encoded request.
    Returns:
      An encoded protocol buffer void response.
    """
    global datastore_access
    response = api_base_pb.VoidProto()

    if READ_ONLY:
      logger.warning('Unable to rollback in read-only mode: {}'.
        format(http_request_data))
      return (response.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      return datastore_access.rollback_transaction(app_id, http_request_data)
    except zktransaction.ZKInternalException:
      logger.exception('ZKInternalException during {} for {}'.
        format(http_request_data, app_id))
      return (response.Encode(), datastore_pb.Error.INTERNAL_ERROR,
              "Internal error with ZooKeeper connection.")
    except Exception:
      logger.exception('Unable to rollback transaction')
      return(response.Encode(),
             datastore_pb.Error.INTERNAL_ERROR,
             "Unable to rollback for this transaction")

  def run_query(self, http_request_data):
    """ High level function for running queries.

    Args:
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      Returns an encoded query response.
    """
    global datastore_access
    query = datastore_pb.Query(http_request_data)
    clone_qr_pb = UnprocessedQueryResult()
    try:
      datastore_access._dynamic_run_query(query, clone_qr_pb)
    except zktransaction.ZKBadRequest, zkie:
      logger.exception('Illegal arguments in transaction during {}'.
        format(query))
      return (clone_qr_pb.Encode(),
              datastore_pb.Error.BAD_REQUEST, 
              "Illegal arguments for transaction. {0}".format(str(zkie)))
    except zktransaction.ZKInternalException:
      logger.exception('ZKInternalException during {}'.format(query))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except zktransaction.ZKTransactionException:
      logger.exception('Concurrent transaction during {}'.format(query))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during query')
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(),
             datastore_pb.Error.INTERNAL_ERROR,
             "Datastore connection error on run_query request.")
    return clone_qr_pb.Encode(), 0, ""

  def create_index_request(self, app_id, http_request_data):
    """ High level function for creating composite indexes.

    Args:
       app_id: Name of the application.
       http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
       Returns an encoded response.
    """
    global datastore_access
    request = entity_pb.CompositeIndex(http_request_data)
    response = api_base_pb.Integer64Proto()

    if READ_ONLY:
      logger.warning('Unable to create in read-only mode: {}'.
        format(request))
      return (response.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      index_id = datastore_access.create_composite_index(app_id, request)
      response.set_value(index_id)
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during index creation')
      response.set_value(0)
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on create index request.")
    return response.Encode(), 0, ""

  def update_index_request(self, app_id, http_request_data):
    """ High level function for updating a composite index.

    Args:
      app_id: A string containing the application ID.
      http_request_data: A string containing the protocol buffer request
        from the AppServer.
    Returns:
       A tuple containing an encoded response, error code, and error details.
    """
    global datastore_access
    index = entity_pb.CompositeIndex(http_request_data)
    response = api_base_pb.VoidProto()

    if READ_ONLY:
      logger.warning('Unable to update in read-only mode: {}'.
        format(index))
      return (response.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    state = index.state()
    if state not in [index.READ_WRITE, index.WRITE_ONLY]:
      state_name = entity_pb.CompositeIndex.State_Name(state)
      error_message = 'Unable to update index because state is {}. '\
        'Index: {}'.format(state_name, index)
      logger.error(error_message)
      return response.Encode(), datastore_pb.Error.PERMISSION_DENIED,\
        error_message
    else:
      # Updating index asynchronously so we can return a response quickly.
      threading.Thread(target=datastore_access.update_composite_index,
        args=(app_id, index)).start()

    return response.Encode(), 0, ""

  def delete_index_request(self, app_id, http_request_data):
    """ Deletes a composite index for a given application.
  
    Args:
      app_id: Name of the application.
      http_request_data: A serialized CompositeIndices item
    Returns:
      A Tuple of an encoded entity_pb.VoidProto, error code, and 
      error explanation.
    """
    global datastore_access
    request = entity_pb.CompositeIndex(http_request_data)
    response = api_base_pb.VoidProto()

    if READ_ONLY:
      logger.warning('Unable to delete in read-only mode: {}'.
        format(request))
      return (response.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try: 
      datastore_access.delete_composite_index_metadata(app_id, request)
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during index deletion')
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete index request.")
    return response.Encode(), 0, ""
    
  def get_indices_request(self, app_id):
    """ Gets the indices of the given application.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
      A Tuple of an encoded response, error code, and error explanation.
    """
    global datastore_access
    response = datastore_pb.CompositeIndices()
    try:
      indices = datastore_access.datastore_batch.get_indices(app_id)
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error while fetching indices for '
        '{}'.format(app_id))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get indices request.")
    for index in indices:
      new_index = response.add_index()
      new_index.ParseFromString(index)
    return response.Encode(), 0, ""

  def allocate_ids_request(self, app_id, http_request_data):
    """ High level function for getting unique identifiers for entities.

    Args:
       app_id: Name of the application.
       http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
       Returns an encoded response.
    Raises:
       NotImplementedError: when requesting a max id.
    """
    request = datastore_pb.AllocateIdsRequest(http_request_data)
    response = datastore_pb.AllocateIdsResponse()

    if request.has_max() and request.has_size():
      return (response.Encode(), datastore_pb.Error.BAD_REQUEST,
              'Both size and max cannot be set.')
    if not (request.has_max() or request.has_size()):
      return (response.Encode(), datastore_pb.Error.BAD_REQUEST,
              'Either size or max must be set.')

    if request.has_size():
      try:
        start, end = datastore_access.allocate_size(app_id, request.size())
      except dbconstants.AppScaleBadArg as error:
        return response.Encode(), datastore_pb.Error.BAD_REQUEST, str(error)
      except dbconstants.AppScaleDBConnectionError as error:
        return response.Encode(), datastore_pb.Error.INTERNAL_ERROR, str(error)
    else:
      try:
        start, end = datastore_access.allocate_max(app_id, request.max())
      except dbconstants.AppScaleBadArg as error:
        return response.Encode(), datastore_pb.Error.BAD_REQUEST, str(error)
      except dbconstants.AppScaleDBConnectionError as error:
        return response.Encode(), datastore_pb.Error.INTERNAL_ERROR, str(error)

    response.set_start(start)
    response.set_end(end)
    return response.Encode(), 0, ""

  @staticmethod
  @gen.coroutine
  def v4_allocate_ids_request(app_id, http_request_data):
    """ Reserves entity IDs so that they will not be re-allocated.

    Args:
      app_id: Name of the application.
      http_request_data: The protocol buffer request from the AppServer.
    Returns:
       Returns an encoded response.
    """
    request = datastore_v4_pb.AllocateIdsRequest(http_request_data)
    response = datastore_v4_pb.AllocateIdsResponse()

    if not request.reserve_list():
      raise gen.Return((response.Encode(), datastore_v4_pb.Error.BAD_REQUEST,
                        'Request must include reserve list'))

    ids = [key.path_element_list()[-1].id() for key in request.reserve_list()]
    datastore_access.reserve_ids(app_id, ids)

    # Forward request to other datastore servers in order to adjust any blocks
    # they've already allocated.
    client = AsyncHTTPClient()
    headers = {'appdata': app_id}

    futures = []
    for server in datastore_servers:
      ip, port = server.split(':')
      port = int(port)
      if ip == options.private_ip and port == options.port:
        continue

      url = 'http://{}:{}/reserve-keys'.format(ip, port)
      future = client.fetch(url, method='POST', headers=headers,
                            body=http_request_data)
      futures.append(future)

    for future in futures:
      yield future

    raise gen.Return((response.Encode(), 0, ''))

  def put_request(self, app_id, http_request_data):
    """ High level function for doing puts.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      Returns an encoded put response.
    """ 
    global datastore_access

    putreq_pb = datastore_pb.PutRequest(http_request_data)
    putresp_pb = datastore_pb.PutResponse()

    if READ_ONLY:
      logger.warning('Unable to put in read-only mode: {}'.
        format(putreq_pb))
      return (putresp_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      datastore_access.dynamic_put(app_id, putreq_pb, putresp_pb)
      return (putresp_pb.Encode(), 0, "")
    except zktransaction.ZKBadRequest as zkie:
      logger.exception('Illegal argument during {}'.format(putreq_pb))
      return (putresp_pb.Encode(),
            datastore_pb.Error.BAD_REQUEST, 
            "Illegal arguments for transaction. {0}".format(str(zkie)))
    except zktransaction.ZKInternalException as error:
      logger.exception('ZKInternalException during put')
      return (putresp_pb.Encode(), datastore_pb.Error.INTERNAL_ERROR,
              str(error))
    except zktransaction.ZKTransactionException:
      logger.exception('Concurrent transaction during {}'.
        format(putreq_pb))
      return (putresp_pb.Encode(),
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during put')
      return (putresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on put.")

    
  def get_request(self, app_id, http_request_data):
    """ High level function for doing gets.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      An encoded get response.
    """ 
    global datastore_access
    getreq_pb = datastore_pb.GetRequest(http_request_data)
    getresp_pb = datastore_pb.GetResponse()
    try:
      datastore_access.dynamic_get(app_id, getreq_pb, getresp_pb)
    except zktransaction.ZKBadRequest as zkie:
      logger.exception('Illegal argument during {}'.format(getreq_pb))
      return (getresp_pb.Encode(),
              datastore_pb.Error.BAD_REQUEST, 
              "Illegal arguments for transaction. {0}".format(str(zkie)))
    except zktransaction.ZKInternalException:
      logger.exception('ZKInternalException during {}'.format(getreq_pb))
      return (getresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except zktransaction.ZKTransactionException:
      logger.exception('Concurrent transaction during {}'.
        format(getreq_pb))
      return (getresp_pb.Encode(),
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on get.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during get')
      return (getresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get.")

    return getresp_pb.Encode(), 0, ""

  def delete_request(self, app_id, http_request_data):
    """ High level function for doing deletes.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      An encoded delete response.
    """ 
    global datastore_access

    delreq_pb = datastore_pb.DeleteRequest( http_request_data )
    delresp_pb = api_base_pb.VoidProto() 

    if READ_ONLY:
      logger.warning('Unable to delete in read-only mode: {}'.
        format(delreq_pb))
      return (delresp_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      datastore_access.dynamic_delete(app_id, delreq_pb)
      return (delresp_pb.Encode(), 0, "")
    except zktransaction.ZKBadRequest as zkie:
      logger.exception('Illegal argument during {}'.format(delreq_pb))
      return (delresp_pb.Encode(),
              datastore_pb.Error.BAD_REQUEST, 
              "Illegal arguments for transaction. {0}".format(str(zkie)))
    except zktransaction.ZKInternalException:
      logger.exception('ZKInternalException during {}'.format(delreq_pb))
      return (delresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except zktransaction.ZKTransactionException:
      logger.exception('Concurrent transaction during {}'.
        format(delreq_pb))
      return (delresp_pb.Encode(),
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on delete.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during delete')
      return (delresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete.")

  def add_actions_request(self, app_id, http_request_data, service_id,
                          version_id):
    """ High level function for adding transactional tasks.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
      service_id: A string specifying the client's service ID.
      version_id: A string specifying the client's version ID.
    Returns:
      An encoded AddActions response.
    """
    global datastore_access

    req_pb = taskqueue_service_pb.TaskQueueBulkAddRequest(http_request_data)
    resp_pb = taskqueue_service_pb.TaskQueueBulkAddResponse()

    if service_id is None:
      return (resp_pb.Encode(), datastore_pb.Error.BAD_REQUEST,
              'Module header must be defined')

    if version_id is None:
      return (resp_pb.Encode(), datastore_pb.Error.BAD_REQUEST,
              'Version header must be defined')

    if READ_ONLY:
      logger.warning('Unable to add transactional tasks in read-only mode')
      return (resp_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      datastore_access.dynamic_add_actions(app_id, req_pb, service_id,
                                           version_id)
      return resp_pb.Encode(), 0, ""
    except dbconstants.ExcessiveTasks as error:
      return (resp_pb.Encode(), datastore_pb.Error.BAD_REQUEST, str(error))
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error')
      return (resp_pb.Encode(), datastore_pb.Error.INTERNAL_ERROR,
              'Datastore connection error when adding transaction tasks.')


def create_server_node():
  """ Creates a server registration entry in ZooKeeper. """
  try:
    zookeeper.handle.create(server_node, ephemeral=True)
  except NodeExistsError:
    # If the server gets restarted, the old node may exist for a short time.
    zookeeper.handle.delete(server_node)
    zookeeper.handle.create(server_node, ephemeral=True)

  logger.info('Datastore registered at {}'.format(server_node))


def zk_state_listener(state):
  """ Handles changes to ZooKeeper connection state.

  Args:
    state: A string specifying the new ZooKeeper connection state.
  """
  if state == KazooState.CONNECTED:
    persistent_create_server_node = retry_data_watch_coroutine(
      server_node, create_server_node)
    IOLoop.instance().add_callback(persistent_create_server_node)


def update_servers(new_servers):
  """ Updates the record of active datastore servers.

  Args:
    new_servers: A list of strings identifying server locations.
  """
  to_remove = [server for server in datastore_servers
               if server not in new_servers]
  for old_server in to_remove:
    datastore_servers.remove(old_server)

  for new_server in new_servers:
    if new_server not in datastore_servers:
      datastore_servers.add(new_server)


def update_servers_watch(new_servers):
  """ Updates the record of active datastore servers.

  Args:
    new_servers: A list of strings identifying server locations.
  """
  main_io_loop = IOLoop.instance()
  main_io_loop.add_callback(update_servers, new_servers)


pb_application = tornado.web.Application([
  ('/clear', ClearHandler),
  ('/read-only', ReadOnlyHandler),
  ('/reserve-keys', ReserveKeysHandler),
  (r'/*', MainHandler),
])


def main():
  """ Starts a web service for handing datastore requests. """

  global datastore_access
  global server_node
  global zookeeper
  zookeeper_locations = appscale_info.get_zk_locations_string()

  parser = argparse.ArgumentParser()
  parser.add_argument('-t', '--type', choices=dbconstants.VALID_DATASTORES,
                      default=dbconstants.VALID_DATASTORES[0],
                      help='Database type')
  parser.add_argument('-p', '--port', type=int,
                      default=dbconstants.DEFAULT_PORT,
                      help='Datastore server port')
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  options.define('private_ip', appscale_info.get_private_ip())
  options.define('port', args.port)

  server_node = '{}/{}:{}'.format(DATASTORE_SERVERS_NODE, options.private_ip,
                                  options.port)

  datastore_batch = DatastoreFactory.getDatastore(
    args.type, log_level=logger.getEffectiveLevel())
  zookeeper = zktransaction.ZKTransaction(
    host=zookeeper_locations, start_gc=True, db_access=datastore_batch,
    log_level=logger.getEffectiveLevel())

  zookeeper.handle.add_listener(zk_state_listener)
  zookeeper.handle.ensure_path(DATASTORE_SERVERS_NODE)
  # Since the client was started before adding the listener, make sure the
  # server node gets created.
  zk_state_listener(zookeeper.handle.state)
  zookeeper.handle.ChildrenWatch(DATASTORE_SERVERS_NODE, update_servers_watch)

  datastore_access = DatastoreDistributed(
    datastore_batch, zookeeper=zookeeper, log_level=logger.getEffectiveLevel())

  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(args.port)

  IOLoop.current().start()
