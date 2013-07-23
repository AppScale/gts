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
"""Manage the lifecycle of servers and dispatch requests to them."""

import collections
import logging
import threading
import urlparse
import wsgiref.headers

from google.appengine.api import request_info
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import scheduled_executor
from google.appengine.tools.devappserver2 import server
from google.appengine.tools.devappserver2 import start_response_utils
from google.appengine.tools.devappserver2 import thread_executor
from google.appengine.tools.devappserver2 import wsgi_server

_THREAD_POOL = thread_executor.ThreadExecutor()

ResponseTuple = collections.namedtuple('ResponseTuple',
                                       ['status', 'headers', 'content'])


class PortRegistry(object):
  def __init__(self):
    self._ports = {}
    self._ports_lock = threading.RLock()

  def add(self, port, servr, inst):
    with self._ports_lock:
      self._ports[port] = (servr, inst)

  def get(self, port):
    with self._ports_lock:
      return self._ports[port]


class Dispatcher(request_info.Dispatcher):
  """A devappserver2 implementation of request_info.Dispatcher.

  In addition to the request_info.Dispatcher interface, it owns servers and
  manages their lifetimes.
  """

  def __init__(self,
               configuration,
               host,
               port,
               auth_domain,
               runtime_stderr_loglevel,
               php_executable_path,
               enable_php_remote_debugging,
               python_config,
               cloud_sql_config,
               server_to_max_instances,
               use_mtime_file_watcher,
               automatic_restart,
               allow_skipped_files):
    """Initializer for Dispatcher.

    Args:
      configuration: An application_configuration.ApplicationConfiguration
          instance storing the configuration data for the app.
      host: A string containing the host that any HTTP servers should bind to
          e.g. "localhost".
      port: An int specifying the first port where servers should listen.
      auth_domain: A string containing the auth domain to set in the environment
          variables.
      runtime_stderr_loglevel: An int reprenting the minimum logging level at
          which runtime log messages should be written to stderr. See
          devappserver2.py for possible values.
      php_executable_path: A string containing the path to PHP execution e.g.
          "/usr/bin/php-cgi".
      enable_php_remote_debugging: A boolean indicating whether the PHP
          interpreter should be started with XDebug remote debugging enabled.
      python_config: A runtime_config_pb2.PythonConfig instance containing
          Python runtime-specific configuration. If None then defaults are
          used.
      cloud_sql_config: A runtime_config_pb2.CloudSQL instance containing the
          required configuration for local Google Cloud SQL development. If None
          then Cloud SQL will not be available.
      server_to_max_instances: A mapping between a server name and the maximum
          number of instances that can be created (this overrides the settings
          found in the configuration argument) e.g.
          {'default': 10, 'backend': 15}.
      use_mtime_file_watcher: A bool containing whether to use mtime polling to
          monitor file changes even if other options are available on the
          current platform.
      automatic_restart: If True then instances will be restarted when a
          file or configuration change that effects them is detected.
      allow_skipped_files: If True then all files in the application's directory
          are readable, even if they appear in a static handler or "skip_files"
          directive.
    """
    self._configuration = configuration
    self._php_executable_path = php_executable_path
    self._enable_php_remote_debugging = enable_php_remote_debugging
    self._python_config = python_config
    self._cloud_sql_config = cloud_sql_config
    self._request_data = None
    self._api_port = None
    self._running_servers = []
    self._server_configurations = {}
    self._host = host
    self._port = port
    self._auth_domain = auth_domain
    self._runtime_stderr_loglevel = runtime_stderr_loglevel
    self._server_name_to_server = {}
    self._dispatch_server = None
    self._quit_event = threading.Event()  # Set when quit() has been called.
    self._update_checking_thread = threading.Thread(
        target=self._loop_checking_for_updates)
    self._server_to_max_instances = server_to_max_instances or {}
    self._use_mtime_file_watcher = use_mtime_file_watcher
    self._automatic_restart = automatic_restart
    self._allow_skipped_files = allow_skipped_files
    self._executor = scheduled_executor.ScheduledExecutor(_THREAD_POOL)
    self._port_registry = PortRegistry()

  def start(self, api_port, request_data):
    """Starts the configured servers.

    Args:
      api_port: The port that APIServer listens for RPC requests on.
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
    """
    self._api_port = api_port
    self._request_data = request_data
    port = self._port
    self._executor.start()
    if self._configuration.dispatch:
      self._dispatch_server = wsgi_server.WsgiServer((self._host, port), self)
      self._dispatch_server.start()
      logging.info('Starting dispatcher running at: http://%s:%s', self._host,
                   self._dispatch_server.port)
      self._update_checking_thread.start()
      if port:
        port += 1
      self._port_registry.add(self._dispatch_server.port, None, None)
    for server_configuration in self._configuration.servers:
      self._server_configurations[
          server_configuration.server_name] = server_configuration
      servr, port = self._create_server(server_configuration, port)
      servr.start()
      self._server_name_to_server[server_configuration.server_name] = servr
      logging.info('Starting server "%s" running at: http://%s',
                   server_configuration.server_name, servr.balanced_address)

  @property
  def dispatch_port(self):
    """The port that the dispatch HTTP server for the Server is listening on."""
    assert self._dispatch_server, 'dispatch server not running'
    assert self._dispatch_server.ready, 'dispatch server not ready'
    return self._dispatch_server.port

  @property
  def host(self):
    """The host that the HTTP server for this Dispatcher is listening on."""
    return self._host

  @property
  def dispatch_address(self):
    """The address of the dispatch HTTP server e.g. "localhost:8080"."""
    if self.dispatch_port != 80:
      return '%s:%s' % (self.host, self.dispatch_port)
    else:
      return self.host

  def _check_for_updates(self):
    self._configuration.dispatch.check_for_updates()

  def _loop_checking_for_updates(self):
    """Loops until the Dispatcher exits, reloading dispatch.yaml config."""
    while not self._quit_event.is_set():
      self._check_for_updates()
      self._quit_event.wait(timeout=1)

  def quit(self):
    """Quits all servers."""
    self._executor.quit()
    self._quit_event.set()
    if self._dispatch_server:
      self._dispatch_server.quit()
    for servr in self._server_name_to_server.values():
      servr.quit()

  def _create_server(self, server_configuration, port):
    max_instances = self._server_to_max_instances.get(
        server_configuration.server_name)
    server_args = (server_configuration,
                   self._host,
                   port,
                   self._api_port,
                   self._auth_domain,
                   self._runtime_stderr_loglevel,
                   self._php_executable_path,
                   self._enable_php_remote_debugging,
                   self._python_config,
                   self._cloud_sql_config,
                   self._port,
                   self._port_registry,
                   self._request_data,
                   self,
                   max_instances,
                   self._use_mtime_file_watcher,
                   self._automatic_restart,
                   self._allow_skipped_files)
    if server_configuration.manual_scaling:
      servr = server.ManualScalingServer(*server_args)
    elif server_configuration.basic_scaling:
      servr = server.BasicScalingServer(*server_args)
    else:
      servr = server.AutoScalingServer(*server_args)

    if port != 0:
      port += 1
    return servr, port

  @property
  def servers(self):
    return self._server_name_to_server.values()

  def get_hostname(self, server_name, version, instance_id=None):
    """Returns the hostname for a (server, version, instance_id) tuple.

    If instance_id is set, this will return a hostname for that particular
    instances. Otherwise, it will return the hostname for load-balancing.

    Args:
      server_name: A str containing the name of the server.
      version: A str containing the version.
      instance_id: An optional str containing the instance ID.

    Returns:
      A str containing the hostname.

    Raises:
      request_info.ServerDoesNotExistError: The server does not exist.
      request_info.VersionDoesNotExistError: The version does not exist.
      request_info.InvalidInstanceIdError: The instance ID is not valid for the
          server/version or the server/version uses automatic scaling.
    """
    servr = self._get_server(server_name, version)
    if instance_id is None:
      return servr.balanced_address
    else:
      return servr.get_instance_address(instance_id)

  def get_server_names(self):
    """Returns a list of server names."""
    return list(self._server_name_to_server)

  def get_server_by_name(self, servr):
    """Returns the server with the given name.

    Args:
      servr: A str containing the name of the server.

    Returns:
      The server.Server with the provided name.

    Raises:
      request_info.ServerDoesNotExistError: The server does not exist.
    """
    try:
      return self._server_name_to_server[servr]
    except KeyError:
      raise request_info.ServerDoesNotExistError(servr)

  def get_versions(self, servr):
    """Returns a list of versions for a server.

    Args:
      servr: A str containing the name of the server.

    Returns:
      A list of str containing the versions for the specified server.

    Raises:
      request_info.ServerDoesNotExistError: The server does not exist.
    """
    if servr in self._server_configurations:
      return [self._server_configurations[servr].major_version]
    else:
      raise request_info.ServerDoesNotExistError(servr)

  def get_default_version(self, servr):
    """Returns the default version for a server.

    Args:
      servr: A str containing the name of the server.

    Returns:
      A str containing the default version for the specified server.

    Raises:
      request_info.ServerDoesNotExistError: The server does not exist.
    """
    if servr in self._server_configurations:
      return self._server_configurations[servr].major_version
    else:
      raise request_info.ServerDoesNotExistError(servr)

  def add_event(self, runnable, eta, service=None, event_id=None):
    """Add a callable to be run at the specified time.

    Args:
      runnable: A callable object to call at the specified time.
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
          This should be set if event_id is set.
      event_id: A str containing the id of the event. If set, this can be passed
          to update_event to change the time at which the event should run.
    """
    if service is not None and event_id is not None:
      key = (service, event_id)
    else:
      key = None
    self._executor.add_event(runnable, eta, key)

  def update_event(self, eta, service, event_id):
    """Update the eta of a scheduled event.

    Args:
      eta: An int containing the time to run the event, in seconds since the
          epoch.
      service: A str containing the name of the service that owns this event.
      event_id: A str containing the id of the event to update.
    """
    self._executor.update_event(eta, (service, event_id))

  def _get_server(self, server_name, version):
    if not server_name:
      server_name = 'default'
    if server_name not in self._server_name_to_server:
      raise request_info.ServerDoesNotExistError(server_name)
    elif (version is not None and
          version != self._server_configurations[server_name].major_version):
      raise request_info.VersionDoesNotExistError()
    return self._server_name_to_server[server_name]

  def set_num_instances(self, server_name, version, num_instances):
    """Sets the number of instances to run for a version of a server.

    Args:
      server_name: A str containing the name of the server.
      version: A str containing the version.
      num_instances: An int containing the number of instances to run.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    self._get_server(server_name, version).set_num_instances(num_instances)

  def get_num_instances(self, server_name, version):
    """Returns the number of instances running for a version of a server.

    Returns:
      An int containing the number of instances running for a server version.

    Args:
      server_name: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    return self._get_server(server_name, version).get_num_instances()

  def start_server(self, server_name, version):
    """Starts a server.

    Args:
      server_name: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    self._get_server(server_name, version).resume()

  def stop_server(self, server_name, version):
    """Stops a server.

    Args:
      server_name: A str containing the name of the server.
      version: A str containing the version.

    Raises:
      ServerDoesNotExistError: The server does not exist.
      VersionDoesNotExistError: The version does not exist.
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
    """
    self._get_server(server_name, version).suspend()

  def send_background_request(self, server_name, version, inst,
                              background_request_id):
    """Dispatch a background thread request.

    Args:
      server_name: A str containing the server name to service this
          request.
      version: A str containing the version to service this request.
      inst: The instance to service this request.
      background_request_id: A str containing the unique background thread
          request identifier.

    Raises:
      NotSupportedWithAutoScalingError: The provided server/version uses
          automatic scaling.
      BackgroundThreadLimitReachedError: The instance is at its background
          thread capacity.
    """
    servr = self._get_server(server_name, version)
    try:
      inst.reserve_background_thread()
    except instance.CannotAcceptRequests:
      raise request_info.BackgroundThreadLimitReachedError()
    port = servr.get_instance_port(inst.instance_id)
    environ = servr.build_request_environ(
        'GET', '/_ah/background',
        [('X-AppEngine-BackgroundRequest', background_request_id)],
        '', '0.1.0.3', port)
    _THREAD_POOL.submit(self._handle_request,
                        environ,
                        start_response_utils.null_start_response,
                        servr,
                        inst,
                        request_type=instance.BACKGROUND_REQUEST,
                        catch_and_log_exceptions=True)

  # TODO: Think of better names for add_async_request and
  # add_request.
  def add_async_request(self, method, relative_url, headers, body, source_ip,
                        server_name=None, version=None, instance_id=None):
    """Dispatch an HTTP request asynchronously.

    Args:
      method: A str containing the HTTP method of the request.
      relative_url: A str containing path and query string of the request.
      headers: A list of (key, value) tuples where key and value are both str.
      body: A str containing the request body.
      source_ip: The source ip address for the request.
      server_name: An optional str containing the server name to service this
          request. If unset, the request will be dispatched to the default
          server.
      version: An optional str containing the version to service this request.
          If unset, the request will be dispatched to the default version.
      instance_id: An optional str containing the instance_id of the instance to
          service this request. If unset, the request will be dispatched to
          according to the load-balancing for the server and version.
    """
    if server_name:
      servr = self._get_server(server_name, version)
    else:
      servr = self._server_for_request(urlparse.urlsplit(relative_url).path)
    inst = servr.get_instance(instance_id) if instance_id else None
    port = servr.get_instance_port(instance_id) if instance_id else (
        servr.balanced_port)
    environ = servr.build_request_environ(method, relative_url, headers, body,
                                          source_ip, port)

    _THREAD_POOL.submit(self._handle_request,
                        environ,
                        start_response_utils.null_start_response,
                        servr,
                        inst,
                        catch_and_log_exceptions=True)

  def add_request(self, method, relative_url, headers, body, source_ip,
                  server_name=None, version=None, instance_id=None,
                  fake_login=False):
    """Process an HTTP request.

    Args:
      method: A str containing the HTTP method of the request.
      relative_url: A str containing path and query string of the request.
      headers: A list of (key, value) tuples where key and value are both str.
      body: A str containing the request body.
      source_ip: The source ip address for the request.
      server_name: An optional str containing the server name to service this
          request. If unset, the request will be dispatched according to the
          host header and relative_url.
      version: An optional str containing the version to service this request.
          If unset, the request will be dispatched according to the host header
          and relative_url.
      instance_id: An optional str containing the instance_id of the instance to
          service this request. If unset, the request will be dispatched
          according to the host header and relative_url and, if applicable, the
          load-balancing for the server and version.
      fake_login: A bool indicating whether login checks should be bypassed,
          i.e. "login: required" should be ignored for this request.

    Returns:
      A request_info.ResponseTuple containing the response information for the
      HTTP request.
    """
    if server_name:
      servr = self._get_server(server_name, version)
      inst = servr.get_instance(instance_id) if instance_id else None
    else:
      headers_dict = wsgiref.headers.Headers(headers)
      servr, inst = self._resolve_target(
          headers_dict['Host'], urlparse.urlsplit(relative_url).path)
    if inst:
      try:
        port = servr.get_instance_port(inst.instance_id)
      except request_info.NotSupportedWithAutoScalingError:
        port = servr.balanced_port
    else:
      port = servr.balanced_port
    environ = servr.build_request_environ(method, relative_url, headers, body,
                                          source_ip, port,
                                          fake_login=fake_login)
    start_response = start_response_utils.CapturingStartResponse()
    response = self._handle_request(environ,
                                    start_response,
                                    servr,
                                    inst)
    return request_info.ResponseTuple(start_response.status,
                                      start_response.response_headers,
                                      start_response.merged_response(response))

  def _resolve_target(self, hostname, path):
    """Returns the server and instance that should handle this request.

    Args:
      hostname: A string containing the value of the host header in the request
          or None if one was not present.
      path: A string containing the path of the request.

    Returns:
      A tuple (servr, inst) where:
        servr: The server.Server that should handle this request.
        inst: The instance.Instance that should handle this request or None if
            the server's load balancing should decide on the instance.

    Raises:
      request_info.ServerDoesNotExistError: if hostname is not known.
    """
    if self._port == 80:
      default_address = self.host
    else:
      default_address = '%s:%s' % (self.host, self._port)
    if not hostname or hostname == default_address:
      return self._server_for_request(path), None

    default_address_offset = hostname.find(default_address)
    if default_address_offset > 0:
      prefix = hostname[:default_address_offset - 1]
      if '.' in prefix:
        raise request_info.ServerDoesNotExistError(prefix)
      return self._get_server(prefix, None), None

    else:
      if ':' in hostname:
        port = int(hostname.split(':', 1)[1])
      else:
        port = 80
      try:
        servr, inst = self._port_registry.get(port)
      except KeyError:
        raise request_info.ServerDoesNotExistError(hostname)
    if not servr:
      servr = self._server_for_request(path)
    return servr, inst

  def _handle_request(self, environ, start_response, servr,
                      inst=None, request_type=instance.NORMAL_REQUEST,
                      catch_and_log_exceptions=False):
    """Dispatch a WSGI request.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      servr: The server to dispatch this request to.
      inst: The instance to service this request. If None, the server will
          be left to choose the instance to serve this request.
      request_type: The request_type of this request. See instance.*_REQUEST
          module constants.
      catch_and_log_exceptions: A bool containing whether to catch and log
          exceptions in handling the request instead of leaving it for the
          caller to handle.

    Returns:
      An iterable over the response to the request as defined in PEP-333.
    """
    try:
      return servr._handle_request(environ, start_response, inst=inst,
                                   request_type=request_type)
    except:
      if catch_and_log_exceptions:
        logging.exception('Internal error while handling request.')
      else:
        raise

  def __call__(self, environ, start_response):
    return self._handle_request(
        environ, start_response, self._server_for_request(environ['PATH_INFO']))

  def _server_for_request(self, path):
    dispatch = self._configuration.dispatch
    if dispatch:
      for url, server_name in dispatch.dispatch:
        if (url.path_exact and path == url.path or
            not url.path_exact and path.startswith(url.path)):
          return self._get_server(server_name, None)
    return self._get_server(None, None)
