# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Remoting client implementation.

@since: 0.1.0
"""

import urllib2
import urlparse

import pyamf
from pyamf import remoting

try:
    from gzip import GzipFile
except ImportError:
    GzipFile = False

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


#: Default user agent is `PyAMF/x.x(.x)`.
DEFAULT_USER_AGENT = 'PyAMF/%s' % (pyamf.version,)


class ServiceMethodProxy(object):
    """
    Serves as a proxy for calling a service method.

    @ivar service: The parent service.
    @type service: L{ServiceProxy}
    @ivar name: The name of the method.
    @type name: C{str} or C{None}

    @see: L{ServiceProxy.__getattr__}
    """

    def __init__(self, service, name):
        self.service = service
        self.name = name

    def __call__(self, *args):
        """
        Inform the proxied service that this function has been called.
        """

        return self.service._call(self, *args)

    def __str__(self):
        """
        Returns the full service name, including the method name if there is
        one.
        """
        service_name = str(self.service)

        if self.name is not None:
            service_name = '%s.%s' % (service_name, self.name)

        return service_name


class ServiceProxy(object):
    """
    Serves as a service object proxy for RPC calls. Generates
    L{ServiceMethodProxy} objects for method calls.

    @see: L{RequestWrapper} for more info.

    @ivar _gw: The parent gateway
    @type _gw: L{RemotingService}
    @ivar _name: The name of the service
    @type _name: L{str}
    @ivar _auto_execute: If set to C{True}, when a service method is called,
        the AMF request is immediately sent to the remote gateway and a
        response is returned. If set to C{False}, a C{RequestWrapper}
        is returned, waiting for the underlying gateway to fire the
        L{execute <RemotingService.execute>} method.
    """

    def __init__(self, gw, name, auto_execute=True):
        self._gw = gw
        self._name = name
        self._auto_execute = auto_execute

    def __getattr__(self, name):
        return ServiceMethodProxy(self, name)

    def _call(self, method_proxy, *args):
        """
        Executed when a L{ServiceMethodProxy} is called. Adds a request to the
        underlying gateway.
        """
        request = self._gw.addRequest(method_proxy, *args)

        if self._auto_execute:
            response = self._gw.execute_single(request)

            if response.status == remoting.STATUS_ERROR:
                if hasattr(response.body, 'raiseException'):
                    try:
                        response.body.raiseException()
                    except:
                        raise
                else:
                    raise remoting.RemotingError

            return response.body

        return request

    def __call__(self, *args):
        """
        This allows services to be 'called' without a method name.
        """
        return self._call(ServiceMethodProxy(self, None), *args)

    def __str__(self):
        """
        Returns a string representation of the name of the service.
        """
        return self._name


class RequestWrapper(object):
    """
    A container object that wraps a service method request.

    @ivar gw: The underlying gateway.
    @type gw: L{RemotingService}
    @ivar id: The id of the request.
    @type id: C{str}
    @ivar service: The service proxy.
    @type service: L{ServiceProxy}
    @ivar args: The args used to invoke the call.
    @type args: C{list}
    """

    def __init__(self, gw, id_, service, *args):
        self.gw = gw
        self.id = id_
        self.service = service
        self.args = args

    def __str__(self):
        return str(self.id)

    def setResponse(self, response):
        """
        A response has been received by the gateway
        """
        self.response = response
        self.result = self.response.body

        if isinstance(self.result, remoting.ErrorFault):
            self.result.raiseException()

    def _get_result(self):
        """
        Returns the result of the called remote request. If the request has not
        yet been called, an C{AttributeError} exception is raised.
        """
        if not hasattr(self, '_result'):
            raise AttributeError(
                "'RequestWrapper' object has no attribute 'result'")

        return self._result

    def _set_result(self, result):
        self._result = result

    result = property(_get_result, _set_result)


class RemotingService(object):
    """
    Acts as a client for AMF calls.

    @ivar url: The url of the remote gateway. Accepts C{http} or C{https} as
        valid schemes.
    @type url: C{string}
    @ivar requests: The list of pending requests to process.
    @type requests: C{list}
    @ivar request_number: A unique identifier for tracking the number of
        requests.
    @ivar amf_version: The AMF version to use. See
        L{ENCODING_TYPES<pyamf.ENCODING_TYPES>}.
    @ivar referer: The referer, or HTTP referer, identifies the address of the
        client. Ignored by default.
    @type referer: C{string}
    @ivar user_agent: Contains information about the user agent (client)
        originating the request. See L{DEFAULT_USER_AGENT}.
    @type user_agent: C{string}
    @ivar headers: A list of persistent headers to send with each request.
    @type headers: L{HeaderCollection<pyamf.remoting.HeaderCollection>}
    @ivar http_headers: A dict of HTTP headers to apply to the underlying HTTP
        connection.
    @type http_headers: L{dict}
    @ivar strict: Whether to use strict AMF en/decoding or not.
    @ivar opener: The function used to power the connection to the remote
        server. Defaults to U{urllib2.urlopen<http://
        docs.python.org/library/urllib2.html#urllib2.urlopen}.
    """

    def __init__(self, url, amf_version=pyamf.AMF0, **kwargs):
        self.original_url = url
        self.amf_version = amf_version

        self.requests = []
        self.request_number = 1
        self.headers = remoting.HeaderCollection()
        self.http_headers = {}
        self.proxy_args = None

        self.user_agent = kwargs.pop('user_agent', DEFAULT_USER_AGENT)
        self.referer = kwargs.pop('referer', None)
        self.strict = kwargs.pop('strict', False)
        self.logger = kwargs.pop('logger', None)
        self.opener = kwargs.pop('opener', urllib2.urlopen)

        if kwargs:
            raise TypeError('Unexpected keyword arguments %r' % (kwargs,))

        self._setUrl(url)

    def _setUrl(self, url):
        """
        """
        self.url = urlparse.urlparse(url)
        self._root_url = url

        if not self.url[0] in ('http', 'https'):
            raise ValueError('Unknown scheme %r' % (self.url[0],))

        if self.logger:
            self.logger.info('Connecting to %r', self._root_url)
            self.logger.debug('Referer: %r', self.referer)
            self.logger.debug('User-Agent: %r', self.user_agent)

    def setProxy(self, host, type='http'):
        """
        Set the proxy for all requests to use.

        @see: U{The Python Docs<http://docs.python.org/library/urllib2.html#
            urllib2.Request.set_proxy}
        """
        self.proxy_args = (host, type)

    def addHeader(self, name, value, must_understand=False):
        """
        Sets a persistent header to send with each request.

        @param name: Header name.
        """
        self.headers[name] = value
        self.headers.set_required(name, must_understand)

    def addHTTPHeader(self, name, value):
        """
        Adds a header to the underlying HTTP connection.
        """
        self.http_headers[name] = value

    def removeHTTPHeader(self, name):
        """
        Deletes an HTTP header.
        """
        del self.http_headers[name]

    def getService(self, name, auto_execute=True):
        """
        Returns a L{ServiceProxy} for the supplied name. Sets up an object that
        can have method calls made to it that build the AMF requests.

        @rtype: L{ServiceProxy}
        """
        if not isinstance(name, basestring):
            raise TypeError('string type required')

        return ServiceProxy(self, name, auto_execute)

    def getRequest(self, id_):
        """
        Gets a request based on the id.

        :raise LookupError: Request not found.
        """
        for request in self.requests:
            if request.id == id_:
                return request

        raise LookupError("Request %r not found" % (id_,))

    def addRequest(self, service, *args):
        """
        Adds a request to be sent to the remoting gateway.
        """
        wrapper = RequestWrapper(self, '/%d' % self.request_number,
            service, *args)

        self.request_number += 1
        self.requests.append(wrapper)

        if self.logger:
            self.logger.debug('Adding request %s%r', wrapper.service, args)

        return wrapper

    def removeRequest(self, service, *args):
        """
        Removes a request from the pending request list.

        """
        if isinstance(service, RequestWrapper):
            if self.logger:
                self.logger.debug('Removing request: %s',
                    self.requests[self.requests.index(service)])
            del self.requests[self.requests.index(service)]

            return

        for request in self.requests:
            if request.service == service and request.args == args:
                if self.logger:
                    self.logger.debug('Removing request: %s',
                        self.requests[self.requests.index(request)])
                del self.requests[self.requests.index(request)]

                return

        raise LookupError("Request not found")

    def getAMFRequest(self, requests):
        """
        Builds an AMF request {LEnvelope<pyamf.remoting.Envelope>} from a
        supplied list of requests.
        """
        envelope = remoting.Envelope(self.amf_version)

        if self.logger:
            self.logger.debug('AMF version: %s' % self.amf_version)

        for request in requests:
            service = request.service
            args = list(request.args)

            envelope[request.id] = remoting.Request(str(service), args)

        envelope.headers = self.headers

        return envelope

    def _get_execute_headers(self):
        headers = self.http_headers.copy()

        headers.update({
            'Content-Type': remoting.CONTENT_TYPE,
            'User-Agent': self.user_agent
        })

        if self.referer is not None:
            headers['Referer'] = self.referer

        return headers

    def execute_single(self, request):
        """
        Builds, sends and handles the response to a single request, returning
        the response.
        """
        if self.logger:
            self.logger.debug('Executing single request: %s', request)

        self.removeRequest(request)

        body = remoting.encode(self.getAMFRequest([request]), strict=self.strict)

        http_request = urllib2.Request(self._root_url, body.getvalue(),
            self._get_execute_headers())

        if self.proxy_args:
            http_request.set_proxy(*self.proxy_args)

        envelope = self._getResponse(http_request)

        return envelope[request.id]

    def execute(self):
        """
        Builds, sends and handles the responses to all requests listed in
        C{self.requests}.
        """
        requests = self.requests[:]

        for r in requests:
            self.removeRequest(r)

        body = remoting.encode(self.getAMFRequest(requests),
            strict=self.strict)

        http_request = urllib2.Request(self._root_url, body.getvalue(),
            self._get_execute_headers())

        if self.proxy_args:
            http_request.set_proxy(*self.proxy_args)

        envelope = self._getResponse(http_request)

        return envelope

    def _getResponse(self, http_request):
        """
        Gets and handles the HTTP response from the remote gateway.
        """
        if self.logger:
            self.logger.debug('Sending POST request to %s', self._root_url)

        try:
            fbh = self.opener(http_request)
        except urllib2.URLError, e:
            if self.logger:
                self.logger.exception('Failed request for %s',
                    self._root_url)

            raise remoting.RemotingError(str(e))

        http_message = fbh.info()

        content_encoding = http_message.getheader('Content-Encoding')
        content_length = http_message.getheader('Content-Length') or -1
        content_type = http_message.getheader('Content-Type')
        server = http_message.getheader('Server')

        if self.logger:
            self.logger.debug('Content-Type: %r', content_type)
            self.logger.debug('Content-Encoding: %r', content_encoding)
            self.logger.debug('Content-Length: %r', content_length)
            self.logger.debug('Server: %r', server)

        if content_type != remoting.CONTENT_TYPE:
            if self.logger:
                self.logger.debug('Body = %s', fbh.read())

            raise remoting.RemotingError('Incorrect MIME type received. '
                '(got: %s)' % (content_type,))

        bytes = fbh.read(int(content_length))

        if self.logger:
            self.logger.debug('Read %d bytes for the response', len(bytes))

        if content_encoding and content_encoding.strip().lower() == 'gzip':
            if not GzipFile:
                raise remoting.RemotingError(
                    'Decompression of Content-Encoding: %s not available.' % (
                        content_encoding,))

            compressedstream = StringIO(bytes)
            gzipper = GzipFile(fileobj=compressedstream)
            bytes = gzipper.read()
            gzipper.close()

        response = remoting.decode(bytes, strict=self.strict)

        if self.logger:
            self.logger.debug('Response: %s', response)

        if remoting.APPEND_TO_GATEWAY_URL in response.headers:
            self.original_url += response.headers[remoting.APPEND_TO_GATEWAY_URL]

            self._setUrl(self.original_url)
        elif remoting.REPLACE_GATEWAY_URL in response.headers:
            self.original_url = response.headers[remoting.REPLACE_GATEWAY_URL]

            self._setUrl(self.original_url)

        if remoting.REQUEST_PERSISTENT_HEADER in response.headers:
            data = response.headers[remoting.REQUEST_PERSISTENT_HEADER]

            for k, v in data.iteritems():
                self.headers[k] = v

        return response

    def setCredentials(self, username, password):
        """
        Sets authentication credentials for accessing the remote gateway.
        """
        self.addHeader('Credentials', dict(userid=username.decode('utf-8'),
            password=password.decode('utf-8')), True)
