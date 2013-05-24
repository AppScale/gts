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
"""Stores application configuration taken from e.g. app.yaml, queues.yaml."""

# TODO: Support more than just app.yaml.


import errno
import logging
import os
import os.path
import random
import string
import threading
import types

from google.appengine.api import appinfo
from google.appengine.api import appinfo_includes
from google.appengine.api import backendinfo
from google.appengine.api import dispatchinfo
from google.appengine.tools.devappserver2 import errors

# Constants passed to functions registered with
# ServerConfiguration.add_change_callback.
NORMALIZED_LIBRARIES_CHANGED = 1
SKIP_FILES_CHANGED = 2
HANDLERS_CHANGED = 3
INBOUND_SERVICES_CHANGED = 4
ENV_VARIABLES_CHANGED = 5
ERROR_HANDLERS_CHANGED = 6
NOBUILD_FILES_CHANGED = 7


class ServerConfiguration(object):
  """Stores server configuration information.

  Most configuration options are mutable and may change any time
  check_for_updates is called. Client code must be able to cope with these
  changes.

  Other properties are immutable (see _IMMUTABLE_PROPERTIES) and are guaranteed
  to be constant for the lifetime of the instance.
  """

  _IMMUTABLE_PROPERTIES = [
      ('application', 'application'),
      ('version', 'major_version'),
      ('runtime', 'runtime'),
      ('threadsafe', 'threadsafe'),
      ('server', 'server_name'),
      ('basic_scaling', 'basic_scaling'),
      ('manual_scaling', 'manual_scaling'),
      ('automatic_scaling', 'automatic_scaling')]

  def __init__(self, yaml_path):
    """Initializer for ServerConfiguration.

    Args:
      yaml_path: A string containing the full path of the yaml file containing
          the configuration for this server.
    """
    self._yaml_path = yaml_path
    self._app_info_external = None
    self._application_root = os.path.realpath(os.path.dirname(yaml_path))
    self._last_failure_message = None

    self._app_info_external, files_to_check = self._parse_configuration(
        self._yaml_path)
    self._mtimes = self._get_mtimes([self._yaml_path] + files_to_check)
    self._application = 'dev~%s' % self._app_info_external.application
    self._api_version = self._app_info_external.api_version
    self._server_name = self._app_info_external.server
    self._version = self._app_info_external.version
    self._threadsafe = self._app_info_external.threadsafe
    self._basic_scaling = self._app_info_external.basic_scaling
    self._manual_scaling = self._app_info_external.manual_scaling
    self._automatic_scaling = self._app_info_external.automatic_scaling
    self._runtime = self._app_info_external.runtime
    if self._runtime == 'python':
      logging.warning(
          'The "python" runtime specified in "%s" is not supported - the '
          '"python27" runtime will be used instead. A description of the '
          'differences between the two can be found here:\n'
          'https://developers.google.com/appengine/docs/python/python25/diff27',
           self._yaml_path)
    self._minor_version_id = ''.join(random.choice(string.digits) for _ in
                                     range(18))

  @property
  def application_root(self):
    """The directory containing the application e.g. "/home/user/myapp"."""
    return self._application_root

  @property
  def application(self):
    return self._application

  @property
  def api_version(self):
    return self._api_version

  @property
  def server_name(self):
    return self._server_name or 'default'

  @property
  def major_version(self):
    return self._version

  @property
  def version_id(self):
    if self.server_name == 'default':
      return '%s.%s' % (
          self.major_version,
          self._minor_version_id)
    else:
      return '%s:%s.%s' % (
          self.server_name,
          self.major_version,
          self._minor_version_id)

  @property
  def runtime(self):
    return self._runtime

  @property
  def threadsafe(self):
    return self._threadsafe

  @property
  def basic_scaling(self):
    return self._basic_scaling

  @property
  def manual_scaling(self):
    return self._manual_scaling

  @property
  def automatic_scaling(self):
    return self._automatic_scaling

  @property
  def normalized_libraries(self):
    return self._app_info_external.GetNormalizedLibraries()

  @property
  def skip_files(self):
    return self._app_info_external.skip_files

  @property
  def nobuild_files(self):
    return self._app_info_external.nobuild_files

  @property
  def error_handlers(self):
    return self._app_info_external.error_handlers

  @property
  def handlers(self):
    return self._app_info_external.handlers

  @property
  def inbound_services(self):
    return self._app_info_external.inbound_services

  @property
  def env_variables(self):
    return self._app_info_external.env_variables

  @property
  def is_backend(self):
    return False

  def check_for_updates(self):
    """Return any configuration changes since the last check_for_updates call.

    Returns:
      A set containing the changes that occured. See the *_CHANGED module
      constants.
    """
    new_mtimes = self._get_mtimes(self._mtimes.keys())
    if new_mtimes == self._mtimes:
      return set()

    try:
      app_info_external, files_to_check = self._parse_configuration(
          self._yaml_path)
    except Exception, e:
      failure_message = str(e)
      if failure_message != self._last_failure_message:
        logging.error('Configuration is not valid: %s', failure_message)
      self._last_failure_message = failure_message
      return set()
    self._last_failure_message = None

    self._mtimes = self._get_mtimes([self._yaml_path] + files_to_check)

    for app_info_attribute, self_attribute in self._IMMUTABLE_PROPERTIES:
      app_info_value = getattr(app_info_external, app_info_attribute)
      self_value = getattr(self, self_attribute)
      if (app_info_value == self_value or
          app_info_value == getattr(self._app_info_external,
                                    app_info_attribute)):
        # Only generate a warning if the value is both different from the
        # immutable value *and* different from the last loaded value.
        continue

      if isinstance(app_info_value, types.StringTypes):
        logging.warning('Restart the development server to see updates to "%s" '
                        '["%s" => "%s"]',
                        app_info_attribute,
                        self_value,
                        app_info_value)
      else:
        logging.warning('Restart the development server to see updates to "%s"',
                        app_info_attribute)

    changes = set()
    if (app_info_external.GetNormalizedLibraries() !=
        self.normalized_libraries):
      changes.add(NORMALIZED_LIBRARIES_CHANGED)
    if app_info_external.skip_files != self.skip_files:
      changes.add(SKIP_FILES_CHANGED)
    if app_info_external.nobuild_files != self.nobuild_files:
      changes.add(NOBUILD_FILES_CHANGED)
    if app_info_external.handlers != self.handlers:
      changes.add(HANDLERS_CHANGED)
    if app_info_external.inbound_services != self.inbound_services:
      changes.add(INBOUND_SERVICES_CHANGED)
    if app_info_external.env_variables != self.env_variables:
      changes.add(ENV_VARIABLES_CHANGED)
    if app_info_external.error_handlers != self.error_handlers:
      changes.add(ERROR_HANDLERS_CHANGED)

    self._app_info_external = app_info_external
    if changes:
      self._minor_version_id = ''.join(random.choice(string.digits) for _ in
                                       range(18))
    return changes

  @staticmethod
  def _get_mtimes(filenames):
    filename_to_mtime = {}
    for filename in filenames:
      try:
        filename_to_mtime[filename] = os.path.getmtime(filename)
      except OSError as e:
        # Ignore deleted includes.
        if e.errno != errno.ENOENT:
          raise
    return filename_to_mtime

  @staticmethod
  def _parse_configuration(configuration_path):
    # TODO: It probably makes sense to catch the exception raised
    # by Parse() and re-raise it using a module-specific exception.
    with open(configuration_path) as f:
      return appinfo_includes.ParseAndReturnIncludePaths(f)


