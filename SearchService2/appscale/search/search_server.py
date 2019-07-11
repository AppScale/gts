"""
The main modules of SearchService2.
It starts tornado http server which handles HTTP request
which contains Remote API protocol buffer request
which wraps Search API protocol buffer request.

This module reads Remote API request, and routes containing Search API
request to proper method of APIMethods.
"""
import argparse
import json
import logging

from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError
from kazoo.protocol.states import KazooState
from tornado.ioloop import IOLoop

from appscale.common.async_retrying import retry_data_watch_coroutine
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from tornado import ioloop, web

from appscale.search import api_methods
from appscale.search.constants import SearchServiceError, SEARCH_SERVERS_NODE
from appscale.search.protocols import search_pb2, remote_api_pb2

logger = logging.getLogger(__name__)


class ProtobufferAPIHandler(web.RequestHandler):
  """ Serves Protobuffer requests to SearchService2. """

  def initialize(self, api):
    self.api = api

  async def post(self):
    """ Function which handles POST requests. Data of the request is the
    request from the AppServer in an encoded protocol buffer format. """
    http_request_data = self.request.body
    pb_type = self.request.headers['protocolbuffertype']
    if pb_type != 'Request':
      raise NotImplementedError('Unknown protocolbuffertype {}'.format(pb_type))

    # Get app_id from appdata
    app_id = self.request.headers['appdata'].split(':')[0]

    remote_api_request = remote_api_pb2.Request()
    remote_api_request.ParseFromString(http_request_data)
    remote_api_response = remote_api_pb2.Response()
    try:
      # Make sure remote_api_request has search api method specified
      if not remote_api_request.HasField('method'):
        raise SearchServiceError(search_pb2.SearchServiceError.INVALID_REQUEST,
                                 'Method was not set in request')
      # Make sure remote_api_request has search api request specified
      if not remote_api_request.HasField('request'):
        raise SearchServiceError(search_pb2.SearchServiceError.INVALID_REQUEST,
                                 'Request data is not set in request')

      # Handle Search API request of specific
      search_api_method = remote_api_request.method
      search_api_request_data = remote_api_request.request
      logger.debug('Handling SearchAPI.{} request..'.format(search_api_method))
      search_api_response = await self.handle_search_api_request(
        app_id, search_api_method, search_api_request_data
      )

      # Set encoded Search API response to Remote API response
      remote_api_response.response = search_api_response.SerializeToString()

    except SearchServiceError as err:
      # Set error information to Remote API response
      service_error_pb = remote_api_response.application_error
      service_error_pb.code = err.error_code
      service_error_pb.detail = err.error_detail
      if err.search_api_response:
        # Write also whatever Search API response is provided
        encoded_response = err.search_api_response.SerializeToString()
        remote_api_response.response = encoded_response

      # Write error details to log
      if err.error_code == search_pb2.SearchServiceError.INTERNAL_ERROR:
        logger.exception('InternalError: {}'.format(err.error_detail))
      else:
        logger.warning('SearchServiceError "{}" ({})'
                       .format(err.error_name, err.error_detail))

    # Write encoded Remote API response
    self.write(remote_api_response.SerializeToString())

  async def handle_search_api_request(self, app_id, search_api_method,
                                      search_api_req_data):
    """ Handles Search API request.

    Args:
      app_id: A string representing project_id.
      search_api_method: A string representing name of Search API method.
      search_api_req_data: Encoded protobuffer Search API request.
    Returns:
      An instance of protobuffer Search API response.
    """
    try:
      req_class, resp_class, executor = self.api[search_api_method]
    except KeyError:
      raise SearchServiceError(
        search_pb2.SearchServiceError.INVALID_REQUEST,
        'Unknown request method "{}"'.format(search_api_method)
      )
    search_api_req = req_class()
    search_api_req.ParseFromString(search_api_req_data)
    if not search_api_req.app_id:
      search_api_req.app_id = app_id
    search_api_resp = resp_class()
    await executor(search_api_req, search_api_resp)
    return search_api_resp


