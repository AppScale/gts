# -*- coding: utf-8 -*-
"""
    webapp2_extras.protorpc
    =======================

    Support for Google ProtoRPC library in webapp2.

    Ported from protorpc.service_handlers.

    See: http://code.google.com/p/google-protorpc/

    .. warning::
       This is an experimental package, as the ProtoRPC API is not stable yet.

    :copyright: 2010 Google Inc.
    :copyright: 2011 tipfy.org.
    :license: Apache Sotware License, see LICENSE for details.
"""
from __future__ import absolute_import

import logging

from protorpc import registry
from protorpc.webapp import service_handlers
from protorpc.webapp import forms

import webapp2


class ServiceHandler(webapp2.RequestHandler, service_handlers.ServiceHandler):
    def dispatch(self, factory, service):
        # Unfortunately we need to access the protected attributes.
        self._ServiceHandler__factory = factory
        self._ServiceHandler__service = service

        request = self.request
        request_method = request.method
        method = getattr(self, request_method.lower(), None)
        service_path, remote_method = request.route_args
        if method:
            self.handle(request_method, service_path, remote_method)
        else:
            message = 'Unsupported HTTP method: %s' % request_method
            logging.error(message)
            self.response.status = '405 %s' % message

        if request_method == 'GET':
            status = self.response.status_int
            if status in (405, 415) or not request.content_type:
                # Again, now a protected method.
                self._ServiceHandler__show_info(service_path, remote_method)


class ServiceHandlerFactory(service_handlers.ServiceHandlerFactory):
    def __call__(self, request, *args, **kwargs):
        """Construct a new service handler instance."""
        handler = ServiceHandler(request, request.response)
        handler.dispatch(self, self.service_factory())


def _normalize_services(mixed_services):
    if isinstance(mixed_services, dict):
        mixed_services = mixed_services.iteritems()

    services = []
    for service_item in mixed_services:
        if isinstance(service_item, (list, tuple)):
            path, service = service_item
        else:
            path = None
            service = service_item

        if isinstance(service, basestring):
            # Lazily import the service class.
            service = webapp2.import_string(service)

        services.append((path, service))

    return services


def service_mapping(services, registry_path=forms.DEFAULT_REGISTRY_PATH):
    """Create a services mapping for use with webapp2.

    Creates basic default configuration and registration for ProtoRPC services.
    Each service listed in the service mapping has a standard service handler
    factory created for it.

    The list of mappings can either be an explicit path to service mapping or
    just services.  If mappings are just services, they will automatically
    be mapped to their default name.  For example::

        from protorpc import messages
        from protorpc import remote

        import webapp2
        from webapp2_extras import protorpc

        class HelloRequest(messages.Message):
            my_name = messages.StringField(1, required=True)

        class HelloResponse(messages.Message):
            hello = messages.StringField(1, required=True)

        class HelloService(remote.Service):
            @remote.method(HelloRequest, HelloResponse)
            def hello(self, request):
                return HelloResponse(hello='Hello there, %s!' %
                                     request.my_name)

        service_mappings = protorpc.service_mapping([
            ('/hello', HelloService),
        ])

        app = webapp2.WSGIApplication(routes=service_mappings)

        def main():
            app.run()

        if __name__ == '__main__':
            main()

    Specifying a service mapping:

    Normally services are mapped to URL paths by specifying a tuple
    (path, service):

    - path: The path the service resides on.
    - service: The service class or service factory for creating new instances
      of the service.  For more information about service factories, please
      see remote.Service.new_factory.

    If no tuple is provided, and therefore no path specified, a default path
    is calculated by using the fully qualified service name using a URL path
    separator for each of its components instead of a '.'.

    :param services:
        Can be service type, service factory or string definition name of
        service being mapped or list of tuples (path, service):

        - path: Path on server to map service to.
        - service: Service type, service factory or string definition name of
          service being mapped.

      Can also be a dict.  If so, the keys are treated as the path and values
      as the service.
    :param registry_path:
        Path to give to registry service. Use None to disable registry service.
    :returns:
        List of tuples defining a mapping of request handlers compatible with a
        webapp2 application.
    :raises:
        ServiceConfigurationError when duplicate paths are provided.
    """
    # TODO: clean the convoluted API? Accept services as tuples only, or
    # make different functions to accept different things.
    # For now we are just following the same API from protorpc.
    services = _normalize_services(services)
    mapping = []
    registry_map = {}

    if registry_path is not None:
        registry_service = registry.RegistryService.new_factory(registry_map)
        services = list(services) + [(registry_path, registry_service)]
        forms_handler = forms.FormsHandler(registry_path=registry_path)
        mapping.append((registry_path + r'/form(?:/)?', forms_handler))
        mapping.append((registry_path + r'/form/(.+)', forms.ResourceHandler))

    paths = set()
    for path, service in services:
        service_class = getattr(service, 'service_class', service)
        if not path:
            path = '/' + service_class.definition_name().replace('.', '/')

        if path in paths:
            raise service_handlers.ServiceConfigurationError(
                'Path %r is already defined in service mapping'
                % path.encode('utf-8'))
        else:
            paths.add(path)

        # Create service mapping for webapp2.
        new_mapping = ServiceHandlerFactory.default(service).mapping(path)
        mapping.append(new_mapping)

        # Update registry with service class.
        registry_map[path] = service_class

    return mapping


def get_app(services, registry_path=forms.DEFAULT_REGISTRY_PATH,
            debug=False, config=None):
    """Returns a WSGI application configured for the given services.

    Parameters are the same as :func:`service_mapping`, plus:

    :param debug:
        WSGI application debug flag: True to enable debug mode.
    :param config:
        WSGI application configuration dictionary.
    """
    mappings = service_mapping(services, registry_path=registry_path)
    return webapp2.WSGIApplication(routes=mappings, debug=debug, config=config)


def run_services(services, registry_path=forms.DEFAULT_REGISTRY_PATH,
                 debug=False, config=None):
    """Handle CGI request using service mapping.

    Parameters are the same as :func:`get_app`.
    """
    app = get_app(services, registry_path=registry_path, debug=debug,
                  config=config)
    app.run()
