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
"""Provides a command line parser for the dev_appserver and related tools.

The standard argparse library is subclassed within to provide configurability to
the parser and argument group __init__ and add_argument methods. This is a
convenient way to share flags between tools, eg dev_appserver.py and
api_server.py binaries, and to toggle flags on and off for certain tools.

The create_command_line_parser accepts a configuration argument:
  create_command_line_parser(DEV_APPSERVER_CONFIGURATION): returns a parser with
      all flags for the dev_appserver.py binary.
  create_command_line_parser(API_SERVER_CONFIGURATION): returns a parser with
      all flags for the api_server.py binary.
"""

import argparse
import os
import sys

from google.appengine.api import appinfo
from google.appengine.datastore import datastore_stub_util
from google.appengine.tools import boolean_action
from google.appengine.tools.devappserver2 import constants


# Configuration tokens used to determine which arguments are added to the
# parser.
DEV_APPSERVER_CONFIGURATION = 'dev_appserver_configuration'
API_SERVER_CONFIGURATION = 'api_server_configuration'


def _get_default_php_path():
  """Returns the path to the siloed php-cgi binary or None if not present."""
  if sys.platform == 'win32':
    default_php_executable_path = os.path.abspath(
        os.path.join(os.path.dirname(sys.argv[0]),
                     'php/php-5.4.15-Win32-VC9-x86/php-cgi.exe'))
    if os.path.exists(default_php_executable_path):
      return default_php_executable_path

  return None


class PortParser(object):
  """An argparse type parser for ints that represent ports."""

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


def parse_per_module_option(
    value, value_type, value_predicate,
    single_bad_type_error, single_bad_predicate_error,
    multiple_bad_type_error, multiple_bad_predicate_error,
    multiple_duplicate_module_error):
  """Parses command line options that may be specified per-module.

  Args:
    value: A str containing the flag value to parse. Two formats are supported:
        1. A universal value (may not contain a colon as that is use to
           indicate a per-module value).
        2. Per-module values. One or more comma separated module-value pairs.
           Each pair is a module_name:value. An empty module-name is shorthand
           for "default" to match how not specifying a module name in the yaml
           is the same as specifying "module: default".
    value_type: a callable that converts the string representation of the value
        to the actual value. Should raise ValueError if the string can not
        be converted.
    value_predicate: a predicate to call on the converted value to validate
        the converted value. Use "lambda _: True" if all values are valid.
    single_bad_type_error: the message to use if a universal value is provided
        and value_type throws a ValueError. The message must consume a single
        format parameter (the provided value).
    single_bad_predicate_error: the message to use if a universal value is
        provided and value_predicate returns False. The message does not
        get any format parameters.
    multiple_bad_type_error: the message to use if a per-module value
        either does not have two values separated by a single colon or if
        value_types throws a ValueError on the second string. The message must
        consume a single format parameter (the module_name:value pair).
    multiple_bad_predicate_error: the message to use if a per-module value if
        value_predicate returns False. The message must consume a single format
        parameter (the module name).
    multiple_duplicate_module_error: the message to use if the same module is
        repeated. The message must consume a single formater parameter (the
        module name).

  Returns:
    Either a single value of value_type for universal values or a dict of
    str->value_type for per-module values.

  Raises:
    argparse.ArgumentTypeError: the value is invalid.
  """
  if ':' not in value:
    try:
      single_value = value_type(value)
    except ValueError:
      raise argparse.ArgumentTypeError(single_bad_type_error % value)
    else:
      if not value_predicate(single_value):
        raise argparse.ArgumentTypeError(single_bad_predicate_error)
      return single_value
  else:
    module_to_value = {}
    for module_value in value.split(','):
      try:
        module_name, single_value = module_value.split(':')
        single_value = value_type(single_value)
      except ValueError:
        raise argparse.ArgumentTypeError(multiple_bad_type_error % module_value)
      else:
        module_name = module_name.strip()
        if not module_name:
          module_name = appinfo.DEFAULT_MODULE
        if module_name in module_to_value:
          raise argparse.ArgumentTypeError(
              multiple_duplicate_module_error % module_name)
        if not value_predicate(single_value):
          raise argparse.ArgumentTypeError(
              multiple_bad_predicate_error % module_name)
        module_to_value[module_name] = single_value
    return module_to_value


def parse_max_module_instances(value):
  """Returns the parsed value for the --max_module_instances flag.

  Args:
    value: A str containing the flag value for parse. The format should follow
        one of the following examples:
          1. "5" - All modules are limited to 5 instances.
          2. "default:3,backend:20" - The default module can have 3 instances,
             "backend" can have 20 instances and all other modules are
              unaffected. An empty name (i.e. ":3") is shorthand for default
              to match how not specifying a module name in the yaml is the
              same as specifying "module: default".
  Returns:
    The parsed value of the max_module_instances flag. May either be an int
    (for values of the form "5") or a dict of str->int (for values of the
    form "default:3,backend:20").

  Raises:
    argparse.ArgumentTypeError: the value is invalid.
  """
  return parse_per_module_option(
      value, int, lambda instances: instances > 0,
      'Invalid max instance count: %r',
      'Max instance count must be greater than zero',
      'Expected "module:max_instance_count": %r',
      'Max instance count for module %s must be greater than zero',
      'Duplicate max instance count for module %s')