class BackendsConfiguration(object):
  """Stores configuration information for a backends.yaml file."""

  def __init__(self, app_yaml_path, backend_yaml_path):
    """Initializer for BackendsConfiguration.

    Args:
      app_yaml_path: A string containing the full path of the yaml file
          containing the configuration for this server.
      backend_yaml_path: A string containing the full path of the backends.yaml
          file containing the configuration for backends.
    """
    self._update_lock = threading.RLock()
    self._base_server_configuration = ServerConfiguration(app_yaml_path)
    backend_info_external = self._parse_configuration(
        backend_yaml_path)

    self._backends_name_to_backend_entry = {}
    for backend in backend_info_external.backends or []:
      self._backends_name_to_backend_entry[backend.name] = backend
    self._changes = dict(
        (backend_name, set())
        for backend_name in self._backends_name_to_backend_entry)

  @staticmethod
  def _parse_configuration(configuration_path):
    # TODO: It probably makes sense to catch the exception raised
    # by Parse() and re-raise it using a module-specific exception.
    with open(configuration_path) as f:
      return backendinfo.LoadBackendInfo(f)

  def get_backend_configurations(self):
    return [BackendConfiguration(self._base_server_configuration, self, entry)
            for entry in self._backends_name_to_backend_entry.values()]

  def check_for_updates(self, backend_name):
    """Return any configuration changes since the last check_for_updates call.

    Args:
      backend_name: A str containing the name of the backend to be checked for
          updates.

    Returns:
      A set containing the changes that occured. See the *_CHANGED module
      constants.
    """
    with self._update_lock:
      server_changes = self._base_server_configuration.check_for_updates()
      if server_changes:
        for backend_changes in self._changes.values():
          backend_changes.update(server_changes)
      changes = self._changes[backend_name]
      self._changes[backend_name] = set()
    return changes


