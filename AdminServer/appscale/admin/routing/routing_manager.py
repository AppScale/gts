""" Configures routing for AppServer instances. """
import json
import logging
from collections import namedtuple

import six
from tornado import gen
from tornado.ioloop import IOLoop

from appscale.admin.constants import CONTROLLER_STATE_NODE
from appscale.admin.routing.haproxy import (
  APP_CONFIG, APP_INSTANCE, APP_STATS_SOCKET, HAProxy, HAProxyListenBlock,
  SERVICE_CONFIG, SERVICE_INSTANCE, SERVICE_STATS_SOCKET)
from appscale.common.async_retrying import (
  retry_children_watch_coroutine, retry_data_watch_coroutine)
from appscale.common.constants import (
  BLOBSTORE_SERVERS_NODE, BLOBSTORE_PORT, DATASTORE_SERVERS_NODE,
  DB_SERVER_PORT, SEARCH_SERVERS_NODE, SEARCH_SERVICE_PORT,
  TASKQUEUE_SERVICE_PORT, TQ_SERVERS_NODE, UA_SERVERS_NODE, UA_SERVER_PORT,
  VERSION_PATH_SEPARATOR, VERSION_REGISTRATION_NODE)

logger = logging.getLogger('appscale-admin')

ServiceInfo = namedtuple('ServiceInfo', ['registration_node', 'port', 'max_connections'])

SERVICE_DETAILS = {
  'as_blob_server': ServiceInfo(BLOBSTORE_SERVERS_NODE, BLOBSTORE_PORT, 1),
  'appscale-datastore_server': ServiceInfo(DATASTORE_SERVERS_NODE, DB_SERVER_PORT, 2),
  'appscale-search_server': ServiceInfo(SEARCH_SERVERS_NODE, SEARCH_SERVICE_PORT, 2),
  'TaskQueue': ServiceInfo(TQ_SERVERS_NODE, TASKQUEUE_SERVICE_PORT, 1),
  'UserAppServer': ServiceInfo(UA_SERVERS_NODE, UA_SERVER_PORT, 1)
}


class VersionRoutingManager(object):
  """ Configures routing for an AppServer instance. """

  # The default number of concurrent connections allowed.
  DEFAULT_MAX_CONNECTIONS = 7

  def __init__(self, version_key, zk_client, haproxy):
    """ Creates a new VersionRoutingManager object.

    Args:
      version_key: A string specifying a version key.
      zk_client: A KazooClient.
      haproxy: An HAProxy object.
    """
    # Indicates that the watch is still needed.
    self._active = True

    self._version_key = version_key
    self._haproxy = haproxy
    self._instances = []
    self._port = None
    self._max_connections = None
    self._zk_client = zk_client

    instances_node = '/'.join([VERSION_REGISTRATION_NODE, self._version_key])
    self._zk_client.ensure_path(instances_node)
    self._zk_client.ChildrenWatch(instances_node, self._update_instances_watch)

    project_id, service_id, version_id = self._version_key.split(
      VERSION_PATH_SEPARATOR)
    version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      project_id, service_id, version_id)
    self._zk_client.DataWatch(version_node, self._update_version_watch)

  @gen.coroutine
  def stop(self):
    """ Stops routing all instances for the version. """
    self._active = False
    self._instances = []
    self._port = None
    self._max_connections = None
    yield self._update_version_block()

  @gen.coroutine
  def _update_instances(self, instances):
    """ Handles changes to list of registered instances.

    Args:
      versions: A list of strings specifying registered instances.
    """
    self._instances = instances
    yield self._update_version_block()

  def _update_instances_watch(self, instances):
    """ Handles changes to list of registered instances.

    Args:
      versions: A list of strings specifying registered instances.
    """
    if not self._active:
      return False

    IOLoop.instance().add_callback(self._update_instances, instances)

  @gen.coroutine
  def _update_version(self, encoded_version):
    """ Handles changes to the version details.

    Args:
      encoded_version: A JSON-encoded string containing version details.
    """
    if encoded_version is None:
      self._port = None
      self._max_connections = None
      yield self._update_version_block()
      return

    version_details = json.loads(encoded_version)

    # If the threadsafe value is not defined, the application can handle
    # concurrent requests.
    threadsafe = version_details.get('threadsafe', True)
    if threadsafe:
      self._max_connections = self.DEFAULT_MAX_CONNECTIONS
    else:
      self._max_connections = 1

    self._port = version_details.get('appscaleExtensions', {}).\
      get('haproxyPort')

    yield self._update_version_block()

  @gen.coroutine
  def _update_version_block(self):
    """ Updates HAProxy's version configuration and triggers a reload. """

    # If the port or max_connections is not known, it's not possible to route
    # the version.
    if (self._port is None or self._max_connections is None or
        not self._instances):
      self._haproxy.blocks.pop(self._version_key, None)
      yield self._haproxy.reload()
      return

    if self._version_key not in self._haproxy.blocks:
      self._haproxy.blocks[self._version_key] = HAProxyListenBlock(
        'gae_' + self._version_key, self._port, self._max_connections)

    haproxy_app_version = self._haproxy.blocks[self._version_key]
    haproxy_app_version.port = self._port
    haproxy_app_version.max_connections = self._max_connections
    haproxy_app_version.servers = self._instances
    yield self._haproxy.reload()

  def _update_version_watch(self, version_details, _):
    """ Handles changes to the version details.

    Args:
      version_details: A JSON-encoded string containing version details.
    """
    if not self._active:
      return False

    IOLoop.instance().add_callback(self._update_version, version_details)


