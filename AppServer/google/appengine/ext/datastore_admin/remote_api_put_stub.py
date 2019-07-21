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
to the local backends *except* for datastore_v3 Put and datastore_v4
AllocateIds calls where the key contains a remote app_id.

Calls to datastore_v3 Put and datastore_v4 AllocateIds for which the entity
keys contain a remote app_id are sent to the remote app.

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


class RemoteApiDatastoreStub(object):
  """A specialised stub for writing to a remote App Engine datastore.

  This class supports checking the app_id of a datastore op and either passing
  the request through to the local app or sending it to a remote app.
  Subclassed to implement supported services datastore_v3 and datastore_v4.
  """


  _SERVICE_NAME = None

  def __init__(self, remote_url, target_app_id, extra_headers, normal_stub):
    """Constructor.

    Args:
      remote_url: The URL of the remote_api handler.
      target_app_id: The app_id to intercept calls for.
      extra_headers: Headers to send (for authentication).
      normal_stub: The standard stub to delegate most calls to.
    """
    self.remote_url = remote_url
    self.target_app_id = target_app_id
    self.extra_headers = InsertDefaultExtraHeaders(extra_headers)
    self.normal_stub = normal_stub

  def CreateRPC(self):
    """Creates RPC object instance.

    Returns:
      a instance of RPC.
    """
    return apiproxy_rpc.RPC(stub=self)

  @classmethod
  def ServiceName(cls):
    """Return the name of the datastore service supported by this stub."""
    return cls._SERVICE_NAME

  def MakeSyncCall(self, service, call, request, response):
    """Handle all calls to this stub; delegate as appropriate."""
    assert service == self.ServiceName(), '%s does not support service %s' % (
        type(self), service)

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


class RemoteApiDatastoreV3Stub(RemoteApiDatastoreStub):
  """A specialised stub for calling datastore_v3 Put on a foreign datastore.

  This stub passes through all requests to the normal stub except for
  datastore v3 Put. It will check those to see if the put is for the local app
  or a remote app, and if remote will send traffic remotely.
  """

  _SERVICE_NAME = 'datastore_v3'

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
      if entity.has_key() and entity.key().app() == self.target_app_id:
        if request.has_transaction():


          raise RemoteTransactionsUnimplemented()
        self._MakeRemoteSyncCall(self.ServiceName(), 'Put', request, response)
        return


    self.normal_stub.MakeSyncCall(self.ServiceName(), 'Put', request, response)


class RemoteApiDatastoreV4Stub(RemoteApiDatastoreStub):
  """A remote api stub to call datastore_v4 AllocateIds on a foreign datastore.

  This stub passes through all requests to the normal datastore_v4 stub except
  for datastore v4 AllocateIds. It will check those to see if the keys are for
  the local app or a remote app, and if remote will send traffic remotely.
  """

  _SERVICE_NAME = 'datastore_v4'

  def _Dynamic_AllocateIds(self, request, response):
    """Handle v4 AllocateIds and route remotely if it matches the target app.

    Args:
      request: A datastore_v4_pb.AllocateIdsRequest
      response: A datastore_v4_pb.AllocateIdsResponse
    """

    if request.reserve_size() > 0:
      app_id = request.reserve(0).partition_id().dataset_id()
    elif request.allocate_size() > 0:
      app_id = request.allocate(0).partition_id().dataset_id()
    else:
      app_id = None

    if app_id == self.target_app_id:
      self._MakeRemoteSyncCall(self.ServiceName(), 'AllocateIds', request,
                               response)
    else:
      self.normal_stub.MakeSyncCall(self.ServiceName(), 'AllocateIds', request,
                                    response)



def get_remote_app_id(remote_url, extra_headers=None):
  """Get the app_id from the remote_api endpoint.

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
                                       extra_headers, follow_redirects=False,
                                       deadline=10)
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
        'Invalid response received from server: %s' % response)
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


def InsertDefaultExtraHeaders(extra_headers):
  """Add defaults to extra_headers arg for stub configuration.

  This permits comparison of a proposed RemoteApiDatastoreStub config with
  an existing config.

  Args:
    extra_headers: The dict of headers to transform.

  Returns:
    A new copy of the input dict with defaults set.
  """
  extra_headers = extra_headers.copy() if extra_headers else {}
  if 'X-appcfg-api-version' not in extra_headers:
    extra_headers['X-appcfg-api-version'] = '1'
  return extra_headers


def StubConfigEqualsRequestedConfig(stub, remote_url, target_app_id,
                                    extra_headers):
  """Return true if the stub and requseted stub config match.

  Args:
    stub: a RemoteApiDatastore stub.
    remote_url: requested remote_api url of target app.
    target_app_id: requested app_id of target (remote) app.
    extra_headers: requested headers for auth, possibly not yet including
      defaults applied at stub instantiation time.

  Returns:
    True if the requested config matches the stub, else False.
  """
  return (stub.remote_url == remote_url and
          stub.target_app_id == target_app_id and
          stub.extra_headers == InsertDefaultExtraHeaders(extra_headers))


def configure_remote_put(remote_url, target_app_id, extra_headers=None):
  """Does necessary setup to intercept v3 Put and v4 AllocateIds.

  Args:
    remote_url: The url to the remote_api handler.
    target_app_id: The app_id of the target app.
    extra_headers: Headers to send (for authentication).

  Raises:
    ConfigurationError: if there is a error configuring the stubs.
  """
  if not target_app_id or not remote_url:
    raise ConfigurationError('app_id and remote_url required')

  for stub_class in (RemoteApiDatastoreV3Stub, RemoteApiDatastoreV4Stub):
    service_name = stub_class.ServiceName()
    original_datastore_stub = apiproxy_stub_map.apiproxy.GetStub(service_name)
    if isinstance(original_datastore_stub, stub_class):
      logging.info('Datastore Admin %s RemoteApi stub is already configured.',
                   service_name)
      if not StubConfigEqualsRequestedConfig(
          original_datastore_stub, remote_url, target_app_id, extra_headers):
        logging.warning('Requested Datastore Admin %s RemoteApi stub '
                        'configuration differs from existing configuration, '
                        'attempting reconfiguration.', service_name)
        datastore_stub = stub_class(remote_url, target_app_id, extra_headers,
                                    original_datastore_stub.normal_stub)
        apiproxy_stub_map.apiproxy.ReplaceStub(service_name, datastore_stub)
    else:
      datastore_stub = stub_class(remote_url, target_app_id, extra_headers,
                                  original_datastore_stub)
      apiproxy_stub_map.apiproxy.RegisterStub(service_name, datastore_stub)
