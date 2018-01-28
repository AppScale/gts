""" A tornado web service for handling TaskQueue request from application
servers. """

import argparse
import json
import logging
import signal
import sys
import time

from kazoo.client import KazooClient
from tornado import gen, httpserver, ioloop
from tornado.web import Application, RequestHandler

from appscale.common import appscale_info
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.cassandra_env.cassandra_interface import DatastoreProxy
from appscale.taskqueue.statistics import PROTOBUFFER_API

from . import distributed_tq
from .rest_api import RESTLease
from .rest_api import RESTQueue
from .rest_api import RESTTask
from .rest_api import RESTTasks
from .statistics import service_stats, stats_lock
from .utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.ext.remote_api import remote_api_pb


# The TaskQueue server's Tornado HTTPServer.
server = None

# Global for Distributed TaskQueue.
task_queue = None

# A KazooClient for watching queue configuration.
zk_client = None


class ProtobufferHandler(RequestHandler):
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

  @gen.coroutine
  def prepare(self):
    with (yield stats_lock.acquire()):
      self.stats_info = service_stats.start_request(api=PROTOBUFFER_API)

  @gen.coroutine
  def on_finish(self):
    if self.stats_info.pb_status is None:
      self.stats_info.pb_status = "UNKNOWN_ERROR"
    with (yield stats_lock.acquire()):
      self.stats_info.finalize()

  @gen.coroutine
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
    version = request.headers['Version']
    module = request.headers['Module']
    app_info = {'app_id': app_id, 'version_id': version, 'module_id': module}
    if pb_type == "Request":
      method, status = self.remote_request(app_info, http_request_data)
      # Fill request stats info
      self.stats_info.pb_method = method
      self.stats_info.pb_status = status
    else:
      self.unknown_request(app_id, http_request_data, pb_type)
      # Fill request stats info
      self.stats_info.pb_status = "NOT_A_PROTOBUFFER_REQUEST"

  def remote_request(self, app_info, http_request_data):
    """ Receives a remote request to which it should give the correct
    response. The http_request_data holds an encoded protocol buffer of a
    certain type. Each type has a particular response type.

    Args:
      app_info: A dictionary containing the application, module, and version ID
        of the app that is sending this request.
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
    app_id = app_info['app_id']
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

    start_time = time.time()

    request_log = method
    if apirequest.has_request_id():
      request_log += ': {}'.format(apirequest.request_id())
    logger.debug(request_log)

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
      response, errcode, errdetail = task_queue.add(app_info,
                                                 http_request_data)
    elif method == "BulkAdd":
      response, errcode, errdetail = task_queue.bulk_add(app_info,
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
    elapsed_time = round(time.time() - start_time, 3)
    timing_log = 'Elapsed: {}'.format(elapsed_time)
    if apirequest.has_request_id():
      timing_log += ' ({})'.format(apirequest.request_id())
    logger.debug(timing_log)

    if response is not None:
      apiresponse.set_response(response)

    # If there was an error add it to the response.
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    self.write(apiresponse.Encode())
    status = taskqueue_service_pb.TaskQueueServiceError.ErrorCode_Name(errcode)
    return method, status


class StatsHandler(RequestHandler):
  """ Defines what to do when the webserver receives different types of HTTP
  requests. """
  @gen.coroutine
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
    up in JSON. """
    cursor = self.get_argument("cursor", None)
    last_milliseconds = self.get_argument("last_milliseconds", None)
    try:
      if cursor:
        recent_stats = service_stats.scroll_recent(int(cursor))
      elif last_milliseconds:
        recent_stats = service_stats.get_recent(int(last_milliseconds))
      else:
        recent_stats = service_stats.get_recent()
    except ValueError:
      self.set_status(400, "cursor and last_milliseconds "
                           "arguments should be integers")
      return

    with (yield stats_lock.acquire()):
      cumulative_counters = service_stats.get_cumulative_counters()

    tq_stats = {
      "current_requests": service_stats.current_requests,
      "cumulative_counters": cumulative_counters,
      "recent_stats": recent_stats
    }
    self.write(json.dumps(tq_stats))
    self.finish()


def graceful_shutdown(*_):
  """ Stop accepting new requests and exit on the next I/O loop iteration.

  This is safe as long as the server is synchronous. It will stop in the middle
  of requests as soon as the server has asynchronous handlers.
  """
  logger.info('Stopping server')
  zk_client.stop()
  server.stop()
  io_loop = ioloop.IOLoop.current()
  io_loop.add_callback_from_signal(io_loop.stop)


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

  global task_queue, zk_client

  zk_client = KazooClient(
    hosts=','.join(appscale_info.get_zk_node_ips()),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()

  db_access = DatastoreProxy()
  task_queue = distributed_tq.DistributedTaskQueue(db_access, zk_client)
  handlers = [
    # Responds with service statistic
    ("/service-stats", StatsHandler),
    # Takes protocol buffers from the AppServers.
    (r"/*", ProtobufferHandler)
  ]

  # Provides compatibility with the v1beta2 REST API.
  handlers += [
    (RESTQueue.PATH, RESTQueue, {'queue_handler': task_queue}),
    (RESTTasks.PATH, RESTTasks, {'queue_handler': task_queue}),
    (RESTLease.PATH, RESTLease, {'queue_handler': task_queue}),
    (RESTTask.PATH, RESTTask, {'queue_handler': task_queue})
  ]

  tq_application = Application(handlers)

  global server
  # Automatically decompress incoming requests.
  server = httpserver.HTTPServer(tq_application, decompress_request=True)
  server.listen(args.port)

  signal.signal(signal.SIGTERM, graceful_shutdown)
  signal.signal(signal.SIGINT, graceful_shutdown)

  logger.info('Starting TaskQueue server on port {}'.format(args.port))
  ioloop.IOLoop.current().start()
