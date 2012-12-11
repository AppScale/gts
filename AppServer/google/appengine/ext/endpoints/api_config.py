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


"""Library for generating an API configuration document for a ProtoRPC backend.

The protorpc.remote.Service is inspected and a JSON document describing
the API is returned.

    class MyResponse(messages.Message):
      bool_value = messages.BooleanField(1)
      int32_value = messages.IntegerField(2)

    class MyService(remote.Service):

      @remote.method(message_types.VoidMessage, MyResponse)
      def entries_get(self, request):
        pass

    api = ApiConfigGenerator().pretty_print_config_to_json(MyService)
"""


import json
import re

from protorpc import message_types
from protorpc import messages
from protorpc import remote
from protorpc import util

from google.appengine.api import app_identity
from google.appengine.ext.endpoints import message_parser

__all__ = [
    'api',
    'ApiConfigGenerator',
    'CacheControl',
    'method',
]


class _ApiInfo(object):
  """Configurable attributes of an API.

  ApiInfo is a structured data object used by the @api decorator below to store
  configurable parameters for an API implementation (e.g. name, version)
  """

  @util.positional(3)
  def __init__(self, name, version, description=None, hostname=None):
    """Constructor for _ApiInfo.

    Args:
      name: string, Name of the API.
      version: string, Version of the API.
      description: string, Short description of the API (Default: None)
      hostname: string, Hostname of the API (Default: app engine default host)
    """
    self.__name = name
    self.__version = version
    self.__description = description
    self.__hostname = hostname

  @property
  def name(self):
    """Name of the API."""
    return self.__name

  @property
  def version(self):
    """Version of the API."""
    return self.__version

  @property
  def description(self):
    """Description of the API."""
    return self.__description

  @property
  def hostname(self):
    """Hostname for the API."""
    return self.__hostname




@util.positional(2)
def api(name, version, description=None, hostname=None):
  """Decorate a ProtoRPC Service class for use by the framework above.

  This decorator can be used to specify an API name, version, description, and
  hostname for your API.

  Sample usage (python 2.7):
    @api_config.api(name='guestbook', version='v0.2',
                    description='Guestbook API')
    class PostService(remote.Service):
      pass

  Sample usage (python 2.5):
    class PostService(remote.Service):
      pass
    api_config.api(PostService, name='guestbook', version='v0.2',
                   description='Guestbook API')(PostService)

  Args:
    name: string, Name of the API.
    version: string, Version of the API.
    description: string, Short description of the API (Default: None)
    hostname: string, Hostname of the API (Default: app engine default host)

  Returns:
    Class decorated with api_info attribute, an instance of ApiInfo.
  """

  def apiserving_api_decorator(api_class):
    """Decorator for ProtoRPC class that configures Google's API server.

    Args:
      api_class: remote.Service class, ProtoRPC service class being wrapped.

    Returns:
      Same class with attributes assigned corresponding name, version, kwargs.
    """
    api_class.api_info = _ApiInfo(
        name, version, description=description, hostname=hostname)
    return api_class

  if hostname is None:
    hostname = app_identity.get_default_version_hostname()
  return apiserving_api_decorator


class CacheControl(object):
  """Cache control settings for an API method.

  Setting is composed of a directive and maximum cache age.
  Available types:
    PUBLIC - Allows clients and proxies to cache responses.
    PRIVATE - Allows only clients to cache responses.
    NO_CACHE - Allows none to cache responses.
  """
  PUBLIC = 'public'
  PRIVATE = 'private'
  NO_CACHE = 'no-cache'
  VALID_VALUES = (PUBLIC, PRIVATE, NO_CACHE)

  def __init__(self, directive=NO_CACHE, max_age_seconds=0):
    """Constructor.

    Args:
      directive: string, Cache control directive, as above. (Default: NO_CACHE)
      max_age_seconds: int, Maximum age of cache responses. (Default: 0)
    """
    if directive not in self.VALID_VALUES:
      directive = self.NO_CACHE
    self.__directive = directive
    self.__max_age_seconds = max_age_seconds

  @property
  def directive(self):
    """The cache setting for this method, PUBLIC, PRIVATE, or NO_CACHE."""
    return self.__directive

  @property
  def max_age_seconds(self):
    """The maximum age of cache responses for this method, in seconds."""
    return self.__max_age_seconds