def parse_threadsafe_override(value):
  """Returns the parsed value for the --threadsafe_override flag.

  Args:
    value: A str containing the flag value for parse. The format should follow
        one of the following examples:
          1. "False" - All modules override the YAML threadsafe configuration
             as if the YAML contained False.
          2. "default:False,backend:True" - The default module overrides the
             YAML threadsafe configuration as if the YAML contained False, the
             "backend" module overrides with a value of True and all other
             modules use the value in the YAML file. An empty name (i.e.
             ":True") is shorthand for default to match how not specifying a
             module name in the yaml is the same as specifying
             "module: default".
  Returns:
    The parsed value of the threadsafe_override flag. May either be a bool
    (for values of the form "False") or a dict of str->bool (for values of the
    form "default:False,backend:True").

  Raises:
    argparse.ArgumentTypeError: the value is invalid.
  """
  return parse_per_module_option(
      value, boolean_action.BooleanParse, lambda _: True,
      'Invalid threadsafe override: %r',
      None,
      'Expected "module:threadsafe_override": %r',
      None,
      'Duplicate threadsafe override value for module %s')


def parse_path(value):
  """Returns the given path with ~ and environment variables expanded."""
  return os.path.expanduser(os.path.expandvars(value))


class ConfigurableArgumentParser(argparse.ArgumentParser):
  """Provides configurations option to the argument parser.

  This provides a convenient way to share flags between tools, and to toggle
  flags on and off for tools, eg for dev_appserver.py vs api_server.py.

  Example usage (with a helper create_parser function):

    def create_parser(config):
      parser = ConfigurableArgumentParser(config)
      parser.add_argument('flag-for-all-configs')
      parser.add_argument('foo-flag',
                          restrict_configurations=['my-configuration'])
      parser.add_argument('bar-flag',
                          restrict_configurations=['another-configuration'])
      parser.add_argument('foobar-flag',
                          restrict_configurations=[
                              'my-configuration', 'another-configuration'])
      return parser

    create_parser('my-configuration')  ->  contains [
        'flag-for-all-configs', 'foo-flag', 'foobar-flag']
    create_parser('another-configuration')  ->  contains [
        'flag-for-all-configs', 'bar-flag', 'foobar-flag']
    create_parser('yet-another-configuration')  ->  contains [
        'flag-for-all-configs']
  """

  def __init__(self, *args, **kwargs):
    """Initializes the argument parser.

    Args:
      *args: Arguments passed on to the parent init method.
      **kwargs: Keyword arguments passed on to the parent init method, can
          optionally contain a 'configuration' kwarg that will be popped and
          stored on the instance. This should be the string configuration
          accepted by the parser.
    """
    self._configuration = kwargs.pop('configuration', None)
    super(ConfigurableArgumentParser, self).__init__(*args, **kwargs)

  def add_argument(self, *args, **kwargs):
    """Adds an argument to the parser.

    Args:
      *args: Arguments passed on to the argument group.
      **kwargs: Keyword arguments passed on to the argument group, can
          optionally contain a 'restrict_configuration' kwarg that will be
          popped. This should be the list of configurations the the argument is
          applicable for. Omitting this kwarg, or providing an empty list,
          signifies that the added argument is valid for all configurations.
    """
    restrict_configuration = kwargs.pop('restrict_configuration', [])
    if (not restrict_configuration or
        self._configuration in restrict_configuration):
      super(ConfigurableArgumentParser, self).add_argument(*args, **kwargs)

  def add_argument_group(self, *args, **kwargs):
    """Adds an argument group to the parser.

    The parsers's configuration is set on the argument group.

    Args:
      *args: Arguments passed on to the argument group.
      **kwargs: Keyword arguments passed on to the argument group.

    Returns:
      An instance of ConfigurableArgumentGroup.
    """
    group = ConfigurableArgumentGroup(
        self, configuration=self._configuration, *args, **kwargs)
    self._action_groups.append(group)
    return group


class ConfigurableArgumentGroup(argparse._ArgumentGroup):  # pylint: disable=protected-access
  """Provides configuration options to the argument group.

  This provides a convenient way to share flags between tools, and to toggle
  flags on and off for tools, eg for dev_appserver.py vs api_server.py.
  """

  def __init__(self, *args, **kwargs):
    """Initializes the argument group.

    Args:
      *args: Arguments passed on to the parent init method.
      **kwargs: Keyword arguments passed on to the parent init method, can
          optionally contain a 'configuration' kwarg that will be popped and
          stored on the instance. This should be the string configuration
          accepted by the parser.
    """
    self._configuration = kwargs.pop('configuration', None)
    super(ConfigurableArgumentGroup, self).__init__(*args, **kwargs)

  def add_argument(self, *args, **kwargs):
    """Adds an argument to the group.

    Args:
      *args: Arguments passed on to the argument group.
      **kwargs: Keyword arguments passed on to the argument group, can
          optionally contain a 'restrict_configuration' kwarg that will be
          popped. This should be the list of configurations the the argument is
          applicable for. Omitting this kwarg, or providing an empty list,
          signifies that the added argument is valid for all configurations.
    """
    restrict_configuration = kwargs.pop('restrict_configuration', [])
    if (not restrict_configuration or
        self._configuration in restrict_configuration):
      super(ConfigurableArgumentGroup, self).add_argument(*args, **kwargs)