class BackendConfiguration(object):
  """Stores backend configuration information.

  This interface is and must remain identical to ServerConfiguration.
  """

  def __init__(self, server_configuration, backends_configuration,
               backend_entry):
    """Initializer for BackendConfiguration.

    Args:
      server_configuration: A ServerConfiguration to use.
      backends_configuration: The BackendsConfiguration that tracks updates for
          this BackendConfiguration.
      backend_entry: A backendinfo.BackendEntry containing the backend
          configuration.
    """
    self._server_configuration = server_configuration
    self._backends_configuration = backends_configuration
    self._backend_entry = backend_entry

    if backend_entry.dynamic:
      self._basic_scaling = appinfo.BasicScaling(
          max_instances=backend_entry.instances or 1)
      self._manual_scaling = None
    else:
      self._basic_scaling = None
      self._manual_scaling = appinfo.ManualScaling(
          instances=backend_entry.instances or 1)
    self._minor_version_id = ''.join(random.choice(string.digits) for _ in
                                     range(18))

  @property
  def application_root(self):
    """The directory containing the application e.g. "/home/user/myapp"."""
    return self._server_configuration.application_root

  @property
  def application(self):
    return self._server_configuration.application

  @property
  def api_version(self):
    return self._server_configuration.api_version

  @property
  def server_name(self):
    return self._backend_entry.name

  @property
  def major_version(self):
    return self._server_configuration.major_version

  @property
  def version_id(self):
    return '%s:%s.%s' % (
        self.server_name,
        self.major_version,
        self._minor_version_id)

  @property
  def runtime(self):
    return self._server_configuration.runtime

  @property
  def threadsafe(self):
    return self._server_configuration.threadsafe

  @property
  def basic_scaling(self):
    return self._basic_scaling

  @property
  def manual_scaling(self):
    return self._manual_scaling

  @property
  def automatic_scaling(self):
    return None

  @property
  def normalized_libraries(self):
    return self._server_configuration.normalized_libraries

  @property
  def skip_files(self):
    return self._server_configuration.skip_files

  @property
  def nobuild_files(self):
    return self._server_configuration.nobuild_files

  @property
  def error_handlers(self):
    return self._server_configuration.error_handlers

  @property
  def handlers(self):
    if self._backend_entry.start:
      return [appinfo.URLMap(
          url='/_ah/start',
          script=self._backend_entry.start,
          login='admin')] + self._server_configuration.handlers
    return self._server_configuration.handlers

  @property
  def inbound_services(self):
    return self._server_configuration.inbound_services

  @property
  def env_variables(self):
    return self._server_configuration.env_variables

  @property
  def is_backend(self):
    return True

  def check_for_updates(self):
    """Return any configuration changes since the last check_for_updates call.

    Returns:
      A set containing the changes that occured. See the *_CHANGED module
      constants.
    """
    changes = self._backends_configuration.check_for_updates(
        self._backend_entry.name)
    if changes:
      self._minor_version_id = ''.join(random.choice(string.digits) for _ in
                                       range(18))
    return changes