class RoutingManager(object):
  """ Configures routing for AppServer instances. """
  def __init__(self, zk_client):
    """ Creates a new RoutingManager object.

    Args:
      zk_client: A KazooClient.
    """
    self._app_haproxy = HAProxy(APP_INSTANCE, APP_CONFIG, APP_STATS_SOCKET)
    self._service_haproxy = HAProxy(SERVICE_INSTANCE, SERVICE_CONFIG,
                                    SERVICE_STATS_SOCKET)
    self._versions = {}
    self._zk_client = zk_client

  def start(self):
    """ Starts updating routing configuration. """
    # Subscribe to changes in controller state, which includes the HAProxy
    # connect timeout.
    self._zk_client.DataWatch(CONTROLLER_STATE_NODE,
                              self._controller_state_watch)

    self._zk_client.ensure_path(VERSION_REGISTRATION_NODE)
    self._zk_client.ChildrenWatch(VERSION_REGISTRATION_NODE,
                                  self._update_versions_watch)

    for service_id, service_info in six.iteritems(SERVICE_DETAILS):
      self._zk_client.ensure_path(service_info.registration_node)
      self._zk_client.ChildrenWatch(service_info.registration_node,
                                    self._create_service_watch(service_id))

  @gen.coroutine
  def _update_versions(self, new_version_list):
    """ Handles changes to list of registered versions.

    This is intended to be run in the main IO loop.

    Args:
      new_version_list: A list of strings specifying registered versions.
    """
    to_stop = [version for version in self._versions
               if version not in new_version_list]
    for version_key in to_stop:
      yield self._versions[version_key].stop()
      del self._versions[version_key]

    for version_key in new_version_list:
      if version_key not in self._versions:
        self._versions[version_key] = VersionRoutingManager(
          version_key, self._zk_client, self._app_haproxy)

  def _update_versions_watch(self, versions):
    """ Handles changes to list of registered versions.

    Args:
      versions: A list of strings specifying registered versions.
    """
    persistent_update_versions = retry_children_watch_coroutine(
      VERSION_REGISTRATION_NODE, self._update_versions)
    IOLoop.instance().add_callback(persistent_update_versions, versions)

  @gen.coroutine
  def _update_service(self, service_id, new_locations):
    if service_id not in self._service_haproxy.blocks:
      service = SERVICE_DETAILS[service_id]
      self._service_haproxy.blocks[service_id] = HAProxyListenBlock(
        service_id, service.port, service.max_connections)

    block = self._service_haproxy.blocks[service_id]
    block.servers = new_locations
    yield self._service_haproxy.reload()

  def _create_service_watch(self, service_id):
    def update_service_watch(locations):
      persistent_update_service = retry_children_watch_coroutine(
        SERVICE_DETAILS[service_id][0], self._update_service)
      IOLoop.instance().add_callback(persistent_update_service, service_id,
                                     locations)

    return update_service_watch

  @gen.coroutine
  def _update_controller_state(self, encoded_controller_state):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    if not encoded_controller_state:
      return

    controller_state = json.loads(encoded_controller_state)

    connect_timeout_ms = int(controller_state.get('@options', {}).\
      get('lb_connect_timeout', HAProxy.DEFAULT_CONNECT_TIMEOUT * 1000))

    if connect_timeout_ms != self._app_haproxy.connect_timeout_ms:
      self._app_haproxy.connect_timeout_ms = connect_timeout_ms
      yield self._app_haproxy.reload()

  def _controller_state_watch(self, encoded_controller_state, _):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    persistent_update_controller_state = retry_data_watch_coroutine(
      CONTROLLER_STATE_NODE, self._update_controller_state)
    IOLoop.instance().add_callback(
      persistent_update_controller_state, encoded_controller_state)
