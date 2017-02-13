# See LICENSE file
#
"""
This web service interfaces with the datastore. It takes protocol buffer
requests from AppServers and responds according to the type of request its
given (Put, Get, Delete, Query, etc).
"""
import getopt
import json
import logging
import os
import sys
import threading
import time
import tornado.httpserver
import tornado.ioloop
import tornado.web

from M2Crypto import SSL
from .. import dbconstants
from ..appscale_datastore_batch import DatastoreFactory
from ..datastore_distributed import DatastoreDistributed
from ..utils import (clean_app_id,
                     logger,
                     UnprocessedQueryResult)
from ..unpackaged import APPSCALE_LIB_DIR
from ..unpackaged import APPSCALE_PYTHON_APPSERVER
from ..zkappscale import zktransaction

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import api_base_pb
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb

# Global for accessing the datastore. An instance of DatastoreDistributed.
datastore_access = None

# ZooKeeper global variable for locking
zookeeper = None

# Determines whether or not to allow datastore writes. Note: After enabling,
# datastore processes must be restarted and the groomer must be stopped.
READ_ONLY = False

# Global stats.
STATS = {}


class ClearHandler(tornado.web.RequestHandler):
  """ Defines what to do when the webserver receives a /clear HTTP request. """

  @tornado.web.asynchronous
  def post(self):
    """ Handles POST requests for clearing datastore server stats. """
    global STATS
    STATS = {}
    self.write({"message": "Statistics for this server cleared."})
    self.finish()


class ReadOnlyHandler(tornado.web.RequestHandler):
  """ Handles requests to check or set read-only mode. """
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


