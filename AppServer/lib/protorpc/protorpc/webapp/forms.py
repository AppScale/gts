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

"""Webapp forms interface to ProtoRPC services.

This webapp application is automatically configured to work with ProtoRPCs
that have a configured protorpc.RegistryService.  This webapp is
automatically added to the registry service URL at <registry-path>/forms
(default is /protorpc/form) when configured using the
service_handlers.service_mapping function.
"""

import logging
import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

__all__ = ['FormsHandler',
           'ResourceHandler',

           'DEFAULT_REGISTRY_PATH',
          ]

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              'static')

_FORMS_TEMPLATE = os.path.join(_TEMPLATES_DIR, 'forms.html')
_METHODS_TEMPLATE = os.path.join(_TEMPLATES_DIR, 'methods.html')

DEFAULT_REGISTRY_PATH = '/protorpc'


class ResourceHandler(webapp.RequestHandler):
  """Serves static resources without needing to add static files to app.yaml."""

  __RESOURCE_MAP = {
    'forms.js': 'text/javascript',
    'jquery-1.4.2.min.js': 'text/javascript',
    'jquery.json-2.2.min.js': 'text/javascript',
  }

  def get(self, relative):
    """Serve known static files.

    If static file is not known, will return 404 to client.

    Response items are cached for 300 seconds.

    Args:
      relative: Name of static file relative to main FormsHandler.
    """
    content_type = self.__RESOURCE_MAP.get(relative, None)
    if not content_type:
      self.response.set_status(404)
      self.response.out.write('Resource not found.')
      return

    path = os.path.join(_TEMPLATES_DIR, relative)
    self.response.headers['Content-Type'] = content_type
    static_file = open(path)
    try:
      contents = static_file.read()
    finally:
      static_file.close()
    self.response.out.write(contents)


class FormsHandler(webapp.RequestHandler):
  """Handler for display HTML/javascript forms of ProtoRPC method calls.

  When accessed with no query parameters, will show a web page that displays
  all services and methods on the associated registry path.  Links on this
  page fill in the service_path and method_name query parameters back to this
  same handler.

  When provided with service_path and method_name parameters will display a
  dynamic form representing the request message for that method.  When sent,
  the form sends a JSON request to the ProtoRPC method and displays the
  response in the HTML page.

  Attribute:
    registry_path: Read-only registry path known by this handler.
  """

  def __init__(self, registry_path=DEFAULT_REGISTRY_PATH):
    """Constructor.

    When configuring a FormsHandler to use with a webapp application do not
    pass the request handler class in directly.  Instead use new_factory to
    ensure that the FormsHandler is created with the correct registry path
    for each request.

    Args:
      registry_path: Absolute path on server where the ProtoRPC RegsitryService
        is located.
    """
    assert registry_path
    self.__registry_path = registry_path

  @property
  def registry_path(self):
    return self.__registry_path

  def get(self):
    """Send forms and method page to user.

    By default, displays a web page listing all services and methods registered
    on the server.  Methods have links to display the actual method form.

    If both parameters are set, will display form for method.

    Query Parameters:
      service_path: Path to service to display method of.  Optional.
      method_name: Name of method to display form for.  Optional.
    """
    params = {'forms_path': self.request.path.rstrip('/'),
              'hostname': self.request.host,
              'registry_path': self.__registry_path,
    }
    service_path = self.request.get('path', None)
    method_name = self.request.get('method', None)

    if service_path and method_name:
      form_template = _METHODS_TEMPLATE
      params['service_path'] = service_path
      params['method_name'] = method_name
    else:
      form_template = _FORMS_TEMPLATE

    self.response.out.write(template.render(form_template, params))

  @classmethod
  def new_factory(cls, registry_path=DEFAULT_REGISTRY_PATH):
    """Construct a factory for use with WSGIApplication.

    This method is called automatically with the correct registry path when
    services are configured via service_handlers.service_mapping.

    Args:
      registry_path: Absolute path on server where the ProtoRPC RegsitryService
        is located.

    Returns:
      Factory function that creates a properly configured FormsHandler instance.
    """
    def forms_factory():
      return cls(registry_path)
    return forms_factory
