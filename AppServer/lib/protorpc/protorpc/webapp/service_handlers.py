#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
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

"""Handlers for remote services.

This module contains classes that may be used to build a service
on top of the App Engine Webapp framework.

The services request handler can be configured to handle requests in a number
of different request formats.  All different request formats must have a way
to map the request to the service handlers defined request message.Message
class.  The handler can also send a response in any format that can be mapped
from the response message.Message class.

Participants in an RPC:

  There are four classes involved with the life cycle of an RPC.

    Service factory: A user-defined service factory that is responsible for
      instantiating an RPC service.  The methods intended for use as RPC
      methods must be decorated by the 'remote' decorator.

    RPCMapper: Responsible for determining whether or not a specific request
      matches a particular RPC format and translating between the actual
      request/response and the underlying message types.  A single instance of
      an RPCMapper sub-class is required per service configuration.  Each
      mapper must be usable across multiple requests.

    ServiceHandler: A webapp.RequestHandler sub-class that responds to the
      webapp framework.  It mediates between the RPCMapper and service
      implementation class during a request.  As determined by the Webapp
      framework, a new ServiceHandler instance is created to handle each
      user request.  A handler is never used to handle more than one request.

    ServiceHandlerFactory: A class that is responsible for creating new,
      properly configured ServiceHandler instance for each request.  The
      factory is configured by providing it with a set of RPCMapper instances.
      When the Webapp framework invokes the service handler, the handler
      creates a new service class instance.  The service class instance is
      provided with a reference to the handler.  A single instance of an
      RPCMapper sub-class is required to configure each service.  Each mapper
      instance must be usable across multiple requests.

RPC mappers:

  RPC mappers translate between a single HTTP based RPC protocol and the
  underlying service implementation.  Each RPC mapper must configured
  with the following information to determine if it is an appropriate
  mapper for a given request:

    http_methods: Set of HTTP methods supported by handler.

    content_types: Set of supported content types.

    default_content_type: Default content type for handler responses.

  Built-in mapper implementations:

    URLEncodedRPCMapper: Matches requests that are compatible with post
      forms with the 'application/x-www-form-urlencoded' content-type
      (this content type is the default if none is specified.  It
      translates post parameters into request parameters.

    ProtobufRPCMapper: Matches requests that are compatible with post
      forms with the 'application/x-google-protobuf' content-type.  It
      reads the contents of a binary post request.

Public Exceptions:
  Error: Base class for service handler errors.
  ServiceConfigurationError: Raised when a service not correctly configured.
  RequestError: Raised by RPC mappers when there is an error in its request
    or request format.
  ResponseError: Raised by RPC mappers when there is an error in its response.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'


import array
import cgi
import itertools
import httplib
import logging
import re
import sys
import traceback
import urllib
import weakref

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util as webapp_util
from .. import messages
from .. import protobuf
from .. import protojson
from .. import protourlencode
from .. import registry
from .. import remote
from .. import util
from . import forms

__all__ = [
    'Error',
    'RequestError',
    'ResponseError',
    'ServiceConfigurationError',

    'DEFAULT_REGISTRY_PATH',

    'ProtobufRPCMapper',
    'RPCMapper',
    'ServiceHandler',
    'ServiceHandlerFactory',
    'URLEncodedRPCMapper',
    'JSONRPCMapper',
    'service_mapping',
    'run_services',
]


class Error(Exception):
  """Base class for all errors in service handlers module."""


class ServiceConfigurationError(Error):
  """When service configuration is incorrect."""


class RequestError(Error):
  """Error occurred when building request."""


class ResponseError(Error):
  """Error occurred when building response."""


_URLENCODED_CONTENT_TYPE = protourlencode.CONTENT_TYPE
_PROTOBUF_CONTENT_TYPE = protobuf.CONTENT_TYPE
_JSON_CONTENT_TYPE = protojson.CONTENT_TYPE

_EXTRA_JSON_CONTENT_TYPES = ['application/x-javascript',
                             'text/javascript',
                             'text/x-javascript',
                             'text/x-json',
                             'text/json',
                            ]

# The whole method pattern is an optional regex.  It contains a single
# group used for mapping to the query parameter.  This is passed to the
# parameters of 'get' and 'post' on the ServiceHandler.
_METHOD_PATTERN = r'(?:\.([^?]*))?'

DEFAULT_REGISTRY_PATH = forms.DEFAULT_REGISTRY_PATH


class RPCMapper(object):
  """Interface to mediate between request and service object.

  Request mappers are implemented to support various types of
  RPC protocols.  It is responsible for identifying whether a
  given request matches a particular protocol, resolve the remote
  method to invoke and mediate between the request and appropriate
  protocol messages for the remote method.
  """

  @util.positional(4)
  def __init__(self,
               http_methods,
               default_content_type,
               protocol,
               content_types=None):
    """Constructor.

    Args:
      http_methods: Set of HTTP methods supported by mapper.
      default_content_type: Default content type supported by mapper.
      protocol: The protocol implementation.  Must implement encode_message and
        decode_message.
      content_types: Set of additionally supported content types.
    """
    self.__http_methods = frozenset(http_methods)
    self.__default_content_type = default_content_type
    self.__protocol = protocol

    if content_types is None:
      content_types = []
    self.__content_types = frozenset([self.__default_content_type] +
                                     content_types)

  @property
  def http_methods(self):
    return self.__http_methods

  @property
  def default_content_type(self):
    return self.__default_content_type

  @property
  def content_types(self):
    return self.__content_types

  def build_request(self, handler, request_type):
    """Build request message based on request.

    Each request mapper implementation is responsible for converting a
    request to an appropriate message instance.

    Args:
      handler: RequestHandler instance that is servicing request.
        Must be initialized with request object and been previously determined
        to matching the protocol of the RPCMapper.
      request_type: Message type to build.

    Returns:
      Instance of request_type populated by protocol buffer in request body.

    Raises:
      RequestError if the mapper implementation is not able to correctly
      convert the request to the appropriate message.
    """
    try:
      return self.__protocol.decode_message(request_type, handler.request.body)
    except (messages.ValidationError, messages.DecodeError), err:
      raise RequestError('Unable to parse request content: %s' % err)

  def build_response(self, handler, response, pad_string=False):
    """Build response based on service object response message.

    Each request mapper implementation is responsible for converting a
    response message to an appropriate handler response.

    Args:
      handler: RequestHandler instance that is servicing request.
        Must be initialized with request object and been previously determined
        to matching the protocol of the RPCMapper.
      response: Response message as returned from the service object.

    Raises:
      ResponseError if the mapper implementation is not able to correctly
      convert the message to an appropriate response.
    """
    try:
      encoded_message = self.__protocol.encode_message(response)
    except messages.ValidationError, err:
      raise ResponseError('Unable to encode message: %s' % err)
    else:
      handler.response.headers['Content-Type'] = self.default_content_type
      handler.response.out.write(encoded_message)


class ServiceHandlerFactory(object):
  """Factory class used for instantiating new service handlers.

  Normally a handler class is passed directly to the webapp framework
  so that it can be simply instantiated to handle a single request.
  The service handler, however, must be configured with additional
  information so that it knows how to instantiate a service object.
  This class acts the same as a normal RequestHandler class by
  overriding the __call__ method to correctly configures a ServiceHandler
  instance with a new service object.

  The factory must also provide a set of RPCMapper instances which
  examine a request to determine what protocol is being used and mediates
  between the request and the service object.

  The mapping of a service handler must have a single group indicating the
  part of the URL path that maps to the request method.  This group must
  exist but can be optional for the request (the group may be followed by
  '?' in the regular expression matching the request).

  Usage:

    stock_factory = ServiceHandlerFactory(StockService)
    ... configure stock_factory by adding RPCMapper instances ...

    application = webapp.WSGIApplication(
        [stock_factory.mapping('/stocks')])

  Default usage:

    application = webapp.WSGIApplication(
        [ServiceHandlerFactory.default(StockService).mapping('/stocks')])
  """

  def __init__(self, service_factory):
    """Constructor.

    Args:
      service_factory: Service factory to instantiate and provide to
        service handler.
    """
    self.__service_factory = service_factory
    self.__request_mappers = []

  def all_request_mappers(self):
    """Get all request mappers.

    Returns:
      Iterator of all request mappers used by this service factory.
    """
    return iter(self.__request_mappers)

  def add_request_mapper(self, mapper):
    """Add request mapper to end of request mapper list."""
    self.__request_mappers.append(mapper)

  def __call__(self):
    """Construct a new service handler instance."""
    return ServiceHandler(self, self.__service_factory())

  @property
  def service_factory(self):
    """Service factory associated with this factory."""
    return self.__service_factory

  @staticmethod
  def __check_path(path):
    """Check a path parameter.

    Make sure a provided path parameter is compatible with the
    webapp URL mapping.

    Args:
      path: Path to check.  This is a plain path, not a regular expression.

    Raises:
      ValueError if path does not start with /, path ends with /.
    """
    if path.endswith('/'):
      raise ValueError('Path %s must not end with /.' % path)

  def mapping(self, path):
    """Convenience method to map service to application.

    Args:
      path: Path to map service to.  It must be a simple path
        with a leading / and no trailing /.

    Returns:
      Mapping from service URL to service handler factory.
    """
    self.__check_path(path)

    service_url_pattern = r'(%s)%s' % (path, _METHOD_PATTERN)

    return service_url_pattern, self

  @classmethod
  def default(cls, service_factory, parameter_prefix=''):
    """Convenience method to map default factory configuration to application.

    Creates a standardized default service factory configuration that pre-maps
    the URL encoded protocol handler to the factory.

    Args:
      service_factory: Service factory to instantiate and provide to
        service handler.
      method_parameter: The name of the form parameter used to determine the
        method to invoke used by the URLEncodedRPCMapper.  If None, no
        parameter is used and the mapper will only match against the form
        path-name.  Defaults to 'method'.
      parameter_prefix: If provided, all the parameters in the form are
        expected to begin with that prefix by the URLEncodedRPCMapper.

    Returns:
      Mapping from service URL to service handler factory.
    """
    factory = cls(service_factory)

    factory.add_request_mapper(ProtobufRPCMapper())
    factory.add_request_mapper(JSONRPCMapper())

    return factory


class ServiceHandler(webapp.RequestHandler):
  """Web handler for RPC service.

  Overridden methods:
    get: All requests handled by 'handle' method.  HTTP method stored in
      attribute.  Takes remote_method parameter as derived from the URL mapping.
    post: All requests handled by 'handle' method.  HTTP method stored in
      attribute.  Takes remote_method parameter as derived from the URL mapping.
    redirect: Not implemented for this service handler.

  New methods:
    handle: Handle request for both GET and POST.

  Attributes (in addition to attributes in RequestHandler):
    service: Service instance associated with request being handled.
    method: Method of request.  Used by RPCMapper to determine match.
    remote_method: Sub-path as provided to the 'get' and 'post' methods.
  """

  def __init__(self, factory, service):
    """Constructor.

    Args:
      factory: Instance of ServiceFactory used for constructing new service
        instances used for handling requests.
      service: Service instance used for handling RPC.
    """
    self.__factory = factory
    self.__service = service

  @property
  def service(self):
    return self.__service

  def __show_info(self, service_path, remote_method):
    self.response.headers['content-type'] = 'text/plain; charset=utf-8'
    response_message = []
    if remote_method:
      response_message.append('%s.%s is a ProtoRPC method.\n\n' %(
        service_path, remote_method))
    else:
      response_message.append('%s is a ProtoRPC service.\n\n' % service_path)
    definition_name_function = getattr(self.__service, 'definition_name', None)
    if definition_name_function:
      definition_name = definition_name_function()
    else:
      definition_name = '%s.%s' % (self.__service.__module__,
                                   self.__service.__class__.__name__)

    response_message.append('Service %s\n\n' % definition_name)
    response_message.append('More about ProtoRPC: ')
      
    response_message.append('http://code.google.com/p/google-protorpc\n')
    self.response.out.write(util.pad_string(''.join(response_message)))

  def get(self, service_path, remote_method):
    """Handler method for GET requests.

    Args:
      service_path: Service path derived from request URL.
      remote_method: Sub-path after service path has been matched.
    """
    self.handle('GET', service_path, remote_method)

  def post(self, service_path, remote_method):
    """Handler method for POST requests.

    Args:
      service_path: Service path derived from request URL.
      remote_method: Sub-path after service path has been matched.
    """
    self.handle('POST', service_path, remote_method)

  def redirect(self, uri, permanent=False):
    """Not supported for services."""
    raise NotImplementedError('Services do not currently support redirection.')

  def __send_error(self,
                   http_code,
                   status_state,
                   error_message,
                   mapper,
                   error_name=None):
    status = remote.RpcStatus(state=status_state,
                              error_message=error_message,
                              error_name=error_name)
    mapper.build_response(self, status)
    self.response.headers['content-type'] = mapper.default_content_type

    logging.error(error_message)
    response_content = self.response.out.getvalue()
    padding = ' ' * max(0, 512 - len(response_content))
    self.response.out.write(padding)

    self.response.set_status(http_code, error_message)

  def __send_simple_error(self, code, message, pad=True):
    """Send error to caller without embedded message."""
    self.response.headers['content-type'] = 'text/plain; charset=utf-8'
    logging.error(message)
    self.response.set_status(code, message)

    response_message = httplib.responses.get(code, 'Unknown Error')
    if pad:
      response_message = util.pad_string(response_message)
    self.response.out.write(response_message)

  def __get_content_type(self):
    content_type = self.request.headers.get('content-type', None)
    if not content_type:
      content_type = self.request.environ.get('HTTP_CONTENT_TYPE', None)
    if not content_type:
      return None

    # Lop off parameters from the end (for example content-encoding)
    return content_type.split(';', 1)[0].lower()

  def __headers(self, content_type):
    for name in self.request.headers:
      name = name.lower()
      if name == 'content-type':
        value = content_type
      elif name == 'content-length':
        value = str(len(self.request.body))
      else:
        value = self.request.headers.get(name, '')
      yield name, value

  def handle(self, http_method, service_path, remote_method):
    """Handle a service request.

    The handle method will handle either a GET or POST response.
    It is up to the individual mappers from the handler factory to determine
    which request methods they can service.

    If the protocol is not recognized, the request does not provide a correct
    request for that protocol or the service object does not support the
    requested RPC method, will return error code 400 in the response.

    Args:
      http_method: HTTP method of request.
      service_path: Service path derived from request URL.
      remote_method: Sub-path after service path has been matched.
    """
    self.response.headers['x-content-type-options'] = 'nosniff'
    if not remote_method and http_method == 'GET':
      # Special case a normal get request, presumably via a browser.
      self.error(405)
      self.__show_info(service_path, remote_method)
      return

    content_type = self.__get_content_type()

    # Provide server state to the service.  If the service object does not have
    # an "initialize_request_state" method, will not attempt to assign state.
    try:
      state_initializer = self.service.initialize_request_state
    except AttributeError:
      pass
    else:
      server_port = self.request.environ.get('SERVER_PORT', None)
      if server_port:
        server_port = int(server_port)

      request_state = remote.HttpRequestState(
          remote_host=self.request.environ.get('REMOTE_HOST', None),
          remote_address=self.request.environ.get('REMOTE_ADDR', None),
          server_host=self.request.environ.get('SERVER_HOST', None),
          server_port=server_port,
          http_method=http_method,
          service_path=service_path,
          headers=list(self.__headers(content_type)))
      state_initializer(request_state)

    if not content_type:
      self.__send_simple_error(400, 'Invalid RPC request: missing content-type')
      return

    # Search for mapper to mediate request.
    for mapper in self.__factory.all_request_mappers():
      if content_type in mapper.content_types:
        break
    else:
      if http_method == 'GET':
        self.error(httplib.UNSUPPORTED_MEDIA_TYPE)
        self.__show_info(service_path, remote_method)
      else:
        self.__send_simple_error(httplib.UNSUPPORTED_MEDIA_TYPE,
                                 'Unsupported content-type: %s' % content_type)
      return

    try:
      if http_method not in mapper.http_methods:
        if http_method == 'GET':
          self.error(httplib.METHOD_NOT_ALLOWED)
          self.__show_info(service_path, remote_method)
        else:
          self.__send_simple_error(httplib.METHOD_NOT_ALLOWED,
                                   'Unsupported HTTP method: %s' % http_method)
        return

      try:
        try:
          method = getattr(self.service, remote_method)
          method_info = method.remote
        except AttributeError, err:
          self.__send_error(
          400, remote.RpcState.METHOD_NOT_FOUND_ERROR,
            'Unrecognized RPC method: %s' % remote_method,
            mapper)
          return

        request = mapper.build_request(self, method_info.request_type)
      except (RequestError, messages.DecodeError), err:
        self.__send_error(400,
                          remote.RpcState.REQUEST_ERROR,
                          'Error parsing ProtoRPC request (%s)' % err,
                          mapper)
        return

      try:
        response = method(request)
      except remote.ApplicationError, err:
        self.__send_error(400,
                          remote.RpcState.APPLICATION_ERROR,
                          err.message,
                          mapper,
                          err.error_name)
        return

      mapper.build_response(self, response)
    except Exception, err:
      logging.error('An unexpected error occured when handling RPC: %s',
                    err, exc_info=1)

      self.__send_error(500,
                        remote.RpcState.SERVER_ERROR,
                        'Internal Server Error',
                        mapper)
      return


# TODO(rafek): Support tag-id only forms.
class URLEncodedRPCMapper(RPCMapper):
  """Request mapper for application/x-www-form-urlencoded forms.

  This mapper is useful for building forms that can invoke RPC.  Many services
  are also configured to work using URL encoded request information because
  of its perceived ease of programming and debugging.

  The mapper must be provided with at least method_parameter or
  remote_method_pattern so that it is possible to determine how to determine the
  requests RPC method.  If both are provided, the service will respond to both
  method request types, however, only one may be present in a given request.
  If both types are detected, the request will not match.
  """

  def __init__(self, parameter_prefix=''):
    """Constructor.

    Args:
      parameter_prefix: If provided, all the parameters in the form are
        expected to begin with that prefix.
    """
    # Private attributes:
    #   __parameter_prefix: parameter prefix as provided by constructor
    #     parameter.
    super(URLEncodedRPCMapper, self).__init__(['POST'],
                                              _URLENCODED_CONTENT_TYPE,
                                              self)
    self.__parameter_prefix = parameter_prefix

  def encode_message(self, message):
    """Encode a message using parameter prefix.

    Args:
      message: Message to URL Encode.

    Returns:
      URL encoded message.
    """
    return protourlencode.encode_message(message,
                                         prefix=self.__parameter_prefix)

  @property
  def parameter_prefix(self):
    """Prefix all form parameters are expected to begin with."""
    return self.__parameter_prefix

  def build_request(self, handler, request_type):
    """Build request from URL encoded HTTP request.

    Constructs message from names of URL encoded parameters.  If this service
    handler has a parameter prefix, parameters must begin with it or are
    ignored.

    Args:
      handler: RequestHandler instance that is servicing request.
      request_type: Message type to build.

    Returns:
      Instance of request_type populated by protocol buffer in request
        parameters.

    Raises:
      RequestError if message type contains nested message field or repeated
      message field.  Will raise RequestError if there are any repeated
      parameters.
    """
    request = request_type()
    builder = protourlencode.URLEncodedRequestBuilder(
        request, prefix=self.__parameter_prefix)
    for argument in sorted(handler.request.arguments()):
      values = handler.request.get_all(argument)
      try:
        builder.add_parameter(argument, values)
      except messages.DecodeError, err:
        raise RequestError(str(err))
    return request


class ProtobufRPCMapper(RPCMapper):
  """Request mapper for application/x-protobuf service requests.

  This mapper will parse protocol buffer from a POST body and return the request
  as a protocol buffer.
  """

  def __init__(self):
    super(ProtobufRPCMapper, self).__init__(['POST'],
                                            _PROTOBUF_CONTENT_TYPE,
                                            protobuf)


class JSONRPCMapper(RPCMapper):
  """Request mapper for application/x-protobuf service requests.

  This mapper will parse protocol buffer from a POST body and return the request
  as a protocol buffer.
  """

  def __init__(self):
    super(JSONRPCMapper, self).__init__(
        ['POST'],
        _JSON_CONTENT_TYPE,
        protojson,
        content_types=_EXTRA_JSON_CONTENT_TYPES)


def service_mapping(services,
                    registry_path=DEFAULT_REGISTRY_PATH):
  """Create a services mapping for use with webapp.

  Creates basic default configuration and registration for ProtoRPC services.
  Each service listed in the service mapping has a standard service handler
  factory created for it.

  The list of mappings can either be an explicit path to service mapping or
  just services.  If mappings are just services, they will automatically
  be mapped to their default name.  For exampel:

    package = 'my_package'

    class MyService(remote.Service):
      ...

    server_mapping([('/my_path', MyService),  # Maps to /my_path
                    MyService,                # Maps to /my_package/MyService
                   ])

  Specifying a service mapping:

    Normally services are mapped to URL paths by specifying a tuple
    (path, service):
      path: The path the service resides on.
      service: The service class or service factory for creating new instances
        of the service.  For more information about service factories, please
        see remote.Service.new_factory.

    If no tuple is provided, and therefore no path specified, a default path
    is calculated by using the fully qualified service name using a URL path
    separator for each of its components instead of a '.'.

  Args:
    services: Can be service type, service factory or string definition name of
        service being mapped or list of tuples (path, service):
      path: Path on server to map service to.
      service: Service type, service factory or string definition name of
        service being mapped.
      Can also be a dict.  If so, the keys are treated as the path and values as
      the service.
    registry_path: Path to give to registry service.  Use None to disable
      registry service.

  Returns:
    List of tuples defining a mapping of request handlers compatible with a
    webapp application.

  Raises:
    ServiceConfigurationError when duplicate paths are provided.
  """
  if isinstance(services, dict):
    services = services.iteritems()
  mapping = []
  registry_map = {}

  if registry_path is not None:
    registry_service = registry.RegistryService.new_factory(registry_map)
    services = list(services) + [(registry_path, registry_service)]
    mapping.append((registry_path + r'/form(?:/)?',
                    forms.FormsHandler.new_factory(registry_path)))
    mapping.append((registry_path + r'/form/(.+)', forms.ResourceHandler))

  paths = set()
  for service_item in services:
    infer_path = not isinstance(service_item, (list, tuple))
    if infer_path:
      service = service_item
    else:
      service = service_item[1]

    service_class = getattr(service, 'service_class', service)

    if infer_path:
      path = '/' + service_class.definition_name().replace('.', '/')
    else:
      path = service_item[0]

    if path in paths:
      raise ServiceConfigurationError(
        'Path %r is already defined in service mapping' % path.encode('utf-8'))
    else:
      paths.add(path)

    # Create service mapping for webapp.
    new_mapping = ServiceHandlerFactory.default(service).mapping(path)
    mapping.append(new_mapping)

    # Update registry with service class.
    registry_map[path] = service_class

  return mapping


def run_services(services,
                 registry_path=DEFAULT_REGISTRY_PATH):
  """Handle CGI request using service mapping.

  Args:
    Same as service_mapping.
  """
  mappings = service_mapping(services, registry_path=registry_path)
  application = webapp.WSGIApplication(mappings)
  webapp_util.run_wsgi_app(application)
