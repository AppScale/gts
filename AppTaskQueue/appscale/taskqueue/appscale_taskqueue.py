""" A tornado web service for handling TaskQueue request from application
servers. """

import argparse
import logging
import sys
import tornado.httpserver
import tornado.ioloop
import tornado.web

import distributed_tq

from appscale.datastore.cassandra_env.cassandra_interface import DatastoreProxy
from .rest_api import RESTLease
from .rest_api import RESTQueue
from .rest_api import RESTTask
from .rest_api import RESTTasks
from .unpackaged import APPSCALE_PYTHON_APPSERVER
from .utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.ext.remote_api import remote_api_pb


# Global for Distributed TaskQueue.
task_queue = None


class StopWorkerHandler(tornado.web.RequestHandler):
  """ Stops taskqueue workers for an app if they are running. """
  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is the
    request from the AppController in a JSON string. """
    global task_queue    
    request = self.request
    http_request_data = request.body
    json_response = task_queue.stop_worker(http_request_data)
    self.write(json_response)
    self.finish()


class ReloadWorkerHandler(tornado.web.RequestHandler):
  """ Reloads taskqueue workers for an app. """
  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is the
    request from the AppController in a JSON string. """
    global task_queue    
    request = self.request
    http_request_data = request.body
    json_response = task_queue.reload_worker(http_request_data)
    self.write(json_response)
    self.finish()


class StartWorkerHandler(tornado.web.RequestHandler):
  """ Starts taskqueue workers for an app if they are not running. """
  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is the
    request from the AppController in a JSON string. """
    global task_queue
    request = self.request
    http_request_data = request.body
    json_response = task_queue.start_worker(http_request_data)
    self.write(json_response)
    self.finish()


class MainHandler(tornado.web.RequestHandler):
  """ Defines what to do when the webserver receives different types of HTTP
  requests. """
  def unknown_request(self, app_id, http_request_data, pb_type):
    """ Function which handles unknown protocol buffers.
   
    Args:
      app_id: A string, the application ID.
      http_request_data: The encoded protocol buffer from the AppServer.
    Raise:
      NotImplementedError: This unknown type is not implemented.
    """
    raise NotImplementedError("Unknown request of operation %s" % pb_type)

  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is the
    request from the AppServer in an encoded protocol buffer format. """
    global task_queue    
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data  = app_data.split(':')
    app_id = app_data[0]
 
    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)

    self.finish()

  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
    up in JSON. """
    global task_queue    
    self.write('{"status":"up"}')
    self.finish()

  def remote_request(self, app_id, http_request_data):
    """ Receives a remote request to which it should give the correct
    response. The http_request_data holds an encoded protocol buffer of a
    certain type. Each type has a particular response type.

    Args:
      app_id: The application ID that is sending this request.
      http_request_data: Encoded protocol buffer.
    """
    global task_queue    
    apirequest = remote_api_pb.Request()
    apirequest.ParseFromString(http_request_data)
    apiresponse = remote_api_pb.Response()
    response = None
    errcode = 0
    errdetail = ""
    method = ""
    http_request_data = ""

    if not apirequest.has_method():
      errcode = taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Method was not set in request"
      apirequest.set_method("NOT_FOUND")
    else:
      method = apirequest.method()

    if not apirequest.has_request():
      errcode = taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Request missing in call"
      apirequest.set_method("NOT_FOUND")
      apirequest.clear_request()
    else:
      http_request_data = apirequest.request()

    logger.debug('Method: {}'.format(method))
    if method == "FetchQueueStats":
      response, errcode, errdetail = task_queue.fetch_queue_stats(app_id,
                                                 http_request_data)
    elif method == "PurgeQueue":
      response, errcode, errdetail = task_queue.purge_queue(app_id,
                                                 http_request_data)
    elif method == "Delete":
      response, errcode, errdetail = task_queue.delete(app_id,
                                                 http_request_data)
    elif method == "QueryAndOwnTasks":
      response, errcode, errdetail = task_queue.query_and_own_tasks(
                                                 app_id,
                                                 http_request_data)
    elif method == "Add":
      response, errcode, errdetail = task_queue.add(app_id,
                                                 http_request_data)
    elif method == "BulkAdd":
      response, errcode, errdetail = task_queue.bulk_add(app_id,
                                                 http_request_data)
    elif method == "ModifyTaskLease":
      response, errcode, errdetail = task_queue.modify_task_lease(app_id,
                                                 http_request_data)
    elif method == "UpdateQueue":
      response = taskqueue_service_pb.TaskQueueUpdateQueueResponse()
      response, errcode, errdetail = response.Encode(), 0, ""
    elif method == "FetchQueues":
      response, errcode, errdetail = task_queue.fetch_queue(app_id,
                                                 http_request_data)
    elif method == "QueryTasks":
      response, errcode, errdetail = task_queue.query_tasks(app_id,
                                                 http_request_data)
    elif method == "FetchTask":
      response, errcode, errdetail = task_queue.fetch_task(app_id,
                                                 http_request_data)
    elif method == "ForceRun":
      response, errcode, errdetail = task_queue.force_run(app_id,
                                                 http_request_data)
    elif method == "DeleteQueue":
      response = taskqueue_service_pb.TaskQueueDeleteQueueResponse()
      response, errcode, errdetail = response.Encode(), 0, ""
    elif method == "PauseQueue":
      response, errcode, errdetail = task_queue.pause_queue(app_id,
                                                 http_request_data)
    elif method == "DeleteGroup":
      response, errcode, errdetail = task_queue.delete_group(app_id,
                                                 http_request_data)
    elif method == "UpdateStorageLimit":
      response, errcode, errdetail = task_queue.update_storage_limit(
                                                 app_id,
                                                 http_request_data)

    if response is not None:
      apiresponse.set_response(response)

    # If there was an error add it to the response.
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    self.write(apiresponse.Encode())


def main():
  """ Main function which initializes and starts the tornado server. """
  parser = argparse.ArgumentParser(description='A taskqueue API server')
  parser.add_argument('--port', '-p', default='17447',
                      help='TaskQueue server port')
  parser.add_argument('--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  global task_queue

  db_access = DatastoreProxy()
  task_queue = distributed_tq.DistributedTaskQueue(db_access)
  handlers = [
    # Takes JSON requests from AppController.
    (r"/startworker", StartWorkerHandler),
    (r"/stopworker", StopWorkerHandler),
    (r"/reloadworker", ReloadWorkerHandler),
    # Takes protocol buffers from the AppServers.
    (r"/*", MainHandler)
  ]

  # Provides compatibility with the v1beta2 REST API.
  handlers.extend([
    (RESTQueue.PATH, RESTQueue, {'queue_handler': task_queue}),
    (RESTTasks.PATH, RESTTasks, {'queue_handler': task_queue}),
    (RESTLease.PATH, RESTLease, {'queue_handler': task_queue}),
    (RESTTask.PATH, RESTTask, {'queue_handler': task_queue})
  ])

  tq_application = tornado.web.Application(handlers)

  server = tornado.httpserver.HTTPServer(
    tq_application,
    decompress_request=True)   # Automatically decompress incoming requests.
  server.listen(args.port)

  while 1:
    try:
      logger.info('Starting TaskQueue server on port {}'.format(args.port))
      tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
      logger.warning('Server interrupted by user, terminating...')
      sys.exit(1)
