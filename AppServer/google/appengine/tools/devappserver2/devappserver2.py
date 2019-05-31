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
"""The main entry point for the new development server."""


import logging
import os
import time

from google.appengine.tools.devappserver2.admin import admin_server
from google.appengine.tools.devappserver2 import api_server
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import cli_parser
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import update_checker
from google.appengine.tools.devappserver2 import wsgi_request_info

from appscale.common import appscale_info

# Initialize logging early -- otherwise some library packages may
# pre-empt our log formatting.  NOTE: the level is provisional; it may
# be changed in main() based on the --debug flag.
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')


PARSER = cli_parser.create_command_line_parser(
    cli_parser.DEV_APPSERVER_CONFIGURATION)


def _setup_environ(app_id, version_info):
  """Sets up the os.environ dictionary for the front-end server and API server.

  This function should only be called once.

  Args:
    app_id: The id of the application.
    version_info: A string in the form of either major_version.minor_version or
      service_id:major_version.minor_version.
  """
  os.environ['APPLICATION_ID'] = app_id

  # AppScale: Define environment variables that the runtime uses so that the
  # API Server can infer the running service ID and version ID.
  if ':' in version_info:
    service_id, version_id = version_info.split(':')
  else:
    service_id = 'default'
    version_id = version_info

  os.environ['CURRENT_MODULE_ID'] = service_id
  os.environ['CURRENT_VERSION_ID'] = version_id


class DevelopmentServer(object):
  """Encapsulates the logic for the development server.

  Only a single instance of the class may be created per process. See
  _setup_environ.
  """

  def __init__(self):
    # A list of servers that are currently running.
    self._running_modules = []
    self._module_to_port = {}

  def module_to_address(self, module_name, instance=None):
    """Returns the address of a module."""
    if module_name is None:
      return self._dispatcher.dispatch_address
    return self._dispatcher.get_hostname(
        module_name,
        self._dispatcher.get_default_version(module_name),
        instance)

  def start(self, options):
    """Start devappserver2 servers based on the provided command line arguments.

    Args:
      options: An argparse.Namespace containing the command line arguments.
    """
    logging.getLogger().setLevel(
        constants.LOG_LEVEL_TO_PYTHON_CONSTANT[options.dev_appserver_log_level])

    configuration = application_configuration.ApplicationConfiguration(
        options.config_paths, options.app_id)

    if options.skip_sdk_update_check:
      logging.info('Skipping SDK update check.')
    else:
      update_checker.check_for_updates(configuration)

    if options.port == 0:
      logging.warn('DEFAULT_VERSION_HOSTNAME will not be set correctly with '
                   '--port=0')

    _setup_environ(configuration.app_id, configuration.modules[0].version_id)

    python_config = runtime_config_pb2.PythonConfig()
    if options.python_startup_script:
      python_config.startup_script = os.path.abspath(
          options.python_startup_script)
      if options.python_startup_args:
        python_config.startup_args = options.python_startup_args

    php_executable_path = (options.php_executable_path and
                           os.path.abspath(options.php_executable_path))
    cloud_sql_config = runtime_config_pb2.CloudSQL()
    cloud_sql_config.mysql_host = options.mysql_host
    cloud_sql_config.mysql_port = options.mysql_port
    cloud_sql_config.mysql_user = options.mysql_user
    cloud_sql_config.mysql_password = options.mysql_password
    if options.mysql_socket:
      cloud_sql_config.mysql_socket = options.mysql_socket

    if options.max_module_instances is None:
      module_to_max_instances = {}
    elif isinstance(options.max_module_instances, int):
      module_to_max_instances = {
          module_configuration.module_name: options.max_module_instances
          for module_configuration in configuration.modules}
    else:
      module_to_max_instances = options.max_module_instances

    if options.threadsafe_override is None:
      module_to_threadsafe_override = {}
    elif isinstance(options.threadsafe_override, bool):
      module_to_threadsafe_override = {
          module_configuration.module_name: options.threadsafe_override
          for module_configuration in configuration.modules}
    else:
      module_to_threadsafe_override = options.threadsafe_override

    self._dispatcher = dispatcher.Dispatcher(
        configuration,
        options.host,
        options.port,
        options.auth_domain,
        constants.LOG_LEVEL_TO_RUNTIME_CONSTANT[options.log_level],
        php_executable_path,
        options.php_remote_debugging,
        python_config,
        cloud_sql_config,
        module_to_max_instances,
        options.use_mtime_file_watcher,
        options.automatic_restart,
        options.allow_skipped_files,
        module_to_threadsafe_override)

    request_data = wsgi_request_info.WSGIRequestInfo(self._dispatcher)
    storage_path = api_server.get_storage_path(
        options.storage_path, configuration.app_id)

    apis = api_server.create_api_server(
        request_data, storage_path, options, configuration.app_id,
        configuration.modules[0].application_root)
    apis.start()
    self._running_modules.append(apis)

    self._dispatcher.start(apis.port, request_data)
    self._running_modules.append(self._dispatcher)

    # AppScale: do not run admin server, dashboard provides admin functionality
    #xsrf_path = os.path.join(storage_path, 'xsrf')
    #admin = admin_server.AdminServer(options.admin_host, options.admin_port,
    #                                 self._dispatcher, configuration, xsrf_path)
    #admin.start()
    #self._running_modules.append(admin)

  def stop(self):
    """Stops all running devappserver2 modules."""
    while self._running_modules:
      self._running_modules.pop().quit()


def main():
  shutdown.install_signal_handlers()
  # The timezone must be set in the devappserver2 process rather than just in
  # the runtime so printed log timestamps are consistent and the taskqueue stub
  # expects the timezone to be UTC. The runtime inherits the environment.
  os.environ['TZ'] = 'UTC'
  if hasattr(time, 'tzset'):
    # time.tzet() should be called on Unix, but doesn't exist on Windows.
    time.tzset()
  options = PARSER.parse_args()
  os.environ['MY_IP_ADDRESS'] = options.host
  os.environ['MY_PORT'] = str(options.port)
  os.environ['COOKIE_SECRET'] = appscale_info.get_secret()
  os.environ['NGINX_HOST'] = options.nginx_host

  if options.pidfile:
    with open(options.pidfile, 'w') as pidfile:
      pidfile.write(str(os.getpid()))

  dev_server = DevelopmentServer()
  try:
    dev_server.start(options)
    shutdown.wait_until_shutdown()
  finally:
    dev_server.stop()


if __name__ == '__main__':
  main()
