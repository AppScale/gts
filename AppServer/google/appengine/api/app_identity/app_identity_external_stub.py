""" App identity stub service implementation.

This just forwards calls to an external server.
"""

import pickle
import urllib2

from google.appengine.api import apiproxy_stub
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext.remote_api import remote_api_pb


class AppIdentityExternalStub(apiproxy_stub.APIProxyStub):
  """ A proxy for the AppIdentityService API. """
  THREADSAFE = True

  def __init__(self, location, service_name='app_identity_service'):
    """ Constructor.

    Args:
      location: The location of a server that handles App Identity requests.
    """
    super(AppIdentityExternalStub, self).__init__(service_name)
    self._location = location
    self._max_request_size = apiproxy_stub.MAX_REQUEST_SIZE
    self._service_name = service_name

  def MakeSyncCall(self, service, call, request, response, request_id=None):
    """ The main RPC entry point.

    Args:
      service: Must be name as provided to service_name of constructor.
      call: A string representing the rpc to make.  Must be part of
        the underlying services methods and impemented by _Dynamic_<call>.
      request: A protocol buffer of the type corresponding to 'call'.
      response: A protocol buffer of the type corresponding to 'call'.
      request_id: A unique string identifying the request associated with the
          API call.
    """
    assert service == self._service_name, ('Expected "%s" service name, '
                                           'was "%s"' % (self._service_name,
                                                         service))

    if request.ByteSize() > self._max_request_size:
      raise apiproxy_errors.RequestTooLargeError(
          'The request to API call %s.%s() was too large.' % (service, call))

    messages = []
    assert request.IsInitialized(messages), messages

    remote_api_request = remote_api_pb.Request()
    remote_api_request.set_service_name(service)
    remote_api_request.set_method(call)
    remote_api_request.set_request(request.Encode())
    if request_id is not None:
      remote_api_request.set_request_id(request_id)

    url = 'http://{}'.format(self._location)
    request_handle = urllib2.Request(url, remote_api_request.Encode())
    response_handle = urllib2.urlopen(request_handle)
    remote_api_response = remote_api_pb.Response(response_handle.read())
    if remote_api_response.has_application_error():
      error_pb = remote_api_response.application_error()
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())

    if remote_api_response.has_exception():
      raise pickle.loads(remote_api_response.exception())

    response.ParseFromString(remote_api_response.response())
