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
"""Serves content for "script" handlers using an HTTP runtime.

http_runtime supports two ways to start the runtime instance.

START_PROCESS sends the runtime_config protobuf (serialized and base64 encoded
as not all platforms support binary data over stdin) to the runtime instance
over stdin and requires the runtime instance to send the port it is listening on
over stdout.

START_PROCESS_FILE creates two temporary files and adds the paths of both files
to the runtime instance command line. The first file is written by http_runtime
with the runtime_config proto (serialized); the runtime instance is expected to
delete the file after reading it. The second file is written by the runtime
instance with the port it is listening on (the line must be newline terminated);
http_runtime is expected to delete the file after reading it.

TODO: convert all runtimes to START_PROCESS_FILE.
"""


import base64
import contextlib
import httplib
import logging
import os
import socket
import subprocess
import sys
import time
import threading
import urllib
import wsgiref.headers

from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import safe_subprocess
from google.appengine.tools.devappserver2 import tee
from google.appengine.tools.devappserver2 import util

START_PROCESS = -1
START_PROCESS_FILE = -2


def _sleep_between_retries(attempt, max_attempts, sleep_base):
  """Sleep between retry attempts.

  Do an exponential backoff between retry attempts on an operation. The general
  pattern for use is:
    for attempt in range(max_attempts):
      # Try operation, either return or break on success
      _sleep_between_retries(attempt, max_attempts, sleep_base)

  Args:
    attempt: Which attempt just failed (0 based).
    max_attempts: The maximum number of attempts that will be made.
    sleep_base: How long in seconds to sleep between the first and second
      attempt (the time will be doubled between each successive attempt). The
      value may be any numeric type that is convertible to float (complex
      won't work but user types that are sufficiently numeric-like will).
  """
  # Don't sleep after the last attempt as we're about to give up.
  if attempt < (max_attempts - 1):
    time.sleep((2 ** attempt) * sleep_base)


def _remove_retry_sharing_violation(path, max_attempts=10, sleep_base=.125):
  """Removes a file (with retries on Windows for sharing violations).

  Args:
    path: The filesystem path to remove.
    max_attempts: The maximum number of attempts to try to remove the path
      before giving up.
    sleep_base: How long in seconds to sleep between the first and second
      attempt (the time will be doubled between each successive attempt). The
      value may be any numeric type that is convertible to float (complex
      won't work but user types that are sufficiently numeric-like will).

  Raises:
    WindowsError: When an error other than a sharing violation occurs.
  """
  if sys.platform == 'win32':
    for attempt in range(max_attempts):
      try:
        os.remove(path)
        break
      except WindowsError as e:
        import winerror
        # Sharing violations are expected to occasionally occur when the runtime
        # instance is context swapped after writing the port but before closing
        # the file. Ignore these and try again.
        if e.winerror != winerror.ERROR_SHARING_VIOLATION:
          raise
      _sleep_between_retries(attempt, max_attempts, sleep_base)
    else:
      logging.warn('Unable to delete %s', path)
  else:
    os.remove(path)