class _MethodInfo(object):
  """Configurable attributes of an API method.

  Consolidates settings from @method decorator and/or any settings that were
  calculating from the ProtoRPC method name, so they only need to be calculated
  once.
  """

  @util.positional(1)
  def __init__(self, name=None, path=None, http_method=None,
               cache_control=None, scopes=None, audiences=None,
               allowed_client_ids=None):
    """Constructor.

    Args:
      name: string, Name of the method, prepended with <apiname>. to make it
        unique.
      path: string, Path portion of the URL to the method, for RESTful methods.
      http_method: string, HTTP method supported by the method.
      cache_control: CacheControl, Cache settings for the API method.
      scopes: list of string, OAuth2 token must contain one of these scopes.
      audiences: list of string, IdToken must contain one of these audiences.
      allowed_client_ids: list of string, Client IDs allowed to call the method.
    """
    self.__name = name
    self.__path = path
    self.__http_method = http_method
    self.__cache_control = cache_control
    self.__scopes = scopes
    self.__audiences = audiences
    self.__allowed_client_ids = allowed_client_ids

  def __safe_name(self, method_name):
    """Restrict method name to a-zA-Z0-9, first char lowercase."""


    safe_name = re.sub('[^\.a-zA-Z0-9]', '', method_name)
    return safe_name[0:1].lower() + safe_name[1:]

  @property
  def name(self):
    """Method name as specified in decorator or derived."""
    return self.__name

  @property
  def path(self):
    """Path portion of the URL to the method (for RESTful methods)."""
    return self.__path

  @property
  def http_method(self):
    """HTTP method supported by the method (e.g. GET, POST)."""
    return self.__http_method

  @property
  def cache_control(self):
    """Cache control setting for the API method."""
    return self.__cache_control

  @property
  def scopes(self):
    """List of scopes for the API method."""
    return self.__scopes

  @property
  def audiences(self):
    """List of audiences for the API method."""
    return self.__audiences

  @property
  def allowed_client_ids(self):
    """List of allowed client IDs for the API method."""
    return self.__allowed_client_ids

  def method_id(self, api_name):
    """Computed method name."""



    return '%s.%s' % (self.__safe_name(api_name),
                      self.__safe_name(self.name))


@util.positional(2)
def method(request_message=message_types.VoidMessage,
           response_message=message_types.VoidMessage,
           name=None,
           path=None,
           http_method='POST',
           cache_control=None,
           scopes=None,
           audiences=None,
           allowed_client_ids=None):
  """Decorate a ProtoRPC Method for use by the framework above.

  This decorator can be used to specify a method name, path, http method,
  cache control, scopes, audiences, and client ids

  Sample usage:
    @api_config.method(RequestMessage, ResponseMessage,
                       name='insert', http_method='PUT')
    def greeting_insert(request):
      ...
      return response

  Args:
    request_message: Message type of expected request.
    response_message: Message type of expected response.
    name: string, Name of the method, prepended with <apiname>. to make it
      unique. (Default: python method name)
    path: string, Path portion of the URL to the method, for RESTful methods.
    http_method: string, HTTP method supported by the method. (Default: POST)
    cache_control: CacheControl, Cache settings for the API method.
    scopes: list of string, OAuth2 token must contain one of these scopes.
    audiences: list of string, IdToken must contain one of these audiences.
    allowed_client_ids: list of string, Client IDs allowed to call the method.
      Currently limited to 5.  If None, no calls will be allowed.

  Returns:
    'apiserving_method_wrapper' function.

  Raises:
    ValueError: if more than 5 allowed_client_ids are specified.
    TypeError: if the request_type or response_type parameters are not
      proper subclasses of messages.Message.
  """


  DEFAULT_HTTP_METHOD = 'POST'

  def check_type(setting, allowed_type, name, allow_none=True):
    """Verify that the setting is of the allowed type or raise TypeError.

    Args:
      setting: The setting to check.
      allowed_type: The allowed type.
      name: Name of the setting, added to the exception.
      allow_none: If set, None is also allowed.

    Raises:
      TypeError: if setting is not of the allowed type.

    Returns:
      The setting, for convenient use in assignment.
    """
    if (setting is None and allow_none or
        isinstance(setting, allowed_type)):
      return setting
    raise TypeError('%s is not of type %s' % (name, allowed_type.__name__))

  def check_list_type(settings, allowed_type, name, allow_none=True):
    """Verify that settings in list are of the allowed type or raise TypeError.

    Args:
      settings: The list of settings to check.
      allowed_type: The allowed type of items in 'settings'.
      name: Name of the setting, added to the exception.
      allow_none: If set, None is also allowed.

    Raises:
      TypeError: if setting is not of the allowed type.

    Returns:
      The list of settings, for convenient use in assignment.
    """
    if (settings is None and allow_none or
        isinstance(settings, list) and
        all(isinstance(i, allowed_type) for i in settings)):
      return settings
    raise TypeError('%s is not a list of %s' % (name, allowed_type.__name__))

  def apiserving_method_decorator(api_method):
    """Decorator for ProtoRPC method that configures Google's API server.

    Args:
      api_method: Original method being wrapped.

    Returns:
      'remote.invoke_remote_method' function responsible for actual invocation.
      Assigns the following attributes to invocation function:
        remote: Instance of RemoteInfo, contains remote method information.
        remote.request_type: Expected request type for remote method.
        remote.response_type: Response type returned from remote method.
        method_info: Instance of _MethodInfo, api method configuration.
      It is also assigned attributes corresponding to the aforementioned kwargs.

    Raises:
      TypeError: if the request_type or response_type parameters are not
        proper subclasses of messages.Message.
    """
    remote_decorator = remote.method(request_message, response_message)
    remote_method = remote_decorator(api_method)
    remote_method.method_info = _MethodInfo(
        name=name or api_method.__name__, path=path or '',
        http_method=http_method or DEFAULT_HTTP_METHOD,
        cache_control=cache_control, scopes=scopes, audiences=audiences,
        allowed_client_ids=allowed_client_ids)
    return remote_method

  check_type(cache_control, CacheControl, 'cache_control')
  check_list_type(scopes, basestring, 'scopes')
  check_list_type(audiences, basestring, 'audiences')
  check_list_type(allowed_client_ids, basestring, 'allowed_client_ids')
  if allowed_client_ids is not None and len(allowed_client_ids) > 5:
    raise ValueError('allowed_client_ids must have 5 or fewer entries.')
  return apiserving_method_decorator


