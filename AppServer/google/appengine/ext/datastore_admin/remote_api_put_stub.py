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




"""An apiproxy stub that calls a remote handler via HTTP.

This is a special version of the remote_api_stub which sends all traffic
to the local backends *except* for datastore.put calls where the key
contains a remote app_id.

It re-implements parts of the remote_api_stub so as to replace dependencies on
the (SDK only) appengine_rpc with urlfetch.
"""








import logging
import pickle
import random
import yaml

from google.appengine.api import apiproxy_rpc
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import urlfetch
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base class for exceptions in this module."""


class ConfigurationError(Error):
  """Exception for configuration errors."""


class FetchFailed(Exception):
  """Remote fetch failed."""


class UnknownJavaServerError(Error):
  """Exception for exceptions returned from a Java remote_api handler."""


class RemoteTransactionsUnimplemented(Error):
  """Remote Put requests do not support transactions."""


class DatastorePutStub(object):
  """A specialised stub for sending "puts" to a remote  App Engine datastore.

  This stub passes through all requests to the normal stub except for
  datastore put. It will check those to see if the put is for the local app
  or a remote app, and if remote will send traffic remotely.
  """

  def __init__(self, remote_url, target_appid, extra_headers, normal_stub):
    """Constructor.

    Args:
      remote_url: The URL of the remote_api handler.
      target_appid: The appid to intercept calls for.
      extra_headers: Headers to send (for authentication).
      normal_stub: The standard stub to delegate most calls to.
    """
    self.remote_url = remote_url
    self.target_appid = target_appid
    self.extra_headers = extra_headers or {}
    if 'X-appcfg-api-version' not in self.extra_headers:
      self.extra_headers['X-appcfg-api-version'] = '1'
    self.normal_stub = normal_stub

  def CreateRPC(self):
    """Creates RPC object instance.

    Returns:
      a instance of RPC.
    """
    return apiproxy_rpc.RPC(stub=self)

  def MakeSyncCall(self, service, call, request, response):
    """Handle all calls to this stub; delegate as appropriate."""
    assert service == 'datastore_v3'

    explanation = []
    assert request.IsInitialized(explanation), explanation

    handler = getattr(self, '_Dynamic_' + call, None)
    if handler:
      handler(request, response)
    else:
      self.normal_stub.MakeSyncCall(service, call, request, response)

    assert response.IsInitialized(explanation), explanation

  def _MakeRemoteSyncCall(self, service, call, request, response):
    """Send an RPC to a remote_api endpoint."""
    request_pb = remote_api_pb.Request()
    request_pb.set_service_name(service)
    request_pb.set_method(call)
    request_pb.set_request(request.Encode())

    response_pb = remote_api_pb.Response()
    encoded_request = request_pb.Encode()
    try:
      urlfetch_response = urlfetch.fetch(self.remote_url, encoded_request,
                                         urlfetch.POST, self.extra_headers,
                                         follow_redirects=False,
                                         deadline=10)
    except Exception, e:


      logging.exception('Fetch failed to %s', self.remote_url)
      raise FetchFailed(e)
    if urlfetch_response.status_code != 200:
      logging.error('Fetch failed to %s; Status %s; body %s',
                    self.remote_url,
                    urlfetch_response.status_code,
                    urlfetch_response.content)
      raise FetchFailed(urlfetch_response.status_code)
    response_pb.ParseFromString(urlfetch_response.content)

    if response_pb.has_application_error():
      error_pb = response_pb.application_error()
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())
    elif response_pb.has_exception():
      raise pickle.loads(response_pb.exception())
    elif response_pb.has_java_exception():
      raise UnknownJavaServerError('An unknown error has occured in the '
                                   'Java remote_api handler for this call.')
    else:
      response.ParseFromString(response_pb.response())

  def _Dynamic_Put(self, request, response):
    """Handle a Put request and route remotely if it matches the target app.

    Args:
      request: A datastore_pb.PutRequest
      response: A datastore_pb.PutResponse

    Raises:
      RemoteTransactionsUnimplemented: Remote transactions are unimplemented.
    """

    if request.entity_list():
      entity = request.entity(0)
      if entity.has_key() and entity.key().app() == self.target_appid:
        if request.has_transaction():


          raise RemoteTransactionsUnimplemented()
        self._MakeRemoteSyncCall('datastore_v3', 'Put', request, response)
        return


    self.normal_stub.MakeSyncCall('datastore_v3', 'Put', request, response)




  def _Dynamic_AllocateIds(self, request, response):
    """Handle AllocateIds and route remotely if it matches the target app.

    Args:
      request: A datastore_pb.AllocateIdsRequest
      response: A datastore_pb.AllocateIdsResponse
    """
    if request.model_key().app() == self.target_appid:
      self._MakeRemoteSyncCall('datastore_v3', 'AllocateIds', request, response)
    else:
      self.normal_stub.MakeSyncCall('datastore_v3', 'AllocateIds', request,
                                    response)


def get_remote_appid(remote_url, extra_headers=None):
  """Get the appid from the remote_api endpoint.

  This also has the side effect of verifying that it is a remote_api endpoint.

  Args:
    remote_url: The url to the remote_api handler.
    extra_headers: Headers to send (for authentication).

  Returns:
    app_id: The app_id of the target app.

  Raises:
    FetchFailed: Urlfetch call failed.
    ConfigurationError: URLfetch suceeded but results were invalid.
  """
  rtok = str(random.random())[2:]
  url = remote_url + '?rtok=' + rtok
  if not extra_headers:
    extra_headers = {}
  if 'X-appcfg-api-version' not in extra_headers:
    extra_headers['X-appcfg-api-version'] = '1'
  try:
    urlfetch_response = urlfetch.fetch(url, None, urlfetch.GET,
                                       extra_headers, follow_redirects=False)
  except Exception, e:


    logging.exception('Fetch failed to %s', remote_url)
    raise FetchFailed('Fetch to %s failed: %r' % (remote_url, e))
  if urlfetch_response.status_code != 200:
    logging.error('Fetch failed to %s; Status %s; body %s',
                  remote_url,
                  urlfetch_response.status_code,
                  urlfetch_response.content)
    raise FetchFailed('Fetch to %s failed with status %s' %
                      (remote_url, urlfetch_response.status_code))
  response = urlfetch_response.content
  if not response.startswith('{'):
    logging.info('Response unparasable: %s', response)
    raise ConfigurationError(
        'Invalid response recieved from server: %s' % response)
  app_info = yaml.load(response)
  if not app_info or 'rtok' not in app_info or 'app_id' not in app_info:
    logging.info('Response unparsable: %s', response)
    raise ConfigurationError('Error parsing app_id lookup response')
  if str(app_info['rtok']) != rtok:
    logging.info('Response invalid token (expected %s): %s', rtok, response)
    raise ConfigurationError('Token validation failed during app_id lookup. '
                             '(sent %s, got %s)' % (repr(rtok),
                                                    repr(app_info['rtok'])))
  return app_info['app_id']


def configure_remote_put(remote_url, app_id, extra_headers=None):
  """Does necessary setup to intercept PUT.

  Args:
    remote_url: The url to the remote_api handler.
    app_id: The app_id of the target app.
    extra_headers: Headers to send (for authentication).

  Raises:
    ConfigurationError: if there is a error configuring the stub.
  """
  if not app_id or not remote_url:
    raise ConfigurationError('app_id and remote_url required')



  original_datastore_stub = apiproxy_stub_map.apiproxy.GetStub('datastore_v3')
  if isinstance(original_datastore_stub, DatastorePutStub):

    logging.info('Stub is already configured. Hopefully in a matching fashion.')
    return
  datastore_stub = DatastorePutStub(remote_url, app_id, extra_headers,
                                    original_datastore_stub)
  apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', datastore_stub)
