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


import argparse
import errno
import getpass
import itertools
import logging
import os
import sys
import tempfile
import time

from google.appengine.datastore import datastore_stub_util
from google.appengine.tools import boolean_action
from google.appengine.tools.devappserver2.admin import admin_server
from google.appengine.tools.devappserver2 import api_server
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import update_checker
from google.appengine.tools.devappserver2 import wsgi_request_info

# Initialize logging early -- otherwise some library packages may
# pre-empt our log formatting.  NOTE: the level is provisional; it may
# be changed in main() based on the --debug flag.
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')

# Valid choices for --log_level and their corresponding constants in
# runtime_config_pb2.Config.stderr_log_level.
_LOG_LEVEL_TO_RUNTIME_CONSTANT = {
    'debug': 0,
    'info': 1,
    'warning': 2,
    'error': 3,
    'critical': 4,
}

# Valid choices for --dev_appserver_log_level and their corresponding Python
# logging levels
_LOG_LEVEL_TO_PYTHON_CONSTANT = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}


def _generate_storage_paths(app_id):
  """Yield an infinite sequence of possible storage paths."""
  if sys.platform == 'win32':
    # The temp directory is per-user on Windows so there is no reason to add
    # the username to the generated directory name.
    user_format = ''
  else:
    try:
      user_name = getpass.getuser()
    except Exception:  # The possible set of exceptions is not documented.
      user_format = ''
    else:
      user_format = '.%s' % user_name

  tempdir = tempfile.gettempdir()
  yield os.path.join(tempdir, 'appengine.%s%s' % (app_id, user_format))
  for i in itertools.count(1):
    yield os.path.join(tempdir, 'appengine.%s%s.%d' % (app_id, user_format, i))


def _get_storage_path(path, app_id):
  """Returns a path to the directory where stub data can be stored."""
  _, _, app_id = app_id.replace(':', '_').rpartition('~')
  if path is None:
    for path in _generate_storage_paths(app_id):
      try:
        os.mkdir(path, 0700)
      except OSError, e:
        if e.errno == errno.EEXIST:
          # Check that the directory is only accessable by the current user to
          # protect against an attacker creating the directory in advance in
          # order to access any created files. Windows has per-user temporary
          # directories and st_mode does not include per-user permission
          # information so assume that it is safe.
          if sys.platform == 'win32' or (
              (os.stat(path).st_mode & 0777) == 0700 and os.path.isdir(path)):
            return path
          else:
            continue
        raise
      else:
        return path
  elif not os.path.exists(path):
    os.mkdir(path)
    return path
  elif not os.path.isdir(path):
    raise IOError('the given storage path %r is a file, a directory was '
                  'expected' % path)
  else:
    return path


class PortParser(object):
  """A parser for ints that represent ports."""

  def __init__(self, allow_port_zero=True):
    self._min_port = 0 if allow_port_zero else 1

  def __call__(self, value):
    try:
      port = int(value)
    except ValueError:
      raise argparse.ArgumentTypeError('Invalid port: %r' % value)
    if port < self._min_port or port >= (1 << 16):
      raise argparse.ArgumentTypeError('Invalid port: %d' % port)
    return port


def parse_max_server_instances(value):
  """Returns the parsed value for the --max_server_instances flag.

  Args:
    value: A str containing the flag value for parse. The format should follow
        one of the following examples:
          1. "5" - All servers are limited to 5 instances.
          2. "default:3,backend:20" - The default server can have 3 instances,
             "backend" can have 20 instances and all other servers are
              unaffected.
  """
  if ':' not in value:
    try:
      max_server_instances = int(value)
    except ValueError:
      raise argparse.ArgumentTypeError('Invalid instance count: %r' % value)
    else:
      if not max_server_instances:
        raise argparse.ArgumentTypeError(
            'Cannot specify zero instances for all servers')
      return max_server_instances
  else:
    server_to_max_instances = {}
    for server_instance_max in value.split(','):
      try:
        server_name, max_instances = server_instance_max.split(':')
        max_instances = int(max_instances)
      except ValueError:
        raise argparse.ArgumentTypeError(
            'Expected "server:max_instances": %r' % server_instance_max)
      else:
        server_name = server_name.strip()
        if server_name in server_to_max_instances:
          raise argparse.ArgumentTypeError(
              'Duplicate max instance value: %r' % server_name)
        server_to_max_instances[server_name] = max_instances
    return server_to_max_instances


