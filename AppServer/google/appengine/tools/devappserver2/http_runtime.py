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
"""Serves content for "script" handlers using an HTTP runtime."""


import base64
import contextlib
import httplib
import logging
import os
import socket
import subprocess
import threading
import urllib
import wsgiref.headers

from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import safe_subprocess
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import util


class HttpRuntimeProxy(instance.RuntimeProxy):
  """Manages a runtime subprocess used to handle dynamic content."""

  def __init__(self, args, runtime_config_getter, server_configuration,
               env=None):
    """Initializer for HttpRuntimeProxy.

    Args:
      args: Arguments to use to start the runtime subprocess.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      server_configuration: An application_configuration.ServerConfiguration
          instance respresenting the configuration of the server that owns the
          runtime.
      env: A dict of environment variables to pass to the runtime subprocess.
    """
    super(HttpRuntimeProxy, self).__init__()
    self._host = 'localhost'
    self._port = None
    self._process = None
    self._process_lock = threading.Lock()  # Lock to guard self._process.
    self._runtime_config_getter = runtime_config_getter
    self._args = args
    self._server_configuration = server_configuration
    self._env = env

  def _get_error_file(self):
    for error_handler in self._server_configuration.error_handlers or []:
      if not error_handler.error_code or error_handler.error_code == 'default':
        return os.path.join(self._server_configuration.application_root,
                            error_handler.file)
    else:
      return None

  def handle(self, environ, start_response, url_map, match, request_id,
             request_type):
    """Serves this request by forwarding it to the runtime process.

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
    environ[http_runtime_constants.SCRIPT_HEADER] = match.expand(url_map.script)
    if request_type == instance.BACKGROUND_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'background'
    elif request_type == instance.SHUTDOWN_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'shutdown'
    elif request_type == instance.INTERACTIVE_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'interactive'

    for name in http_runtime_constants.ENVIRONS_TO_PROPAGATE:
      if http_runtime_constants.INTERNAL_ENVIRON_PREFIX + name not in environ:
        value = environ.get(name, None)
        if value is not None:
          environ[
              http_runtime_constants.INTERNAL_ENVIRON_PREFIX + name] = value
    headers = util.get_headers_from_environ(environ)
    if environ.get('QUERY_STRING'):
      url = '%s?%s' % (urllib.quote(environ['PATH_INFO']),
                       environ['QUERY_STRING'])
    else:
      url = urllib.quote(environ['PATH_INFO'])
    if 'CONTENT_LENGTH' in environ:
      headers['CONTENT-LENGTH'] = environ['CONTENT_LENGTH']
      data = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
    else:
      data = ''

    cookies = environ.get('HTTP_COOKIE')
    user_email, admin, user_id = login.get_user_info(cookies)
    if user_email:
      nickname, organization = user_email.split('@', 1)
    else:
      nickname = ''
      organization = ''
    headers[http_runtime_constants.REQUEST_ID_HEADER] = request_id
    headers[http_runtime_constants.INTERNAL_HEADER_PREFIX + 'User-Id'] = (
        user_id)
    headers[http_runtime_constants.INTERNAL_HEADER_PREFIX + 'User-Email'] = (
        user_email)
    headers[
        http_runtime_constants.INTERNAL_HEADER_PREFIX + 'User-Is-Admin'] = (
            str(int(admin)))
    headers[
        http_runtime_constants.INTERNAL_HEADER_PREFIX + 'User-Nickname'] = (
            nickname)
    headers[
        http_runtime_constants.INTERNAL_HEADER_PREFIX + 'User-Organization'] = (
            organization)
    headers['X-AppEngine-Country'] = 'ZZ'
    connection = httplib.HTTPConnection(self._host, self._port)
    with contextlib.closing(connection):
      try:
        connection.connect()
        connection.request(environ.get('REQUEST_METHOD', 'GET'),
                           url,
                           data,
                           dict(headers.items()))
        response = connection.getresponse()

        # Ensures that we avoid merging repeat headers into a single header,
        # allowing use of multiple Set-Cookie headers.
        headers = []
        for name in response.msg:
          for value in response.msg.getheaders(name):
            headers.append((name, value))

        response_headers = wsgiref.headers.Headers(headers)

        error_file = self._get_error_file()
        if (error_file and
            http_runtime_constants.ERROR_CODE_HEADER in response_headers):
          try:
            with open(error_file) as f:
              content = f.read()
          except IOError:
            content = 'Failed to load error handler'
            logging.exception('failed to load error file: %s', error_file)
          start_response('500 Internal Server Error',
                         [('Content-Type', 'text/html'),
                          ('Content-Length', str(len(content)))])
          yield content
          return
        del response_headers[http_runtime_constants.ERROR_CODE_HEADER]
        start_response('%s %s' % (response.status, response.reason),
                       response_headers.items())

        # Yield the response body in small blocks.
        block = response.read(512)
        while block:
          yield block
          block = response.read(512)
      except Exception:
        with self._process_lock:
          if self._process and self._process.poll() is not None:
            # The development server is in a bad state. Log and return an error
            # message and quit.
            message = ('the runtime process for the instance running on port '
                       '%d has unexpectedly quit; exiting the development '
                       'server' % (
                           self._port))
            logging.error(message)
            start_response('500 Internal Server Error',
                           [('Content-Type', 'text/plain'),
                            ('Content-Length', str(len(message)))])
            shutdown.async_quit()
            yield message
          else:
            raise

  def start(self):
    """Starts the runtime process and waits until it is ready to serve."""
    runtime_config = self._runtime_config_getter()
    serialized_config = base64.b64encode(runtime_config.SerializeToString())
    # TODO: Use a different process group to isolate the child process
    # from signals sent to the parent. Only available in subprocess in
    # Python 2.7.
    with self._process_lock:
      assert not self._process, 'start() can only be called once'
      self._process = safe_subprocess.start_process(
          self._args,
          serialized_config,
          stdout=subprocess.PIPE,
          env=self._env,
          cwd=self._server_configuration.application_root)
    line = self._process.stdout.readline()
    try:
      self._port = int(line)
    except ValueError:
      # The development server is in a bad state. Log an error message and quit.
      logging.error('unexpected port response from runtime [%r]; '
                    'exiting the development server',
                    line)
      shutdown.async_quit()
    else:
      self._check_serving()

  def _can_connect(self):
    connection = httplib.HTTPConnection(self._host, self._port)
    with contextlib.closing(connection):
      try:
        connection.connect()
      except socket.error:
        return False
      else:
        return True

  def _check_serving(self):
    """Checks if the runtime can serve requests.

    Quits the development server if the runtime cannot serve.
    """
    if not self._can_connect():
      logging.error('cannot connect to runtime running on port %r; '
                    'exiting the development server',
                    self._port)
      shutdown.async_quit()

  def quit(self):
    """Causes the runtime process to exit."""
    with self._process_lock:
      assert self._process, 'server was not running'
      try:
        self._process.kill()
      except OSError:
        pass
      self._process = None
