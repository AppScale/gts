""" A tornado web service for handling TaskQueue request from application
servers. """

import argparse
import json
import logging
import monotonic
import signal
import sys

from kazoo.client import KazooClient, KazooState, NodeExistsError
from tornado import gen, httpserver, ioloop
from tornado.web import Application, RequestHandler

from appscale.common import appscale_info
from appscale.common.constants import TQ_SERVERS_NODE, ZK_PERSISTENT_RECONNECTS
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

from appscale.taskqueue import distributed_tq, pg_connection_wrapper
from appscale.taskqueue.constants import SHUTTING_DOWN_TIMEOUT
from .protocols import taskqueue_service_pb2
from .protocols import remote_api_pb2
from appscale.taskqueue.rest_api import (
  REST_PREFIX, RESTLease, RESTQueue, RESTTask, RESTTasks, QueueList
)
from appscale.taskqueue.statistics import (
  PROTOBUFFER_API, service_stats, stats_lock
)
from appscale.taskqueue.utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)


class ProtobufferHandler(RequestHandler):
  """ Defines what to do when the webserver receives different types of HTTP
  requests. """

  def initialize(self, queue_handler):
    """ Provide access to the queue handler. """
    self.queue_handler = queue_handler

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
      self.stats_info = service_stats.start_request()
      self.stats_info.api = PROTOBUFFER_API
      self.stats_info.pb_method = None
      self.stats_info.rest_method = None
      self.stats_info.pb_status = None
      self.stats_info.rest_status = None

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
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data = app_data.split(':')
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
    apirequest = remote_api_pb2.Request()
    apirequest.ParseFromString(http_request_data)
    apiresponse = remote_api_pb2.Response()
    response = None
    errcode = 0
    errdetail = ""
    method = ""
    http_request_data = ""
    app_id = app_info['app_id']
    if not apirequest.HasField("method"):
      errcode = taskqueue_service_pb2.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Method was not set in request"
      apirequest.method = "NOT_FOUND"
    else:
      method = apirequest.method

    if not apirequest.HasField("request"):
      errcode = taskqueue_service_pb2.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Request missing in call"
      apirequest.method = "NOT_FOUND"
      apirequest.ClearField("request")
    else:
      http_request_data = apirequest.request

    start_time = monotonic.monotonic()

    request_log = method
    if apirequest.HasField("request_id"):
      request_log += ': {}'.format(apirequest.request_id)
    logger.debug(request_log)

    result = None
    if method == "FetchQueueStats":
      result = self.queue_handler.fetch_queue_stats(app_id, http_request_data)
    elif method == "PurgeQueue":
      result = self.queue_handler.purge_queue(app_id, http_request_data)
    elif method == "Delete":
      result = self.queue_handler.delete(app_id, http_request_data)
    elif method == "QueryAndOwnTasks":
      result = self.queue_handler.query_and_own_tasks(app_id, http_request_data)
    elif method == "Add":
      result = self.queue_handler.add(app_info, http_request_data)
    elif method == "BulkAdd":
      result = self.queue_handler.bulk_add(app_info, http_request_data)
    elif method == "ModifyTaskLease":
      result = self.queue_handler.modify_task_lease(app_id, http_request_data)
    elif method == "UpdateQueue":
      response = taskqueue_service_pb2.TaskQueueUpdateQueueResponse()
      result = self.queue_handler.SerializeToString(), 0, ""
    elif method == "FetchQueues":
      result = self.queue_handler.fetch_queue(app_id, http_request_data)
    elif method == "QueryTasks":
      result = self.queue_handler.query_tasks(app_id, http_request_data)
    elif method == "FetchTask":
      result = self.queue_handler.fetch_task(app_id, http_request_data)
    elif method == "ForceRun":
      result = self.queue_handler.force_run(app_id, http_request_data)
    elif method == "DeleteQueue":
      response = taskqueue_service_pb2.TaskQueueDeleteQueueResponse()
      result = self.queue_handler.SerializeToString(), 0, ""
    elif method == "PauseQueue":
      result = self.queue_handler.pause_queue(app_id, http_request_data)
    elif method == "DeleteGroup":
      result = self.queue_handler.delete_group(app_id, http_request_data)
    elif method == "UpdateStorageLimit":
      result = self.queue_handler.update_storage_limit(
        app_id, http_request_data)

    if result:
      response, errcode, errdetail = result

    elapsed_time = round(monotonic.monotonic() - start_time, 3)
    timing_log = 'Elapsed: {}'.format(elapsed_time)
    if apirequest.HasField("request_id"):
      timing_log += ' ({})'.format(apirequest.request_id)
    logger.debug(timing_log)

    if response is not None:
      apiresponse.response = response

    # If there was an error add it to the response.
    if errcode != 0:
      apperror_pb = apiresponse.application_error
      apperror_pb.code = errcode
      apperror_pb.detail = errdetail

    self.write(apiresponse.SerializeToString())
    status = taskqueue_service_pb2.TaskQueueServiceError.ErrorCode.Name(errcode)
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