class DispatchConfiguration(object):
  """Stores dispatcher configuration information."""

  def __init__(self, yaml_path):
    self._yaml_path = yaml_path
    self._mtime = os.path.getmtime(self._yaml_path)
    self._process_dispatch_entries(self._parse_configuration(self._yaml_path))

  @staticmethod
  def _parse_configuration(configuration_path):
    # TODO: It probably makes sense to catch the exception raised
    # by LoadSingleDispatch() and re-raise it using a module-specific exception.
    with open(configuration_path) as f:
      return dispatchinfo.LoadSingleDispatch(f)

  def check_for_updates(self):
    mtime = os.path.getmtime(self._yaml_path)
    if mtime > self._mtime:
      self._mtime = mtime
      try:
        dispatch_info_external = self._parse_configuration(self._yaml_path)
      except Exception, e:
        failure_message = str(e)
        logging.error('Configuration is not valid: %s', failure_message)
        return
      self._process_dispatch_entries(dispatch_info_external)

  def _process_dispatch_entries(self, dispatch_info_external):
    path_only_entries = []
    hostname_entries = []
    for entry in dispatch_info_external.dispatch:
      parsed_url = dispatchinfo.ParsedURL(entry.url)
      if parsed_url.host:
        hostname_entries.append(entry)
      else:
        path_only_entries.append((parsed_url, entry.server))
    if hostname_entries:
      logging.warning(
          'Hostname routing is not supported by the development server. The '
          'following dispatch entries will not match any requests:\n%s',
          '\n\t'.join(str(entry) for entry in hostname_entries))
    self._entries = path_only_entries

  @property
  def dispatch(self):
    return self._entries


class ApplicationConfiguration(object):
  """Stores application configuration information."""

  def __init__(self, yaml_paths):
    """Initializer for ApplicationConfiguration.

    Args:
      yaml_paths: A list of strings containing the paths to yaml files.
    """
    self.servers = []
    self.dispatch = None
    if len(yaml_paths) == 1 and os.path.isdir(yaml_paths[0]):
      directory_path = yaml_paths[0]
      for app_yaml_path in [os.path.join(directory_path, 'app.yaml'),
                            os.path.join(directory_path, 'app.yml')]:
        if os.path.exists(app_yaml_path):
          yaml_paths = [app_yaml_path]
          break
      else:
        raise errors.AppConfigNotFoundError(
            'no app.yaml file at %r' % directory_path)
      for backends_yaml_path in [os.path.join(directory_path, 'backends.yaml'),
                                 os.path.join(directory_path, 'backends.yml')]:
        if os.path.exists(backends_yaml_path):
          yaml_paths.append(backends_yaml_path)
          break
    for yaml_path in yaml_paths:
      if os.path.isdir(yaml_path):
        raise errors.InvalidAppConfigError(
            '"%s" is a directory and a yaml configuration file is required' %
            yaml_path)
      elif (yaml_path.endswith('backends.yaml') or
            yaml_path.endswith('backends.yml')):
        # TODO: Reuse the ServerConfiguration created for the app.yaml
        # instead of creating another one for the same file.
        self.servers.extend(
            BackendsConfiguration(yaml_path.replace('backends.y', 'app.y'),
                                  yaml_path).get_backend_configurations())
      elif (yaml_path.endswith('dispatch.yaml') or
            yaml_path.endswith('dispatch.yml')):
        if self.dispatch:
          raise errors.InvalidAppConfigError(
              'Multiple dispatch.yaml files specified')
        self.dispatch = DispatchConfiguration(yaml_path)
      else:
        server_configuration = ServerConfiguration(yaml_path)
        self.servers.append(server_configuration)
    application_ids = set(server.application
                          for server in self.servers)
    if len(application_ids) > 1:
      raise errors.InvalidAppConfigError(
          'More than one application ID found: %s' %
          ', '.join(sorted(application_ids)))

    self._app_id = application_ids.pop()
    server_names = set()
    for server in self.servers:
      if server.server_name in server_names:
        raise errors.InvalidAppConfigError('Duplicate server: %s' %
                                           server.server_name)
      server_names.add(server.server_name)
    if self.dispatch:
      if 'default' not in server_names:
        raise errors.InvalidAppConfigError(
            'A default server must be specified.')
      missing_servers = (
          set(server_name for _, server_name in self.dispatch.dispatch) -
          server_names)
      if missing_servers:
        raise errors.InvalidAppConfigError(
            'Servers %s specified in dispatch.yaml are not defined by a yaml '
            'file.' % sorted(missing_servers))

  @property
  def app_id(self):
    return self._app_id
