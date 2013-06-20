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
"""Serves content for "script" handlers using the PHP runtime."""


import logging
import os
import re
import subprocess
import sys

import google
from google.appengine.api import appinfo
from google.appengine.tools.devappserver2 import http_runtime
from google.appengine.tools.devappserver2 import instance

from google.appengine.tools.devappserver2 import safe_subprocess


_RUNTIME_PATH = os.path.abspath(
    os.path.join(os.path.dirname(sys.argv[0]), '_php_runtime.py')
    )
_CHECK_ENVIRONMENT_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), 'php', 'check_environment.php')
_RUNTIME_ARGS = [sys.executable, _RUNTIME_PATH]


class _PHPEnvironmentError(Exception):
  pass


class _BadPHPEnvironmentRuntimeProxy(instance.RuntimeProxy):
  """Servers an error page describing the problem with the user's PHP setup."""

  def __init__(self, php_executable_path, problem_description):
    self._php_executable_path = php_executable_path
    self._problem_description = problem_description

  def start(self):
    pass

  def quit(self):
    pass

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Serves a request by displaying an error page.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.
      url_map: An appinfo.URLMap instance containing the configuration for the
          handler matching this request.
      match: A re.MatchObject containing the result of the matched URL pattern.
      request_id: A unique string id associated with the request.
      request_type: The type of the request. See instance.*_REQUEST module
          constants.

    Yields:
      A sequence of strings containing the body of the HTTP response.
    """
    start_response('500 Internal Server Error',
                   [('Content-Type', 'text/html')])
    yield '<html><head><title>Invalid PHP Configuration</title></head>'
    yield '<body>'
    yield '<title>Invalid PHP Configuration</title>'
    yield '<b>The PHP interpreter specified with the --php_executable_path flag'
    yield ' (&quot;%s&quot;) is not compatible with the App Engine PHP ' % (
        self._php_executable_path)
    yield 'development environment.</b><br>'
    yield '<br>'
    yield '<pre>%s</pre>' % self._problem_description
    yield '</body></html>'


class PHPRuntimeInstanceFactory(instance.InstanceFactory):
  """A factory that creates new PHP runtime Instances."""

  # A mapping from a php executable path to the _BadPHPEnvironmentRuntimeProxy
  # descriping why it is not useable. If the php executable is usable then the
  # path will map to None. Only one PHP executable will be used in a run of the
  # development server but that is not necessarily the case for tests.
  _php_binary_to_bad_environment_proxy = {}

  # TODO: Use real script values.
  START_URL_MAP = appinfo.URLMap(
      url='/_ah/start',
      script='$PHP_LIB/default_start_handler',
      login='admin')
  WARMUP_URL_MAP = appinfo.URLMap(
      url='/_ah/warmup',
      script='$PHP_LIB/default_warmup_handler',
      login='admin')
  FILE_CHANGE_INSTANCE_RESTART_POLICY = instance.NEVER

  def __init__(self, request_data, runtime_config_getter, server_configuration):
    """Initializer for PHPRuntimeInstanceFactory.

    Args:
      request_data: A wsgi_request_info.WSGIRequestInfo that will be provided
          with request information for use by API stubs.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      server_configuration: An application_configuration.ServerConfiguration
          instance respresenting the configuration of the server that owns the
          runtime.
    """
    super(PHPRuntimeInstanceFactory, self).__init__(
        request_data, 8 if runtime_config_getter().threadsafe else 1)
    self._runtime_config_getter = runtime_config_getter
    self._server_configuration = server_configuration
    self._bad_environment_proxy = None

  @staticmethod
  def _check_environment(php_executable_path):
    if not os.path.exists(php_executable_path):
      raise _PHPEnvironmentError(
          'the file "%s" does not exist' % php_executable_path)

    version_process = safe_subprocess.start_process([php_executable_path, '-v'],
                                                    stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE,
                                                    env={})
    version_stdout, version_stderr = version_process.communicate()
    if version_process.returncode:
      raise _PHPEnvironmentError(
          '"%s -v" returned an error [%d]\n%s%s' % (
              php_executable_path,
              version_process.returncode,
              version_stderr,
              version_stdout))

    version_match = re.search(r'PHP (\d+).(\d+)', version_stdout)
    if version_match is None:
      raise _PHPEnvironmentError(
          '"%s -v" returned an unexpected version string:\n%s%s' % (
              php_executable_path,
              version_stderr,
              version_stdout))

    version = tuple(int(v) for v in version_match.groups())
    if version < (5, 4):
      raise _PHPEnvironmentError(
          'The PHP interpreter must be version >= 5.4, %d.%d found' % version)

    check_process = safe_subprocess.start_process(
        [php_executable_path, '-f', _CHECK_ENVIRONMENT_SCRIPT_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={})
    check_process_stdout, _ = check_process.communicate()
    if check_process.returncode:
      raise _PHPEnvironmentError(check_process_stdout)

  def new_instance(self, instance_id, expect_ready_request=False):
    """Create and return a new Instance.

    Args:
      instance_id: A string or integer representing the unique (per server) id
          of the instance.
      expect_ready_request: If True then the instance will be sent a special
          request (i.e. /_ah/warmup or /_ah/start) before it can handle external
          requests.

    Returns:
      The newly created instance.Instance.
    """

    def instance_config_getter():
      runtime_config = self._runtime_config_getter()
      runtime_config.instance_id = str(instance_id)
      return runtime_config

    php_executable_path = (
        self._runtime_config_getter().php_config.php_executable_path)

    if self._php_binary_to_bad_environment_proxy.get(
        php_executable_path) is None:
      try:
        self._check_environment(php_executable_path)
      except _PHPEnvironmentError as e:
        self._php_binary_to_bad_environment_proxy[php_executable_path] = (
            _BadPHPEnvironmentRuntimeProxy(php_executable_path, str(e)))
        logging.error('The PHP runtime is not available because: %r', str(e))
      else:
        self._php_binary_to_bad_environment_proxy[php_executable_path] = None

    proxy = self._php_binary_to_bad_environment_proxy[php_executable_path]
    if proxy is None:
      proxy = http_runtime.HttpRuntimeProxy(_RUNTIME_ARGS,
                                            instance_config_getter,
                                            self._server_configuration)
    return instance.Instance(self.request_data,
                             instance_id,
                             proxy,
                             self.max_concurrent_requests,
                             self.max_background_threads,
                             expect_ready_request)