class HttpRuntimeProxy(instance.RuntimeProxy):
  """Manages a runtime subprocess used to handle dynamic content."""

  _VALID_START_PROCESS_FLAVORS = [START_PROCESS, START_PROCESS_FILE]

  def __init__(self, args, runtime_config_getter, module_configuration,
               env=None, start_process_flavor=START_PROCESS):
    """Initializer for HttpRuntimeProxy.

    Args:
      args: Arguments to use to start the runtime subprocess.
      runtime_config_getter: A function that can be called without arguments
          and returns the runtime_config_pb2.Config containing the configuration
          for the runtime.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the configuration of the module that owns the
          runtime.
      env: A dict of environment variables to pass to the runtime subprocess.
      start_process_flavor: Which version of start process to start your
        runtime process. SUpported flavors are START_PROCESS and
        START_PROCESS_FILE.

    Raises:
      ValueError: An unknown value for start_process_flavor was used.
    """
    super(HttpRuntimeProxy, self).__init__()
    self._host = 'localhost'
    self._port = None
    self._process = None
    self._process_lock = threading.Lock()  # Lock to guard self._process.
    self._prior_error = None
    self._stderr_tee = None
    self._runtime_config_getter = runtime_config_getter
    self._args = args
    self._module_configuration = module_configuration
    self._env = env
    if start_process_flavor not in self._VALID_START_PROCESS_FLAVORS:
      raise ValueError('Invalid start_process_flavor.')
    self._start_process_flavor = start_process_flavor

  def _get_error_file(self):
    for error_handler in self._module_configuration.error_handlers or []:
      if not error_handler.error_code or error_handler.error_code == 'default':
        return os.path.join(self._module_configuration.application_root,
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
    if self._prior_error:
      yield self._handle_error(self._prior_error, start_response)
      return

    environ[http_runtime_constants.SCRIPT_HEADER] = match.expand(url_map.script)
    if request_type == instance.BACKGROUND_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'background'
    elif request_type == instance.SHUTDOWN_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'shutdown'
    elif request_type == instance.INTERACTIVE_REQUEST:
      environ[http_runtime_constants.REQUEST_TYPE_HEADER] = 'interactive'
    elif http_runtime_constants.REQUEST_TYPE_HEADER in environ:
      del environ[http_runtime_constants.REQUEST_TYPE_HEADER]

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

    prefix = http_runtime_constants.INTERNAL_HEADER_PREFIX

    # The Go runtime from the 1.9.48 SDK looks for different headers.
    if self._module_configuration.runtime == 'go':
      headers['X-Appengine-Dev-Request-Id'] = request_id
      prefix = 'X-Appengine-'

    headers[prefix + 'User-Id'] = (user_id)
    headers[prefix + 'User-Email'] = (user_email)
    headers[prefix + 'User-Is-Admin'] = (str(int(admin)))
    headers[prefix + 'User-Nickname'] = (nickname)
    headers[prefix + 'User-Organization'] = (organization)
    headers['X-AppEngine-Country'] = 'ZZ'
    connection = httplib.HTTPConnection(self._host, self._port)
    with contextlib.closing(connection):
      try:
        connection.connect()
        connection.request(environ.get('REQUEST_METHOD', 'GET'),
                           url,
                           data,
                           dict(headers.items()))

        try:
          response = connection.getresponse()
        except httplib.HTTPException as e:
          # The runtime process has written a bad HTTP response. For example,
          # a Go runtime process may have crashed in app-specific code.
          yield self._handle_error(
              'the runtime process gave a bad HTTP response: %s' % e,
              start_response)
          return

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
        while True:
          try:
            block = response.read(512)
            if not block:
              break
            yield block
          except httplib.HTTPException:
            # The runtime process has encountered a problem, but has not
            # necessarily crashed. For example, a Go runtime process' HTTP
            # handler may have panicked in app-specific code (which the http
            # package will recover from, so the process as a whole doesn't
            # crash). At this point, we have already proxied onwards the HTTP
            # header, so we cannot retroactively serve a 500 Internal Server
            # Error. We silently break here; the runtime process has presumably
            # already written to stderr (via the Tee).
            break
      except Exception:
        with self._process_lock:
          if self._process and self._process.poll() is not None:
            # The development server is in a bad state. Log and return an error
            # message.
            self._prior_error = ('the runtime process for the instance running '
                                 'on port %d has unexpectedly quit' % (
                                     self._port))
            yield self._handle_error(self._prior_error, start_response)
          else:
            raise

  def _handle_error(self, message, start_response):
    # Give the runtime process a bit of time to write to stderr.
    time.sleep(0.1)
    buf = self._stderr_tee.get_buf()
    if buf:
      message = message + '\n\n' + buf
    # TODO: change 'text/plain' to 'text/plain; charset=utf-8'
    # throughout devappserver2.
    start_response('500 Internal Server Error',
                   [('Content-Type', 'text/plain'),
                    ('Content-Length', str(len(message)))])
    return message

  def _read_start_process_file(self, max_attempts=10, sleep_base=.125):
    """Read the single line response expected in the start process file.

    The START_PROCESS_FILE flavor uses a file for the runtime instance to
    report back the port it is listening on. We can't rely on EOF semantics
    as that is a race condition when the runtime instance is simultaneously
    writing the file while the devappserver process is reading it; rather we
    rely on the line being terminated with a newline.

    Args:
      max_attempts: The maximum number of attempts to read the line.
      sleep_base: How long in seconds to sleep between the first and second
        attempt (the time will be doubled between each successive attempt). The
        value may be any numeric type that is convertible to float (complex
        won't work but user types that are sufficiently numeric-like will).

    Returns:
      If a full single line (as indicated by a newline terminator) is found, all
      data read up to that point is returned; return an empty string if no
      newline is read before the process exits or the max number of attempts are
      made.
    """
    try:
      for attempt in range(max_attempts):
        # Yes, the final data may already be in the file even though the
        # process exited. That said, since the process should stay alive
        # if it's exited we don't care anyway.
        if self._process.poll() is not None:
          return ''
        # On Mac, if the first read in this process occurs before the data is
        # written, no data will ever be read by this process without the seek.
        self._process.child_out.seek(0)
        line = self._process.child_out.read()
        if '\n' in line:
          return line
        _sleep_between_retries(attempt, max_attempts, sleep_base)
    finally:
      self._process.child_out.close()
    return ''

  def start(self):
    """Starts the runtime process and waits until it is ready to serve."""
    runtime_config = self._runtime_config_getter()
    # TODO: Use a different process group to isolate the child process
    # from signals sent to the parent. Only available in subprocess in
    # Python 2.7.
    assert self._start_process_flavor in self._VALID_START_PROCESS_FLAVORS
    if self._start_process_flavor == START_PROCESS:
      serialized_config = base64.b64encode(runtime_config.SerializeToString())
      with self._process_lock:
        assert not self._process, 'start() can only be called once'
        self._process = safe_subprocess.start_process(
            self._args,
            serialized_config,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
            cwd=self._module_configuration.application_root)
      line = self._process.stdout.readline()
    elif self._start_process_flavor == START_PROCESS_FILE:
      serialized_config = runtime_config.SerializeToString()
      with self._process_lock:
        assert not self._process, 'start() can only be called once'
        self._process = safe_subprocess.start_process_file(
            args=self._args,
            input_string=serialized_config,
            env=self._env,
            cwd=self._module_configuration.application_root,
            stderr=subprocess.PIPE)
      line = self._read_start_process_file()
      _remove_retry_sharing_violation(self._process.child_out.name)

    # _stderr_tee may be pre-set by unit tests.
    if self._stderr_tee is None:
      self._stderr_tee = tee.Tee(self._process.stderr, sys.stderr)
      self._stderr_tee.start()
    self._prior_error = None
    self._port = None
    try:
      # Older runtimes output just the port, while newer ones prepend the host.
      self._port = int(line.split()[-1])
    except ValueError:
      self._prior_error = 'bad runtime process port [%r]' % line
      logging.error(self._prior_error)
    else:
      # Check if the runtime can serve requests.
      if not self._can_connect():
        self._prior_error = 'cannot connect to runtime on port %r' % self._port
        logging.error(self._prior_error)

  def _can_connect(self):
    connection = httplib.HTTPConnection(self._host, self._port)
    with contextlib.closing(connection):
      try:
        connection.connect()
      except socket.error:
        return False
      else:
        return True

  def quit(self):
    """Causes the runtime process to exit."""
    with self._process_lock:
      assert self._process, 'module was not running'
      try:
        self._process.kill()
      except OSError:
        pass
      # Mac leaks file descriptors without call to join. Suspect a race
      # condition where the interpreter is unable to close the subprocess pipe
      # as the thread hasn't returned from the readline call.
      self._stderr_tee.join(5)
      self._process = None
