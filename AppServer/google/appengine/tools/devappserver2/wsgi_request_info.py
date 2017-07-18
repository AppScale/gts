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
"""Associates request state, derived from a WSGI environ, with a unique id."""


import contextlib
import random
import string
import threading
import wsgiref.util

from google.appengine.api import request_info


def _choose_request_id():
  return ''.join(random.choice(string.ascii_letters) for _ in range(10))


class WSGIRequestInfo(request_info.RequestInfo):
  """Associates request state, derived from a WSGI environ, with a unique id."""

  def __init__(self, dispatcher):
    """Initializer for WSGIRequestInfo.

    Args:
      dispatcher: A request_info.Dispatcher instance to provide to API stubs.
    """
    super(WSGIRequestInfo, self).__init__()
    self._request_wsgi_environ = {}
    self._request_id_to_module_configuration = {}
    self._request_id_to_instance = {}
    self._lock = threading.Lock()
    self._dispatcher = dispatcher

  @contextlib.contextmanager
  def request(self, environ, module_configuration):
    """A context manager that consumes a WSGI environ and returns a request id.

    with request_information.request(environ, app_info_external) as request_id:
      # Stubs will have access to the state associated with request_id only in
      # this context.
      send_request_to_runtime(request_id, ...)

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the current module configuration.

    Returns:
      A unique string id that will be associated with the request.
    """
    request_id = self.start_request(environ, module_configuration)
    yield request_id
    self.end_request(request_id)

  def start_request(self, environ, module_configuration):
    """Adds the WSGI to the state of the class and returns a request id.

    Args:
      environ: An environ dict for the request as defined in PEP-333.
      module_configuration: An application_configuration.ModuleConfiguration
          instance respresenting the current module configuration.

    Returns:
      A unique string id that will be associated with the request.
    """
    with self._lock:
      request_id = _choose_request_id()
      self._request_wsgi_environ[request_id] = environ
      self._request_id_to_module_configuration[
          request_id] = module_configuration
      return request_id

  def end_request(self, request_id):
    """Removes the information associated with given request_id."""
    with self._lock:
      del self._request_wsgi_environ[request_id]
      del self._request_id_to_module_configuration[request_id]
      if request_id in self._request_id_to_instance:
        del self._request_id_to_instance[request_id]

  def set_request_instance(self, request_id, instance):
    with self._lock:
      self._request_id_to_instance[request_id] = instance

  def get_request_url(self, request_id, scheme=None):
    """Returns the URL the request e.g. 'http://localhost:8080/foo?bar=baz'.

    Args:
      request_id: The string id of the request making the API call.
      scheme: A string, the protocol to be used for this request URL.

    Returns:
      The URL of the request as a string.
    """
    with self._lock:
      environ = self._request_wsgi_environ[request_id]
      url = wsgiref.util.request_uri(environ)
      if scheme is not None:
        url = "{0}{1}".format(scheme, url[url.find(':'):])
      return url

  def get_request_environ(self, request_id):
    """Returns a dict containing the WSGI environ for the request."""
    with self._lock:
      return self._request_wsgi_environ[request_id]

  def get_dispatcher(self):
    """Returns the Dispatcher.

    Returns:
      The Dispatcher instance.
    """
    return self._dispatcher

  def get_module(self, request_id):
    """Returns the name of the module serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the module name.
    """
    with self._lock:
      return self._request_id_to_module_configuration[request_id].module_name

  def get_version(self, request_id):
    """Returns the version of the module serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      A str containing the version.
    """
    with self._lock:
      return self._request_id_to_module_configuration[request_id].major_version

  def get_instance(self, request_id):
    """Returns the instance serving this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      The instance.Instance serving this request or None if no instance is
      serving it.
    """
    with self._lock:
      return self._request_id_to_instance.get(request_id, None)

  def get_scheme(self, request_id):
    """Returns the scheme for this request.

    Args:
      request_id: The string id of the request making the API call.

    Returns:
      One of 'http', 'https'.
    """
    with self._lock:
      scheme = 'http'
      environ = self._request_wsgi_environ[request_id]
      if environ['HTTP_X_FORWARDED_PROTO'] is not None:
        scheme = environ['HTTP_X_FORWARDED_PROTO']
      return scheme