def create_command_line_parser():
  """Returns an argparse.ArgumentParser to parse command line arguments."""
  # TODO: Add more robust argument validation. Consider what flags
  # are actually needed.

  parser = argparse.ArgumentParser(
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('yaml_files', nargs='+')

  common_group = parser.add_argument_group('Common')
  common_group.add_argument(
      '--host', default='localhost',
      help='host name to which application servers should bind')
  common_group.add_argument(
      '--port', type=PortParser(), default=8080,
      help='lowest port to which application servers should bind')
  common_group.add_argument(
      '--admin_host', default='localhost',
      help='host name to which the admin server should bind')
  common_group.add_argument(
      '--admin_port', type=PortParser(), default=8000,
      help='port to which the admin server should bind')
  common_group.add_argument(
      '--auth_domain', default='gmail.com',
      help='name of the authorization domain to use')
  common_group.add_argument(
      '--storage_path', metavar='PATH',
      type=os.path.expanduser,
      help='path to the data (datastore, blobstore, etc.) associated with the '
      'application.')
  common_group.add_argument(
      '--log_level', default='info',
      choices=_LOG_LEVEL_TO_RUNTIME_CONSTANT.keys(),
      help='the log level below which logging messages generated by '
      'application code will not be displayed on the console')
  common_group.add_argument(
      '--max_server_instances',
      type=parse_max_server_instances,
      help='the maximum number of runtime instances that can be started for a '
      'particular server - the value can be an integer, in what case all '
      'servers are limited to that number of instances or a comma-seperated '
      'list of server:max_instances e.g. "default:5,backend:3"')
  common_group.add_argument(
      '--use_mtime_file_watcher',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='use mtime polling for detecting source code changes - useful if '
      'modifying code from a remote machine using a distributed file system')

  # PHP
  php_group = parser.add_argument_group('PHP')
  php_group.add_argument('--php_executable_path', metavar='PATH',
                         help='path to the PHP executable',
                         default='php-cgi')
  php_group.add_argument('--php_remote_debugging',
                         action=boolean_action.BooleanAction,
                         const=True,
                         default=False,
                         help='enable XDebug remote debugging')

  # Python
  python_group = parser.add_argument_group('Python')
  python_group.add_argument(
      '--python_startup_script',
      help='the script to run at the startup of new Python runtime instances '
      '(useful for tools such as debuggers.')
  python_group.add_argument(
      '--python_startup_args',
      help='the arguments made available to the script specified in '
      '--python_startup_script.')

  # Blobstore
  blobstore_group = parser.add_argument_group('Blobstore API')
  blobstore_group.add_argument(
      '--blobstore_path',
      type=os.path.expanduser,
      help='path to directory used to store blob contents '
      '(defaults to a subdirectory of --storage_path if not set)',
      default=None)

  # Cloud SQL
  cloud_sql_group = parser.add_argument_group('Cloud SQL')
  cloud_sql_group.add_argument(
      '--mysql_host',
      default='localhost',
      help='host name of a running MySQL server used for simulated Google '
      'Cloud SQL storage')
  cloud_sql_group.add_argument(
      '--mysql_port', type=PortParser(allow_port_zero=False),
      default=3306,
      help='port number of a running MySQL server used for simulated Google '
      'Cloud SQL storage')
  cloud_sql_group.add_argument(
      '--mysql_user',
      default='',
      help='username to use when connecting to the MySQL server specified in '
      '--mysql_host and --mysql_port or --mysql_socket')
  cloud_sql_group.add_argument(
      '--mysql_password',
      default='',
      help='passpord to use when connecting to the MySQL server specified in '
      '--mysql_host and --mysql_port or --mysql_socket')
  cloud_sql_group.add_argument(
      '--mysql_socket',
      help='path to a Unix socket file to use when connecting to a running '
      'MySQL server used for simulated Google Cloud SQL storage')

  # Datastore
  datastore_group = parser.add_argument_group('Datastore API')
  datastore_group.add_argument(
      '--datastore_path',
      type=os.path.expanduser,
      default=None,
      help='path to a file used to store datastore contents '
      '(defaults to a file in --storage_path if not set)',)
  datastore_group.add_argument('--clear_datastore',
                               action=boolean_action.BooleanAction,
                               const=True,
                               default=False,
                               help='clear the datastore on startup')
  datastore_group.add_argument(
      '--datastore_consistency_policy',
      default='time',
      choices=['consistent', 'random', 'time'],
      help='the policy to apply when deciding whether a datastore write should '
      'appear in global queries')
  datastore_group.add_argument(
      '--require_indexes',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='generate an error on datastore queries that '
      'requires a composite index not found in index.yaml')
  datastore_group.add_argument(
      '--auto_id_policy',
      default=datastore_stub_util.SCATTERED,
      choices=[datastore_stub_util.SEQUENTIAL,
               datastore_stub_util.SCATTERED],
      help='the type of sequence from which the datastore stub '
      'assigns automatic IDs. NOTE: Sequential IDs are '
      'deprecated. This flag will be removed in a future '
      'release. Please do not rely on sequential IDs in your '
      'tests.')

  # Logs
  logs_group = parser.add_argument_group('Logs API')
  logs_group.add_argument(
      '--logs_path', default=None,
      help='path to a file used to store request logs (defaults to a file in '
      '--storage_path if not set)',)

  # Mail
  mail_group = parser.add_argument_group('Mail API')
  mail_group.add_argument(
      '--show_mail_body',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='logs the contents of e-mails sent using the Mail API')
  mail_group.add_argument(
      '--enable_sendmail',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='use the "sendmail" tool to transmit e-mail sent '
      'using the Mail API (ignored if --smpt_host is set)')
  mail_group.add_argument(
      '--smtp_host', default='',
      help='host name of an SMTP server to use to transmit '
      'e-mail sent using the Mail API')
  mail_group.add_argument(
      '--smtp_port', default=25,
      type=PortParser(allow_port_zero=False),
      help='port number of an SMTP server to use to transmit '
      'e-mail sent using the Mail API (ignored if --smtp_host '
      'is not set)')
  mail_group.add_argument(
      '--smtp_user', default='',
      help='username to use when connecting to the SMTP server '
      'specified in --smtp_host and --smtp_port')
  mail_group.add_argument(
      '--smtp_password', default='',
      help='password to use when connecting to the SMTP server '
      'specified in --smtp_host and --smtp_port')

  # Matcher
  prospective_search_group = parser.add_argument_group('Prospective Search API')
  prospective_search_group.add_argument(
      '--prospective_search_path', default=None,
      type=os.path.expanduser,
      help='path to a file used to store the prospective '
      'search subscription index (defaults to a file in '
      '--storage_path if not set)')
  prospective_search_group.add_argument(
      '--clear_prospective_search',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='clear the prospective search subscription index')

  # Search
  search_group = parser.add_argument_group('Search API')
  search_group.add_argument(
      '--search_indexes_path', default=None,
      type=os.path.expanduser,
      help='path to a file used to store search indexes '
      '(defaults to a file in --storage_path if not set)',)
  search_group.add_argument(
      '--clear_search_indexes',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='clear the search indexes')

  # Taskqueue
  taskqueue_group = parser.add_argument_group('Task Queue API')
  taskqueue_group.add_argument(
      '--enable_task_running',
      action=boolean_action.BooleanAction,
      const=True,
      default=True,
      help='run "push" tasks created using the taskqueue API automatically')

  # Misc
  misc_group = parser.add_argument_group('Miscellaneous')
  misc_group.add_argument(
      '--allow_skipped_files',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='make files specified in the app.yaml "skip_files" or "static"'
      'handles readable by the application.')
  misc_group.add_argument(
      '--api_port', type=PortParser(), default=0,
      help='port to which the server for API calls should bind')
  misc_group.add_argument(
      '--automatic_restart',
      action=boolean_action.BooleanAction,
      const=True,
      default=True,
      help=('restart instances automatically when files relevant to their '
            'server are changed'))
  misc_group.add_argument(
      '--dev_appserver_log_level', default='info',
      choices=_LOG_LEVEL_TO_PYTHON_CONSTANT.keys(),
      help='the log level below which logging messages generated by '
      'the development server will not be displayed on the console (this '
      'flag is more useful for diagnosing problems in dev_appserver.py rather '
      'than in application code)')
  misc_group.add_argument(
      '--skip_sdk_update_check',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='skip checking for SDK updates (if false, use .appcfg_nag to '
      'decide)')


  return parser

PARSER = create_command_line_parser()


def _clear_datastore_storage(datastore_path):
  """Delete the datastore storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(datastore_path):
    try:
      os.remove(datastore_path)
    except OSError, e:
      logging.warning('Failed to remove datastore file %r: %s',
                      datastore_path,
                      e)


def _clear_prospective_search_storage(prospective_search_path):
  """Delete the perspective search storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(prospective_search_path):
    try:
      os.remove(prospective_search_path)
    except OSError, e:
      logging.warning('Failed to remove prospective search file %r: %s',
                      prospective_search_path,
                      e)


def _clear_search_indexes_storage(search_index_path):
  """Delete the search indexes storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(search_index_path):
    try:
      os.remove(search_index_path)
    except OSError, e:
      logging.warning('Failed to remove search indexes file %r: %s',
                      search_index_path,
                      e)


def _setup_environ(app_id):
  """Sets up the os.environ dictionary for the front-end server and API server.

  This function should only be called once.

  Args:
    app_id: The id of the application.
  """
  os.environ['APPLICATION_ID'] = app_id


class DevelopmentServer(object):
  """Encapsulates the logic for the development server.

  Only a single instance of the class may be created per process. See
  _setup_environ.
  """

  def __init__(self):
    # A list of servers that are currently running.
    self._running_servers = []
    self._server_to_port = {}

  def server_to_address(self, server_name, instance=None):
    """Returns the address of a server."""
    if server_name is None:
      return self._dispatcher.dispatch_address
    return self._dispatcher.get_hostname(
        server_name,
        self._dispatcher.get_default_version(server_name),
        instance)

  def start(self, options):
    """Start devappserver2 servers based on the provided command line arguments.

    Args:
      options: An argparse.Namespace containing the command line arguments.
    """
    logging.getLogger().setLevel(
        _LOG_LEVEL_TO_PYTHON_CONSTANT[options.dev_appserver_log_level])

    configuration = application_configuration.ApplicationConfiguration(
        options.yaml_files)

    if options.skip_sdk_update_check:
      logging.info('Skipping SDK update check.')
    else:
      update_checker.check_for_updates(configuration)

    if options.port == 0:
      logging.warn('DEFAULT_VERSION_HOSTNAME will not be set correctly with '
                   '--port=0')

    _setup_environ(configuration.app_id)

    python_config = runtime_config_pb2.PythonConfig()
    if options.python_startup_script:
      python_config.startup_script = os.path.abspath(
          options.python_startup_script)
      if options.python_startup_args:
        python_config.startup_args = options.python_startup_args

    cloud_sql_config = runtime_config_pb2.CloudSQL()
    cloud_sql_config.mysql_host = options.mysql_host
    cloud_sql_config.mysql_port = options.mysql_port
    cloud_sql_config.mysql_user = options.mysql_user
    cloud_sql_config.mysql_password = options.mysql_password
    if options.mysql_socket:
      cloud_sql_config.mysql_socket = options.mysql_socket

    if options.max_server_instances is None:
      server_to_max_instances = {}
    elif isinstance(options.max_server_instances, int):
      server_to_max_instances = {
          server_configuration.server_name: options.max_server_instances
          for server_configuration in configuration.servers}
    else:
      server_to_max_instances = options.max_server_instances

    self._dispatcher = dispatcher.Dispatcher(
        configuration,
        options.host,
        options.port,
        options.auth_domain,
        _LOG_LEVEL_TO_RUNTIME_CONSTANT[options.log_level],
        options.php_executable_path,
        options.php_remote_debugging,
        python_config,
        cloud_sql_config,
        server_to_max_instances,
        options.use_mtime_file_watcher,
        options.automatic_restart,
        options.allow_skipped_files)

    request_data = wsgi_request_info.WSGIRequestInfo(self._dispatcher)

    storage_path = _get_storage_path(options.storage_path, configuration.app_id)
    datastore_path = options.datastore_path or os.path.join(storage_path,
                                                            'datastore.db')
    logs_path = options.logs_path or os.path.join(storage_path, 'logs.db')
    xsrf_path = os.path.join(storage_path, 'xsrf')

    search_index_path = options.search_indexes_path or os.path.join(
        storage_path, 'search_indexes')

    prospective_search_path = options.prospective_search_path or os.path.join(
        storage_path, 'prospective-search')

    blobstore_path = options.blobstore_path or os.path.join(storage_path,
                                                            'blobs')

    if options.clear_datastore:
      _clear_datastore_storage(datastore_path)

    if options.clear_prospective_search:
      _clear_prospective_search_storage(prospective_search_path)

    if options.clear_search_indexes:
      _clear_search_indexes_storage(search_index_path)

    if options.auto_id_policy==datastore_stub_util.SEQUENTIAL:
      logging.warn("--auto_id_policy='sequential' is deprecated. This option "
                   "will be removed in a future release.")

    application_address = '%s' % options.host
    if options.port and options.port != 80:
      application_address += ':' + str(options.port)

    user_login_url = '/%s?%s=%%s' % (login.LOGIN_URL_RELATIVE,
                                     login.CONTINUE_PARAM)
    user_logout_url = '%s&%s=%s' % (user_login_url, login.ACTION_PARAM,
                                    login.LOGOUT_ACTION)

    if options.datastore_consistency_policy == 'time':
      consistency = datastore_stub_util.TimeBasedHRConsistencyPolicy()
    elif options.datastore_consistency_policy == 'random':
      consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy()
    elif options.datastore_consistency_policy == 'consistent':
      consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy(1.0)
    else:
      assert 0, ('unknown consistency policy: %r' %
                 options.datastore_consistency_policy)

    api_server.maybe_convert_datastore_file_stub_data_to_sqlite(
        configuration.app_id, datastore_path)
    api_server.setup_stubs(
        request_data=request_data,
        app_id=configuration.app_id,
        application_root=configuration.servers[0].application_root,
        # The "trusted" flag is only relevant for Google administrative
        # applications.
        trusted=getattr(options, 'trusted', False),
        blobstore_path=blobstore_path,
        datastore_path=datastore_path,
        datastore_consistency=consistency,
        datastore_require_indexes=options.require_indexes,
        datastore_auto_id_policy=options.auto_id_policy,
        images_host_prefix='http://%s' % application_address,
        logs_path=logs_path,
        mail_smtp_host=options.smtp_host,
        mail_smtp_port=options.smtp_port,
        mail_smtp_user=options.smtp_user,
        mail_smtp_password=options.smtp_password,
        mail_enable_sendmail=options.enable_sendmail,
        mail_show_mail_body=options.show_mail_body,
        matcher_prospective_search_path=prospective_search_path,
        search_index_path=search_index_path,
        taskqueue_auto_run_tasks=options.enable_task_running,
        taskqueue_default_http_server=application_address,
        user_login_url=user_login_url,
        user_logout_url=user_logout_url)

    # The APIServer must bind to localhost because that is what the runtime
    # instances talk to.
    apis = api_server.APIServer('localhost', options.api_port,
                                configuration.app_id)
    apis.start()
    self._running_servers.append(apis)

    self._running_servers.append(self._dispatcher)
    self._dispatcher.start(apis.port, request_data)

    admin = admin_server.AdminServer(options.admin_host, options.admin_port,
                                     self._dispatcher, configuration, xsrf_path)
    admin.start()
    self._running_servers.append(admin)

  def stop(self):
    """Stops all running devappserver2 servers."""
    while self._running_servers:
      self._running_servers.pop().quit()


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
  dev_server = DevelopmentServer()
  try:
    dev_server.start(options)
    shutdown.wait_until_shutdown()
  finally:
    dev_server.stop()


if __name__ == '__main__':
  main()