class ApiConfigGenerator(object):
  """Generates an API configuration from a ProtoRPC service.

  Example:

    class HelloRequest(messages.Message):
      my_name = messages.StringField(1, required=True)

    class HelloResponse(messages.Message):
      hello = messages.StringField(1, required=True)

    class HelloService(remote.Service):

      @remote.method(HelloRequest, HelloResponse)
      def hello(self, request):
        return HelloResponse(hello='Hello there, %s!' %
                             request.my_name)

    api_config = ApiConfigGenerator().pretty_print_config_to_json(HelloService)

  The resulting api_config will be a JSON document describing the API
  implemented by HelloService.
  """




  __NO_BODY = 1
  __BODY_ONLY = 2


  __FIELD_TO_PARAM_TYPE_MAP = {
      messages.IntegerField: 'int64',
      messages.FloatField: 'double',
      messages.BooleanField: 'boolean',
      messages.BytesField: 'string',
      messages.StringField: 'string',
      messages.MessageField: 'object',
      messages.EnumField: 'string',
  }

  __DEFAULT_PARAM_TYPE = 'string'

  def __init__(self):
    self.__parser = message_parser.MessageTypeToJsonSchema()


    self.__request_schema = {}


    self.__response_schema = {}


    self.__id_from_name = {}

  def __get_request_kind(self, method_info):
    """Categorize the type of the request.

    Args:
      method_info: _MethodInfo, method information.

    Returns:
      The kind of request.
    """
    if method_info.http_method in ['GET', 'DELETE']:
      return self.__NO_BODY
    else:
      return self.__BODY_ONLY

  def __params_descriptor(self, message_type):
    """Describe the parameters of a method.

    Args:
      message_type: messages.Message class, Message with parameters to describe.

    Returns:
      A tuple (dict, list of string): Descriptor of the parameters, Order of the
        parameters
    """
    params = {}
    param_order = []

    for field in sorted(message_type.all_fields(), key=lambda f: f.number):
      if field.required:
        param_order.append(field.name)


      descriptor = {}
      descriptor['source'] = field.required and 'path' or 'query'
      param_type = self.__FIELD_TO_PARAM_TYPE_MAP.get(
          type(field), self.__DEFAULT_PARAM_TYPE)
      descriptor['type'] = param_type

      if field.default:
        if type(field) == messages.EnumField:
          descriptor['default'] = str(field.default)
        else:
          descriptor['default'] = field.default

      params[field.name] = descriptor

    return params, param_order

  def __request_message_descriptor(self, request_kind, message_type, method_id):
    """Describes the parameters and body of the request.

    Args:
      request_kind: The type of request being made.
      message_type: messages.Message class, The message to describe.
      method_id: string, Unique method identifier (e.g. 'myapi.items.method')

    Returns:
      Dictionary describing the request.
    """
    descriptor = {}

    params, param_order = self.__params_descriptor(message_type)

    if (request_kind == self.__NO_BODY or
        message_type == message_types.VoidMessage()):
      descriptor['body'] = 'empty'
    else:
      descriptor['body'] = 'autoTemplate(backendRequest)'
      descriptor['bodyName'] = 'resource'
      self.__request_schema[method_id] = self.__parser.add_message(
          message_type.__class__)

      params = dict((k, v) for k, v in params.iteritems()
                    if v.get('source', None) == 'path')

    if params:
      descriptor['parameters'] = params
      descriptor['parameterOrder'] = param_order

    return descriptor

  def __response_message_descriptor(self, message_type, method_id):
    """Describes the response.

    Args:
      message_type: messages.Message class, The message to describe.
      method_id: string, Unique method identifier (e.g. 'myapi.items.method')

    Returns:
      Dictionary describing the response.
    """
    descriptor = {}

    self.__parser.add_message(message_type.__class__)
    if message_type == message_types.VoidMessage():
      descriptor['body'] = 'empty'
    else:
      descriptor['body'] = 'autoTemplate(backendResponse)'
      descriptor['bodyName'] = 'resource'
      self.__response_schema[method_id] = self.__parser.ref_for_message_type(
          message_type.__class__)

    return descriptor

  def __method_descriptor(self, service_name, api_name, method_info,
                          protorpc_method_name, protorpc_method_info):
    """Describes a method.

    Args:
      service_name: string, Name of the service.
      api_name: string, Name of the API.
      method_info: _MethodInfo, Configuration for the method.
      protorpc_method_name: string, Name of the method as given in the
        ProtoRPC implementation.
      protorpc_method_info: protorpc.remote._RemoteMethodInfo, ProtoRPC
        description of the method.

    Returns:
      Dictionary describing the method.
    """
    descriptor = {}

    request_message_type = protorpc_method_info.remote.request_type()
    request_kind = self.__get_request_kind(method_info)
    remote_method = protorpc_method_info.remote

    descriptor['path'] = method_info.path if method_info.path else ''
    descriptor['httpMethod'] = method_info.http_method
    descriptor['rosyMethod'] = '%s.%s' % (service_name, protorpc_method_name)
    descriptor['request'] = self.__request_message_descriptor(
        request_kind, request_message_type, method_info.method_id(api_name))
    descriptor['response'] = self.__response_message_descriptor(
        remote_method.response_type(), method_info.method_id(api_name))

    if remote_method.method.__doc__:
      descriptor['description'] = remote_method.method.__doc__

    return descriptor

  def __schema_descriptor(self, service_name, protorpc_methods):
    """Descriptor for the all the JSON Schema used.

    Args:
      service_name: string, Name of the service.
      protorpc_methods: dict, Map of protorpc_method_name to
        protorpc.remote._RemoteMethodInfo.

    Returns:
      Dictionary containing all the JSON Schema used in the service.
    """
    methods_desc = {}

    for protorpc_method_name in protorpc_methods.iterkeys():
      method_id = self.__id_from_name[protorpc_method_name]

      request_response = {}

      request_schema_id = self.__request_schema.get(method_id)
      if request_schema_id:
        request_response['request'] = {
            '$ref': request_schema_id
            }

      response_schema_id = self.__response_schema.get(method_id)
      if response_schema_id:
        request_response['response'] = {
            '$ref': response_schema_id
            }

      rosy_method = '%s.%s' % (service_name, protorpc_method_name)
      methods_desc[rosy_method] = request_response

    descriptor = {
        'methods': methods_desc,
        'schemas': self.__parser.schemas(),
        }

    return descriptor

  def __api_descriptor(self, service):
    """Builds a description of an API.

    Args:
      service: protorpc.remote.Service, Implementation of the API as a service.

    Returns:
      A dictionary that can be deserialized into JSON and stored as an API
      description document.
    """

    descriptor = {
        'extends': 'thirdParty.api',
        'root': 'https://%s/_ah/api' % service.api_info.hostname,
        'name': service.api_info.name,
        'version': service.api_info.version,
        'defaultVersion': True,
        'abstract': False,
        'adapter': {
            'bns': 'http://%s/_ah/spi' % service.api_info.hostname
            }
        }

    description = service.api_info.description or service.__doc__
    if description:
      descriptor['description'] = description

    method_map = {}

    protorpc_methods = service.all_remote_methods()
    for protorpc_meth_name, protorpc_meth_info in protorpc_methods.iteritems():
      method_info = getattr(protorpc_meth_info, 'method_info', None)

      if method_info is None:
        continue
      method_id = method_info.method_id(service.api_info.name)
      self.__id_from_name[protorpc_meth_name] = method_id
      method_map[method_id] = self.__method_descriptor(
          service.__name__, service.api_info.name, method_info,
          protorpc_meth_name, protorpc_meth_info)

    if method_map:
      descriptor['methods'] = method_map
      descriptor['descriptor'] = self.__schema_descriptor(
          service.__name__, protorpc_methods)

    return descriptor

  def pretty_print_config_to_json(self, service):
    """Description of a protorpc.remote.Service in API format.

    Args:
      service: protorpc.remote.Service, Implementation of the API as a service.

    Returns:
      string, The API descriptor document as JSON.
    """
    descriptor = self.__api_descriptor(service)
    return json.dumps(descriptor, sort_keys=True, indent=2)