def prepare_taskqueue_application(task_queue):
  handlers = [
    # Allows task viewer to retrieve list of queues.
    (REST_PREFIX, QueueList, {'queue_handler': task_queue}),

    # Provides compatibility with the v1beta2 REST API.
    (RESTQueue.PATH, RESTQueue, {'queue_handler': task_queue}),
    (RESTTasks.PATH, RESTTasks, {'queue_handler': task_queue}),
    (RESTLease.PATH, RESTLease, {'queue_handler': task_queue}),
    (RESTTask.PATH, RESTTask, {'queue_handler': task_queue}),
    # Responds with service statistic
    ("/service-stats", StatsHandler),
    # Takes protocol buffers from the AppServers.
    (r"/.*", ProtobufferHandler, {'queue_handler': task_queue})
  ]

  return Application(handlers)


def prepare_graceful_shutdown(zk_client, tornado_server):
  """ Defines function which should handle termination signal.
  
  Args:
    zk_client: an instance of zookeeper client.
    tornado_server: an instance of tornado server.
  Returns:
    a callable which takes care about graceful shutdown.
  """

  def graceful_shutdown(*_):
    """ Stop accepting new requests and exit when all requests are finished
    or timeout is exceeded.
    """
    deadline = monotonic.monotonic() + SHUTTING_DOWN_TIMEOUT
    logger.info('Stopping server')
    tornado_server.stop()
    io_loop = ioloop.IOLoop.current()

    def stop_on_signal():
      current_requests = service_stats.current_requests
      if current_requests and monotonic.monotonic() < deadline:
        logger.warning("Can't stop Taskqueue server now as {reqs} requests are "
                       "still in progress".format(reqs=current_requests))
      else:
        if current_requests:
          logger.error("Shutting down server despite {reqs} requests "
                       "in progress".format(reqs=current_requests))
        # Stop tornado IO loop and zookeeper client
        io_loop.stop()
        zk_client.stop()
        logger.info("IOLoop stopped")

    ioloop.PeriodicCallback(stop_on_signal, 200).start()

  return graceful_shutdown


def register_location(zk_client, host, port):
  """ Register service location with ZooKeeper. """
  server_node = '{}/{}:{}'.format(TQ_SERVERS_NODE, host, port)

  def create_server_node():
    """ Creates a server registration entry in ZooKeeper. """
    try:
      zk_client.retry(zk_client.create, server_node, ephemeral=True)
    except NodeExistsError:
      # If the server gets restarted, the old node may exist for a short time.
      zk_client.retry(zk_client.delete, server_node)
      zk_client.retry(zk_client.create, server_node, ephemeral=True)

    logger.info('TaskQueue server registered at {}'.format(server_node))

  def zk_state_listener(state):
    """ Handles changes to ZooKeeper connection state.

    Args:
      state: A string specifying the new ZooKeeper connection state.
    """
    if state == KazooState.CONNECTED:
      ioloop.IOLoop.instance().add_callback(create_server_node)

  zk_client.add_listener(zk_state_listener)
  zk_client.ensure_path(TQ_SERVERS_NODE)
  # Since the client was started before adding the listener, make sure the
  # server node gets created.
  zk_state_listener(zk_client.state)


def main():
  """ Main function which initializes and starts the tornado server. """
  # Parse command line arguments
  parser = argparse.ArgumentParser(description='A taskqueue API server')
  parser.add_argument('--port', '-p', default='17447',
                      help='TaskQueue server port')
  parser.add_argument('--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()
  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  # Configure zookeeper and db access
  zk_client = KazooClient(
    hosts=','.join(appscale_info.get_zk_node_ips()),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()

  pg_connection_wrapper.start_postgres_dsn_watch(zk_client)
  register_location(zk_client, appscale_info.get_private_ip(), args.port)

  # Initialize tornado server
  task_queue = distributed_tq.DistributedTaskQueue(zk_client)
  tq_application = prepare_taskqueue_application(task_queue)
  # Automatically decompress incoming requests.
  server = httpserver.HTTPServer(tq_application, decompress_request=True)
  server.listen(args.port)

  # Make sure taskqueue shuts down gracefully when signal is received
  graceful_shutdown = prepare_graceful_shutdown(zk_client, server)
  signal.signal(signal.SIGTERM, graceful_shutdown)
  signal.signal(signal.SIGINT, graceful_shutdown)

  logger.info('Starting TaskQueue server on port {}'.format(args.port))
  ioloop.IOLoop.current().start()
