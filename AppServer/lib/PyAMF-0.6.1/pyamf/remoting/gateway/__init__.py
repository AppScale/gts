# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Remoting server implementations.

@since: 0.1.0
"""

import sys
import types
import datetime

import pyamf
from pyamf import remoting, util, python

try:
    from platform import python_implementation
    impl = python_implementation()
except ImportError:
    impl = 'Python'

SERVER_NAME = 'PyAMF/%s %s/%s' % (
    pyamf.version, impl,
    '.'.join(map(lambda x: str(x), sys.version_info[0:3]))
)


class BaseServiceError(pyamf.BaseError):
    """
    Base service error.
    """


class UnknownServiceError(BaseServiceError):
    """
    Client made a request for an unknown service.
    """
    _amf_code = 'Service.ResourceNotFound'


class UnknownServiceMethodError(BaseServiceError):
    """
    Client made a request for an unknown method.
    """
    _amf_code = 'Service.MethodNotFound'


class InvalidServiceMethodError(BaseServiceError):
    """
    Client made a request for an invalid methodname.
    """
    _amf_code = 'Service.MethodInvalid'


class ServiceWrapper(object):
    """
    Wraps a supplied service with extra functionality.

    @ivar service: The original service.
    @type service: C{callable}
    @ivar description: A description of the service.
    @type description: C{str}
    """
    def __init__(self, service, description=None, authenticator=None,
        expose_request=None, preprocessor=None):
        self.service = service
        self.description = description
        self.authenticator = authenticator
        self.expose_request = expose_request
        self.preprocessor = preprocessor

    def __cmp__(self, other):
        if isinstance(other, ServiceWrapper):
            return cmp(self.__dict__, other.__dict__)

        return cmp(self.service, other)

    def _get_service_func(self, method, params):
        """
        @raise InvalidServiceMethodError: Calls to private methods are not
            allowed.
        @raise UnknownServiceMethodError: Unknown method.
        @raise InvalidServiceMethodError: Service method must be callable.
        """
        service = None

        if isinstance(self.service, (type, types.ClassType)):
            service = self.service()
        else:
            service = self.service

        if method is not None:
            method = str(method)

            if method.startswith('_'):
                raise InvalidServiceMethodError(
                    "Calls to private methods are not allowed")

            try:
                func = getattr(service, method)
            except AttributeError:
                raise UnknownServiceMethodError(
                    "Unknown method %s" % str(method))

            if not python.callable(func):
                raise InvalidServiceMethodError(
                    "Service method %s must be callable" % str(method))

            return func

        if not python.callable(service):
            raise UnknownServiceMethodError(
                "Unknown method %s" % str(self.service))

        return service

    def __call__(self, method, params):
        """
        Executes the service.

        If the service is a class, it will be instantiated.

        @param method: The method to call on the service.
        @type method: C{None} or C{mixed}
        @param params: The params to pass to the service.
        @type params: C{list} or C{tuple}
        @return: The result of the execution.
        @rtype: C{mixed}
        """
        func = self._get_service_func(method, params)

        return func(*params)

    def getMethods(self):
        """
        Gets a C{dict} of valid method callables for the underlying service
        object.
        """
        callables = {}

        for name in dir(self.service):
            method = getattr(self.service, name)

            if name.startswith('_') or not python.callable(method):
                continue

            callables[name] = method

        return callables

    def getAuthenticator(self, service_request=None):
        if service_request is None:
            return self.authenticator

        methods = self.getMethods()

        if service_request.method is None:
            if hasattr(self.service, '_pyamf_authenticator'):
                return self.service._pyamf_authenticator

        if service_request.method not in methods:
            return self.authenticator

        method = methods[service_request.method]

        if hasattr(method, '_pyamf_authenticator'):
            return method._pyamf_authenticator

        return self.authenticator

    def mustExposeRequest(self, service_request=None):
        if service_request is None:
            return self.expose_request

        methods = self.getMethods()

        if service_request.method is None:
            if hasattr(self.service, '_pyamf_expose_request'):
                return self.service._pyamf_expose_request

            return self.expose_request

        if service_request.method not in methods:
            return self.expose_request

        method = methods[service_request.method]

        if hasattr(method, '_pyamf_expose_request'):
            return method._pyamf_expose_request

        return self.expose_request

    def getPreprocessor(self, service_request=None):
        if service_request is None:
            return self.preprocessor

        methods = self.getMethods()

        if service_request.method is None:
            if hasattr(self.service, '_pyamf_preprocessor'):
                return self.service._pyamf_preprocessor

        if service_request.method not in methods:
            return self.preprocessor

        method = methods[service_request.method]

        if hasattr(method, '_pyamf_preprocessor'):
            return method._pyamf_preprocessor

        return self.preprocessor


class ServiceRequest(object):
    """
    Remoting service request.

    @ivar request: The request to service.
    @type request: L{Envelope<pyamf.remoting.Envelope>}
    @ivar service: Facilitates the request.
    @type service: L{ServiceWrapper}
    @ivar method: The method to call on the service. A value of C{None}
        means that the service will be called directly.
    @type method: C{None} or C{str}
    """
    def __init__(self, amf_request, service, method):
        self.request = amf_request
        self.service = service
        self.method = method

    def __call__(self, *args):
        return self.service(self.method, args)


class ServiceCollection(dict):
    """
    I hold a collection of services, mapping names to objects.
    """
    def __contains__(self, value):
        if isinstance(value, basestring):
            return value in self.keys()

        return value in self.values()


class BaseGateway(object):
    """
    Generic Remoting gateway.

    @ivar services: A map of service names to callables.
    @type services: L{ServiceCollection}
    @ivar authenticator: A callable that will check the credentials of
        the request before allowing access to the service. Will return a
        C{bool} value.
    @type authenticator: C{Callable} or C{None}
    @ivar preprocessor: Called before the actual service method is invoked.
        Useful for setting up sessions etc.
    @type preprocessor: C{Callable} or C{None}
    @ivar logger: A logging instance.
    @ivar strict: Defines whether the gateway should use strict en/decoding.
    @type strict: C{bool}
    @ivar timezone_offset: A U{datetime.datetime.timedelta<http://
        docs.python.org/library/datetime.html#datetime.timedelta} between UTC
        and the timezone to be encoded. Most dates should be handled as UTC to
        avoid confusion but for older legacy systems this is not an option.
        Supplying an int as this will be interpretted in seconds.
    @ivar debug: Provides debugging information when an error occurs. Use only
        in non production settings.
    @type debug: C{bool}
    """

    _request_class = ServiceRequest

    def __init__(self, services=None, **kwargs):
        if services is None:
            services = {}

        if not hasattr(services, 'iteritems'):
            raise TypeError("dict type required for services")

        self.services = ServiceCollection()
        self.authenticator = kwargs.pop('authenticator', None)
        self.preprocessor = kwargs.pop('preprocessor', None)
        self.expose_request = kwargs.pop('expose_request', False)
        self.strict = kwargs.pop('strict', False)
        self.logger = kwargs.pop('logger', None)
        self.timezone_offset = kwargs.pop('timezone_offset', None)

        self.debug = kwargs.pop('debug', False)

        if kwargs:
            raise TypeError('Unknown kwargs: %r' % (kwargs,))

        for name, service in services.iteritems():
            self.addService(service, name)

    def addService(self, service, name=None, description=None,
        authenticator=None, expose_request=None, preprocessor=None):
        """
        Adds a service to the gateway.

        @param service: The service to add to the gateway.
        @type service: C{callable}, class instance, or a module
        @param name: The name of the service.
        @type name: C{str}
        @raise pyamf.remoting.RemotingError: Service already exists.
        @raise TypeError: C{service} cannot be a scalar value.
        @raise TypeError: C{service} must be C{callable} or a module.
        """
        if isinstance(service, (int, long, float, basestring)):
            raise TypeError("Service cannot be a scalar value")

        allowed_types = (types.ModuleType, types.FunctionType, types.DictType,
            types.MethodType, types.InstanceType, types.ObjectType)

        if not python.callable(service) and not isinstance(service, allowed_types):
            raise TypeError("Service must be a callable, module, or an object")

        if name is None:
            # TODO: include the module in the name
            if isinstance(service, (type, types.ClassType)):
                name = service.__name__
            elif isinstance(service, types.FunctionType):
                name = service.func_name
            elif isinstance(service, types.ModuleType):
                name = service.__name__
            else:
                name = str(service)

        if name in self.services:
            raise remoting.RemotingError("Service %s already exists" % name)

        self.services[name] = ServiceWrapper(service, description,
            authenticator, expose_request, preprocessor)

    def _get_timezone_offset(self):
        if self.timezone_offset is None:
            return None

        if isinstance(self.timezone_offset, datetime.timedelta):
            return self.timezone_offset

        return datetime.timedelta(seconds=self.timezone_offset)

    def removeService(self, service):
        """
        Removes a service from the gateway.

        @param service: Either the name or t of the service to remove from the
                        gateway, or .
        @type service: C{callable} or a class instance
        @raise NameError: Service not found.
        """
        for name, wrapper in self.services.iteritems():
            if service in (name, wrapper.service):
                del self.services[name]
                return

        raise NameError("Service %r not found" % (service,))

    def getServiceRequest(self, request, target):
        """
        Returns a service based on the message.

        @raise UnknownServiceError: Unknown service.
        @param request: The AMF request.
        @type request: L{Request<pyamf.remoting.Request>}
        @rtype: L{ServiceRequest}
        """
        try:
            return self._request_class(
                request.envelope, self.services[target], None)
        except KeyError:
            pass

        try:
            sp = target.split('.')
            name, meth = '.'.join(sp[:-1]), sp[-1]

            return self._request_class(
                request.envelope, self.services[name], meth)
        except (ValueError, KeyError):
            pass

        raise UnknownServiceError("Unknown service %s" % target)

    def getProcessor(self, request):
        """
        Returns request processor.

        @param request: The AMF message.
        @type request: L{Request<remoting.Request>}
        """
        if request.target == 'null' or not request.target:
            from pyamf.remoting import amf3

            return amf3.RequestProcessor(self)
        else:
            from pyamf.remoting import amf0

            return amf0.RequestProcessor(self)

    def getResponse(self, amf_request):
        """
        Returns the response to the request.

        Any implementing gateway must define this function.

        @param amf_request: The AMF request.
        @type amf_request: L{Envelope<pyamf.remoting.Envelope>}

        @return: The AMF response.
        @rtype: L{Envelope<pyamf.remoting.Envelope>}
        """
        raise NotImplementedError

    def mustExposeRequest(self, service_request):
        """
        Decides whether the underlying http request should be exposed as the
        first argument to the method call. This is granular, looking at the
        service method first, then at the service level and finally checking
        the gateway.

        @rtype: C{bool}
        """
        expose_request = service_request.service.mustExposeRequest(service_request)

        if expose_request is None:
            if self.expose_request is None:
                return False

            return self.expose_request

        return expose_request

    def getAuthenticator(self, service_request):
        """
        Gets an authenticator callable based on the service_request. This is
        granular, looking at the service method first, then at the service
        level and finally to see if there is a global authenticator function
        for the gateway. Returns C{None} if one could not be found.
        """
        auth = service_request.service.getAuthenticator(service_request)

        if auth is None:
            return self.authenticator

        return auth

    def authenticateRequest(self, service_request, username, password, **kwargs):
        """
        Processes an authentication request. If no authenticator is supplied,
        then authentication succeeds.

        @return: Returns a C{bool} based on the result of authorization. A
            value of C{False} will stop processing the request and return an
            error to the client.
        @rtype: C{bool}
        """
        authenticator = self.getAuthenticator(service_request)

        if authenticator is None:
            return True

        args = (username, password)

        if hasattr(authenticator, '_pyamf_expose_request'):
            http_request = kwargs.get('http_request', None)
            args = (http_request,) + args

        return authenticator(*args) == True

    def getPreprocessor(self, service_request):
        """
        Gets a preprocessor callable based on the service_request. This is
        granular, looking at the service method first, then at the service
        level and finally to see if there is a global preprocessor function
        for the gateway. Returns C{None} if one could not be found.
        """
        preproc = service_request.service.getPreprocessor(service_request)

        if preproc is None:
            return self.preprocessor

        return preproc

    def preprocessRequest(self, service_request, *args, **kwargs):
        """
        Preprocesses a request.
        """
        processor = self.getPreprocessor(service_request)

        if processor is None:
            return

        args = (service_request,) + args

        if hasattr(processor, '_pyamf_expose_request'):
            http_request = kwargs.get('http_request', None)
            args = (http_request,) + args

        return processor(*args)

    def callServiceRequest(self, service_request, *args, **kwargs):
        """
        Executes the service_request call
        """
        if self.mustExposeRequest(service_request):
            http_request = kwargs.get('http_request', None)
            args = (http_request,) + args

        return service_request(*args)


def authenticate(func, c, expose_request=False):
    """
    A decorator that facilitates authentication per method. Setting
    C{expose_request} to C{True} will set the underlying request object (if
    there is one), usually HTTP and set it to the first argument of the
    authenticating callable. If there is no request object, the default is
    C{None}.

    @raise TypeError: C{func} and authenticator must be callable.
    """
    if not python.callable(func):
        raise TypeError('func must be callable')

    if not python.callable(c):
        raise TypeError('Authenticator must be callable')

    attr = func

    if isinstance(func, types.UnboundMethodType):
        attr = func.im_func

    if expose_request is True:
        c = globals()['expose_request'](c)

    setattr(attr, '_pyamf_authenticator', c)

    return func


def expose_request(func):
    """
    A decorator that adds an expose_request flag to the underlying callable.

    @raise TypeError: C{func} must be callable.
    """
    if not python.callable(func):
        raise TypeError("func must be callable")

    if isinstance(func, types.UnboundMethodType):
        setattr(func.im_func, '_pyamf_expose_request', True)
    else:
        setattr(func, '_pyamf_expose_request', True)

    return func


def preprocess(func, c, expose_request=False):
    """
    A decorator that facilitates preprocessing per method. Setting
    C{expose_request} to C{True} will set the underlying request object (if
    there is one), usually HTTP and set it to the first argument of the
    preprocessing callable. If there is no request object, the default is
    C{None}.

    @raise TypeError: C{func} and preprocessor must be callable.
    """
    if not python.callable(func):
        raise TypeError('func must be callable')

    if not python.callable(c):
        raise TypeError('Preprocessor must be callable')

    attr = func

    if isinstance(func, types.UnboundMethodType):
        attr = func.im_func

    if expose_request is True:
        c = globals()['expose_request'](c)

    setattr(attr, '_pyamf_preprocessor', c)

    return func


def format_exception():
    import traceback

    f = util.BufferedByteStream()

    traceback.print_exc(file=f)

    return f.getvalue()
