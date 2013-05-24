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
"""A PHP devappserver2 runtime."""


import base64
import cStringIO
import httplib
import logging
import os
import subprocess
import sys
import time
import urllib

import google

from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import php
from google.appengine.tools.devappserver2 import request_rewriter
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import wsgi_server

SDK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(sys.argv[0]), 'php/sdk'))
SETUP_PHP_PATH = os.path.join(os.path.dirname(php.__file__), 'setup.php')


class PHPRuntime(object):
  """A WSGI application that runs PHP scripts using the PHP CGI binary."""

  def __init__(self, config):
    logging.debug('Initializing runtime with %s', config)
    self.config = config
    self.environ_template = {
        'APPLICATION_ID': str(config.app_id),
        'CURRENT_VERSION_ID': str(config.version_id),
        'DATACENTER': config.datacenter,
        'INSTANCE_ID': config.instance_id,
        'APPENGINE_RUNTIME': 'php',
        'AUTH_DOMAIN': config.auth_domain,
        'HTTPS': 'off',
        # By default php-cgi does not allow .php files to be run directly so
        # REDIRECT_STATUS must be set. See:
        # http://php.net/manual/en/security.cgi-bin.force-redirect.php
        'REDIRECT_STATUS': '1',
        'REMOTE_API_PORT': str(config.api_port),
        'SERVER_SOFTWARE': http_runtime_constants.SERVER_SOFTWARE,
        'TZ': 'UTC',
        }
    self.environ_template.update((env.key, env.value) for env in config.environ)

  def __call__(self, environ, start_response):
    """Handles an HTTP request for the runtime using a PHP executable.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      start_response: A function with semantics defined in PEP-333.

    Returns:
      An iterable over strings containing the body of the HTTP response.
    """
    user_environ = self.environ_template.copy()

    self.copy_headers(environ, user_environ)
    user_environ['REQUEST_METHOD'] = environ.get('REQUEST_METHOD', 'GET')
    user_environ['PATH_INFO'] = environ['PATH_INFO']
    user_environ['QUERY_STRING'] = environ['QUERY_STRING']
    # Modify the SCRIPT_FILENAME to specify the setup script that readies the
    # PHP environment. Put the user script in REAL_SCRIPT_FILENAME.
    user_environ['REAL_SCRIPT_FILENAME'] = environ[
        http_runtime_constants.SCRIPT_HEADER]
    user_environ['SCRIPT_FILENAME'] = SETUP_PHP_PATH
    user_environ['REMOTE_REQUEST_ID'] = environ[
        http_runtime_constants.REQUEST_ID_ENVIRON]

    if 'CONTENT_TYPE' in environ:
      user_environ['CONTENT_TYPE'] = environ['CONTENT_TYPE']

    if 'CONTENT_LENGTH' in environ:
      user_environ['CONTENT_LENGTH'] = environ['CONTENT_LENGTH']
      content = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
    else:
      content = None

    include_path = 'include_path=%s:%s' % (self.config.application_root,
                                           SDK_PATH)

    args = [self.config.php_config.php_executable_path, '-d', include_path]

    if self.config.php_config.enable_debugger:
      args.extend(['-d', 'xdebug.remote_enable="1"'])
      user_environ['XDEBUG_CONFIG'] = os.environ.get('XDEBUG_CONFIG', '')

    p = subprocess.Popen(args,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         env=user_environ,
                         cwd=self.config.application_root)
    stdout, stderr = p.communicate(content)

    if p.returncode:
      logging.error('php failure (%r) with:\n%s', p.returncode, stdout+stderr)
      start_response('500 Internal Server Error',
                     [(http_runtime_constants.ERROR_CODE_HEADER, '1')])
      return []

    message = httplib.HTTPMessage(cStringIO.StringIO(stdout))
    assert 'Content-Type' in message, 'invalid CGI response: %r' % stdout

    if 'Status' in message:
      status = message['Status']
      del message['Status']
    else:
      status = '200 OK'

    # Ensures that we avoid merging repeat headers into a single header,
    # allowing use of multiple Set-Cookie headers.
    headers = []
    for name in message:
      for value in message.getheaders(name):
        headers.append((name, value))

    start_response(status, headers)
    return [message.fp.read()]

  def copy_headers(self, source_environ, dest_environ):
    """Copy headers from source_environ to dest_environ.

    This extracts headers that represent environ values and propagates all
    other headers which are not used for internal implementation details or
    headers that are stripped.

    Args:
      source_environ: The source environ dict.
      dest_environ: The environ dict to populate.
    """
    # TODO: This method is copied from python/runtime.py. If this
    # method isn't obsoleted, consider moving it to some sort of utility module.
    for env in http_runtime_constants.ENVIRONS_TO_PROPAGATE:
      value = source_environ.get(
          http_runtime_constants.INTERNAL_ENVIRON_PREFIX + env, None)
      if value is not None:
        dest_environ[env] = value
    for name, value in source_environ.items():
      if (name.startswith('HTTP_') and
          not name.startswith(http_runtime_constants.INTERNAL_ENVIRON_PREFIX)):
        dest_environ[name] = value


def main():
  config = runtime_config_pb2.Config()
  config.ParseFromString(base64.b64decode(sys.stdin.read()))
  server = wsgi_server.WsgiServer(
      ('localhost', 0),
      request_rewriter.runtime_rewriter_middleware(PHPRuntime(config)))
  server.start()
  print server.port
  sys.stdout.close()
  sys.stdout = sys.stderr
  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    server.quit()


if __name__ == '__main__':
  main()