class HealthRequestHandler(web.RequestHandler):
  """ Serves health check requests to SearchService2. """

  def initialize(self, solr_api, zk_client):
    self.solr_api = solr_api
    self.zk_client = zk_client

  def get(self):
    self.set_header('Content-Type', 'application/json')
    self.write(json.dumps({
      'solr_live_nodes': self.solr_api.live_nodes,
      'zookeeper_state': self.zk_client.state
    }))


def prepare_api_methods_routing(methods):
  """ Instantiates APIMethods and defines API methods routing.

  Args:
    zk_client: an instance of kazoo.client.KazooClient.
  Returns:
    a dict which maps Search API method name to a tuple of
    (<request_class>, <response_class>, <coroutine_to_handle_request>)
  """
  return {
    'IndexDocument': (
      search_pb2.IndexDocumentRequest,
      search_pb2.IndexDocumentResponse,
      methods.index_document
    ),
    'DeleteDocument': (
      search_pb2.DeleteDocumentRequest,
      search_pb2.DeleteDocumentResponse,
      methods.delete_document
    ),
    'ListIndexes': (
      search_pb2.ListIndexesRequest,
      search_pb2.ListIndexesResponse,
      methods.list_indexes
    ),
    'ListDocuments': (
      search_pb2.ListDocumentsRequest,
      search_pb2.ListDocumentsResponse,
      methods.list_documents
    ),
    'Search': (
      search_pb2.SearchRequest,
      search_pb2.SearchResponse,
      methods.search
    )
  }


def register_search_server(zk_client, private_ip, port):
  server_node = '{}/{}:{}'.format(SEARCH_SERVERS_NODE, private_ip, port)

  def create_server_node():
    """ Creates a server registration entry in ZooKeeper. """
    try:
      zk_client.create(server_node, ephemeral=True)
    except NodeExistsError:
      # If the server gets restarted, the old node may exist for a short time.
      zk_client.delete(server_node)
      zk_client.create(server_node, ephemeral=True)
    logger.info('Search server registered at {}'.format(server_node))

  def zk_state_listener(state):
    """ Handles changes to ZooKeeper connection state.

    Args:
      state: A string specifying the new ZooKeeper connection state.
    """
    if state == KazooState.CONNECTED:
      persistent_create_server_node = retry_data_watch_coroutine(
        server_node, create_server_node)
      IOLoop.instance().add_callback(persistent_create_server_node)

  zk_client.add_listener(zk_state_listener)
  # Make sure the server node gets created initially.
  zk_client.ensure_path(SEARCH_SERVERS_NODE)
  zk_state_listener(zk_client.state)


def main():
  """ Start SearchService2 server. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--host', help='The host to listen on')
  parser.add_argument(
    '--port', type=int, help='The port to listen on')
  parser.add_argument(
    '--zk-locations', nargs='+', help='ZooKeeper location(s)')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  zk_client = KazooClient(
    hosts=','.join(args.zk_locations),
    connection_retry=ZK_PERSISTENT_RECONNECTS
  )
  zk_client.start()

  # Initialize Protobuffer API routing
  methods = api_methods.APIMethods(zk_client)
  api = prepare_api_methods_routing(methods)

  logging.info('Starting server on port {}'.format(args.port))
  app = web.Application([
    (r'/?', ProtobufferAPIHandler, {'api': api}),
    (r'/_health', HealthRequestHandler, {'solr_api': methods.solr_adapter.solr,
                                         'zk_client': zk_client}),
  ])
  app.listen(args.port)
  io_loop = ioloop.IOLoop.current()

  # Make sure /appscale/search/servers/<IP>:<PORT> exists while server is alive.
  register_search_server(zk_client, args.host, args.port)

  io_loop.start()
