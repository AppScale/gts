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


"""Api serving config collection service implementation.

Contains the implementation for BackendService as defined in api_backend.py.
"""


import json

from google.appengine.ext.endpoints import api_backend


__all__ = [
    'ApiConfigRegistry',
    'BackendServiceImpl',
]


class ApiConfigRegistry(object):
  """Registry of active APIs to be registered with Google API Server."""

  def __init__(self):

    self.__api_roots = set()

    self.__api_configs = []

    self.__api_methods = {

        'BackendService.getApiConfigs': 'BackendService.getApiConfigs'
    }



  def register_api(self, api_root_url, config_contents):
    """Register a single API given its config contents.

    Args:
      api_root_url: URL that uniquely identifies this APIs root.
      config_contents: String containing API configuration.
    """
    if api_root_url in self.__api_roots:
      return
    self.__api_roots.add(api_root_url)
    self.__api_configs.append(config_contents)
    self.__register_methods(config_contents)

  def __register_methods(self, config_file):
    """Register all methods from the given api config file.

    Methods are stored in a map from method_name to rosyMethod,
    the name of the ProtoRPC method to be called on the backend.
    If no rosyMethod was specified the value will be None.

    Args:
      config_file: json string containing api config.
    """
    try:
      parsed_config = json.loads(config_file)
    except (TypeError, ValueError):
      return None
    methods = parsed_config.get('methods')
    if not methods:
      return None
    for method_name, method in methods.iteritems():
      self.__api_methods[method_name] = method.get('rosyMethod')

  def lookup_api_method(self, api_method_name):
    """Looks an API method up by name to find the backend method to call.

    Args:
      api_method_name: Name of the method in the API that was called.

    Returns:
      Name of the ProtoRPC method called on the backend, or None if not found.
    """
    return self.__api_methods.get(api_method_name)

  def all_api_configs(self):
    """Return a list of all API configration specs as registered above."""
    return self.__api_configs


class BackendServiceImpl(api_backend.BackendService):
  """Implementation of BackendService."""

  def __init__(self, api_config_registry):
    """Create a new BackendService implementation.

    Args:
      api_config_registry: ApiConfigRegistry to register and look up configs.
    """
    self.__api_config_registry = api_config_registry




  @staticmethod
  def definition_name():
    """Override definition_name so that it is not BackendServiceImpl."""
    return api_backend.BackendService.definition_name()

  def getApiConfigs(self, unused_request):
    """Return a list of active APIs and their configuration files.

    Args:
      unused_request: Empty request message, unused

    Returns:
      List of ApiConfigMessages
    """
    configs = self.__api_config_registry.all_api_configs()
    return api_backend.ApiConfigList(items=configs)