class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """

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
  
  @tornado.web.asynchronous
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
      return

    # If the application identifier has the HRD string prepened, remove it.
    app_id = clean_app_id(app_id)

    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)
    self.finish()
  
  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
        up in json.
    """
    self.write(str(STATS))
    self.finish() 

  def remote_request(self, app_id, http_request_data):
    """ Receives a remote request to which it should give the correct 
        response. The http_request_data holds an encoded protocol buffer
        of a certain type. Each type has a particular response type. 
    
    Args:
      app_id: The application ID that is sending this request.
      http_request_data: Encoded protocol buffer.
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
    logger.debug('Request type: {}'.format(method))
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
    except zktransaction.ZKInternalException:
      logger.exception('Unable to begin {}'.format(transaction_pb))
      return (transaction_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")

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
      logger.exception('DB connection error during {}'.format(query))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(),
             datastore_pb.Error.INTERNAL_ERROR,
             "Datastore connection error on run_query request.")
    return (clone_qr_pb.Encode(), 0, "")

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
      logger.exception('DB connection error during {}'.format(request))
      response.set_value(0)
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on create index request.")
    return (response.Encode(), 0, "")

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
      logger.exception('DB connection error during {}'.format(request))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete index request.")
    return (response.Encode(), 0, "")
    
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
    except dbconstants.AppScaleDBConnectionError, dbce:
      logger.exception('DB connection error while fetching indices for '
        '{}'.format(app_id))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get indices request.")
    for index in indices:
      new_index = response.add_index()
      new_index.ParseFromString(index)
    return (response.Encode(), 0, "")

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
    global datastore_access
    request = datastore_pb.AllocateIdsRequest(http_request_data)
    response = datastore_pb.AllocateIdsResponse()

    if READ_ONLY:
      logger.warning('Unable to allocate in read-only mode: {}'.
        format(request))
      return (response.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    max_id = int(request.max())
    size = int(request.size())
    start = end = 0
    try:
      start, end = datastore_access.allocate_ids(app_id, size, max_id=max_id)
    except zktransaction.ZKBadRequest as zkie:
      logger.exception('Unable to allocate IDs for {}'.format(app_id))
      return (response.Encode(),
              datastore_pb.Error.BAD_REQUEST, 
              "Illegal arguments for transaction. {0}".format(str(zkie)))
    except zktransaction.ZKInternalException:
      logger.exception('Unable to allocate IDs for {}'.format(app_id))
      return (response.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except zktransaction.ZKTransactionException:
      logger.exception('Unable to allocate IDs for {}'.format(app_id))
      return (response.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on allocate id request.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error while allocating IDs for {}'.
        format(app_id))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on allocate id request.")


    response.set_start(start)
    response.set_end(end)
    return (response.Encode(), 0, "")

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
    except zktransaction.ZKInternalException:
      logger.exception('ZKInternalException during {}'.format(putreq_pb))
      return (putresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except zktransaction.ZKTransactionException:
      logger.exception('Concurrent transaction during {}'.
        format(putreq_pb))
      return (putresp_pb.Encode(),
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error during {}'.format(putreq_pb))
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
      logger.exception('DB connection error during {}'.format(getreq_pb))
      return (getresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get.")

    return (getresp_pb.Encode(), 0, "")

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
      logger.exception('DB connection error during {}'.format(delreq_pb))
      return (delresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete.")

  def add_actions_request(self, app_id, http_request_data):
    """ High level function for adding transactional tasks.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      An encoded AddActions response.
    """
    global datastore_access

    req_pb = taskqueue_service_pb.TaskQueueBulkAddRequest(http_request_data)
    resp_pb = taskqueue_service_pb.TaskQueueBulkAddResponse()

    if READ_ONLY:
      logger.warning('Unable to add transactional tasks in read-only mode')
      return (resp_pb.Encode(), datastore_pb.Error.CAPABILITY_DISABLED,
        'Datastore is in read-only mode.')

    try:
      datastore_access.dynamic_add_actions(app_id, req_pb)
      return resp_pb.Encode(), 0, ""
    except dbconstants.ExcessiveTasks as error:
      return (resp_pb.Encode(), datastore_pb.Error.BAD_REQUEST, str(error))
    except dbconstants.AppScaleDBConnectionError:
      logger.exception('DB connection error')
      return (resp_pb.Encode(), datastore_pb.Error.INTERNAL_ERROR,
              'Datastore connection error when adding transaction tasks.')


def usage():
  """ Prints the usage for this web service. """
  print "AppScale Server"
  print
  print "Options:"
  print "\t--type=<" + ','.join(dbconstants.VALID_DATASTORES) +  ">"
  print "\t--no_encryption"
  print "\t--port"


pb_application = tornado.web.Application([
  ('/clear', ClearHandler),
  ('/read-only', ReadOnlyHandler),
  (r'/*', MainHandler),
])


def main():
  """ Starts a web service for handing datastore requests. """

  global datastore_access
  zookeeper_locations = appscale_info.get_zk_locations_string()

  db_info = appscale_info.get_db_info()
  db_type = db_info[':table']
  port = dbconstants.DEFAULT_SSL_PORT
  is_encrypted = True
  verbose = False

  argv = sys.argv[1:]
  try:
    opts, args = getopt.getopt(argv, "t:p:n:v:",
      ["type=", "port", "no_encryption", "verbose"])
  except getopt.GetoptError:
    usage()
    sys.exit(1)
  
  for opt, arg in opts:
    if opt in ("-t", "--type"):
      db_type = arg
      print "Datastore type: ", db_type
    elif opt in ("-p", "--port"):
      port = int(arg)
    elif opt in ("-n", "--no_encryption"):
      is_encrypted = False
    elif opt in ("-v", "--verbose"):
      verbose = True

  if verbose:
    logger.setLevel(logging.DEBUG)

  if db_type not in dbconstants.VALID_DATASTORES:
    print "This datastore is not supported for this version of the AppScale\
          datastore API:" + db_type
    sys.exit(1)
 
  datastore_batch = DatastoreFactory.getDatastore(
    db_type, log_level=logger.getEffectiveLevel())
  zookeeper = zktransaction.ZKTransaction(
    host=zookeeper_locations, start_gc=True, db_access=datastore_batch,
    log_level=logger.getEffectiveLevel())

  datastore_access = DatastoreDistributed(
    datastore_batch, zookeeper=zookeeper, log_level=logger.getEffectiveLevel())
  if port == dbconstants.DEFAULT_SSL_PORT and not is_encrypted:
    port = dbconstants.DEFAULT_PORT

  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(port)

  while 1:
    try:
      # Start Server #
      tornado.ioloop.IOLoop.instance().start()
    except SSL.SSLError:
      # This happens when connections timeout, there is a just a bad
      # SSL connection such as it does not use SSL when expected. 
      pass
    except KeyboardInterrupt:
      print "Server interrupted by user, terminating..."
      zookeeper.close()
      sys.exit(1)