def create_command_line_parser(configuration=None):
  """Returns an argparse.ArgumentParser to parse command line arguments.

  Args:
    configuration: A string token containing the configuration to generate a
      command line parser for.

  Returns:
    An instance of ConfigurableArgumentParser.
  """
  # TODO: Add more robust argument validation. Consider what flags
  # are actually needed.

  parser = ConfigurableArgumentParser(
      configuration=configuration,
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  arg_name = 'yaml_path'
  arg_help = 'Path to one or more app.yaml files'

  # dev_appserver.py requires config_paths, api_server.py does not.
  parser.add_argument(
      'config_paths', restrict_configuration=[DEV_APPSERVER_CONFIGURATION],
      metavar=arg_name, nargs='+', help=arg_help)
  parser.add_argument(
      'config_paths', restrict_configuration=[API_SERVER_CONFIGURATION],
      metavar=arg_name, nargs='*', help=arg_help)

  common_group = parser.add_argument_group('Common')
  common_group.add_argument(
      '-A', '--application', action='store', dest='app_id',
      help='Set the application, overriding the application value from the '
      'app.yaml file.')
  common_group.add_argument(
      '--host', default='localhost',
      help='host name to which application modules should bind')
  common_group.add_argument(
      '--port', type=PortParser(), default=8080,
      help='lowest port to which application modules should bind')
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
      type=parse_path,
      help='path to the data (datastore, blobstore, etc.) associated with the '
      'application.')
  common_group.add_argument(
      '--log_level', default='info',
      choices=constants.LOG_LEVEL_TO_RUNTIME_CONSTANT.keys(),
      help='the log level below which logging messages generated by '
      'application code will not be displayed on the console')
  common_group.add_argument(
      '--max_module_instances',
      type=parse_max_module_instances,
      help='the maximum number of runtime instances that can be started for a '
      'particular module - the value can be an integer, in what case all '
      'modules are limited to that number of instances or a comma-seperated '
      'list of module:max_instances e.g. "default:5,backend:3"')
  common_group.add_argument(
      '--use_mtime_file_watcher',
      action=boolean_action.BooleanAction,
      const=True,
      default=False,
      help='use mtime polling for detecting source code changes - useful if '
      'modifying code from a remote machine using a distributed file system')
  common_group.add_argument(
      '--threadsafe_override',
      type=parse_threadsafe_override,
      help='override the application\'s threadsafe configuration - the value '
      'can be a boolean, in which case all modules threadsafe setting will '
      'be overridden or a comma-separated list of module:threadsafe_override '
      'e.g. "default:False,backend:True"')

  # PHP
  php_group = parser.add_argument_group('PHP')
  php_group.add_argument('--php_executable_path', metavar='PATH',
                         type=parse_path,
                         default=_get_default_php_path(),
                         help='path to the PHP executable')
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
      type=parse_path,
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
      type=parse_path,
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
      type=parse_path,
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
      type=parse_path,
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
      help='make files specified in the app.yaml "skip_files" or "static" '
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
            'module are changed'))
  misc_group.add_argument(
      '--dev_appserver_log_level', default='info',
      choices=constants.LOG_LEVEL_TO_PYTHON_CONSTANT.keys(),
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
  misc_group.add_argument(
      '--default_gcs_bucket_name', default=None,
      help='default Google Cloud Storgage bucket name')

  # AppScale
  appscale_group = parser.add_argument_group('AppScale')
  appscale_group.add_argument(
    '--external_api_port', type=int,
    help='The port of the external server that handles API calls')
  appscale_group.add_argument(
    '--login_server',
    help='the FQDN or IP address where users should be redirected to when the '
    'app needs them to log in on a given URL.')
  appscale_group.add_argument(
    '--nginx_host',
    help='the FQDN or IP address where Task Queue tasks should sent to, so '
    'that they are evenly distributed amongst AppServers.')
  appscale_group.add_argument(
    '--xmpp_path',
    help='the FQDN or IP address where ejabberd is running, so that we know '
    'where XMPP connections should be made to.')
  appscale_group.add_argument(
    '--uaserver_path',
    help='the FQDN or IP address where the UserAppServer runs.')
  appscale_group.add_argument(
    '--trusted',
    action=boolean_action.BooleanAction,
    const=True,
    default=False,
    help='if this application can read data stored by other applications.')
  appscale_group.add_argument('--pidfile', help='create pidfile at location')

  return parser
