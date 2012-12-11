# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Twisted gateway tests.

@since: 0.1.0
"""

try:
    from twisted.internet import reactor, defer
    from twisted.python import failure
    from twisted.web import http, server, client, error, resource
    from twisted.trial import unittest

    from pyamf.remoting.gateway import twisted
except ImportError:
    twisted = None

    import unittest

import pyamf
from pyamf import remoting
from pyamf.remoting import gateway
from pyamf.flex import messaging


class TestService(object):
    def spam(self):
        return 'spam'

    def echo(self, x):
        return x


class BaseTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        if not twisted:
            self.skipTest("'twisted' is not available")


class TwistedServerTestCase(BaseTestCase):
    """
    """

    missing = object()

    def setUp(self):
        BaseTestCase.setUp(self)

        self.gw = twisted.TwistedGateway(expose_request=False)
        root = resource.Resource()
        root.putChild('', self.gw)

        self.p = reactor.listenTCP(0, server.Site(root), interface="127.0.0.1")
        self.port = self.p.getHost().port

    def tearDown(self):
        self.p.stopListening()

    def getPage(self, data=None, **kwargs):
        kwargs.setdefault('method', 'POST')
        kwargs['postdata'] = data

        return client.getPage("http://127.0.0.1:%d/" % (self.port,), **kwargs)

    def doRequest(self, service, body=missing, type=pyamf.AMF3, raw=False, decode=True):
        if not raw:
            if body is self.missing:
                body = []
            else:
                body = [body]

            env = remoting.Envelope(type)
            request = remoting.Request(service, body=body)
            env['/1'] = request

            body = remoting.encode(env).getvalue()

        d = self.getPage(body)

        if decode:
            d.addCallback(lambda result: remoting.decode(result))

        return d

    def test_invalid_method(self):
        """
        A classic GET on the xml server should return a NOT_ALLOWED.
        """
        d = self.getPage(method='GET')
        d = self.assertFailure(d, error.Error)
        d.addCallback(
            lambda exc: self.assertEqual(int(exc.args[0]), http.NOT_ALLOWED))

        return d

    def test_bad_content(self):
        d = self.getPage('spamandeggs')
        d = self.assertFailure(d, error.Error)

        d.addCallback(
            lambda exc: self.assertEqual(int(exc.args[0]), http.BAD_REQUEST))

        return d

    def test_process_request(self):
        def echo(data):
            return data

        self.gw.addService(echo)

        d = self.doRequest('echo', 'hello')

        def cb(response):
            self.assertEqual(response.amfVersion, pyamf.AMF3)

            self.assertTrue('/1' in response)
            body_response = response['/1']

            self.assertEqual(body_response.status, remoting.STATUS_OK)
            self.assertEqual(body_response.body, 'hello')

        return d.addCallback(cb)

    def test_deferred_service(self):
        def echo(data):
            x = defer.Deferred()
            reactor.callLater(0, x.callback, data)

            return x

        self.gw.addService(echo)
        d = self.doRequest('echo', 'hello')

        def cb(response):
            self.assertEqual(response.amfVersion, pyamf.AMF3)

            self.assertTrue('/1' in response)
            body_response = response['/1']

            self.assertEqual(body_response.status, remoting.STATUS_OK)
            self.assertEqual(body_response.body, 'hello')

        return d.addCallback(cb)

    def test_unknown_request(self):
        d = self.doRequest('echo', 'hello')

        def cb(response):
            message = response['/1']

            self.assertEqual(message.status, remoting.STATUS_ERROR)
            body = message.body

            self.assertTrue(isinstance(body, remoting.ErrorFault))
            self.assertEqual(body.code, 'Service.ResourceNotFound')

        return d.addCallback(cb)

    def test_expose_request(self):
        self.gw.expose_request = True
        self.executed = False

        def echo(http_request, data):
            self.assertTrue(isinstance(http_request, http.Request))

            self.assertTrue(hasattr(http_request, 'amf_request'))

            amf_request = http_request.amf_request

            self.assertEqual(amf_request.target, 'echo')
            self.assertEqual(amf_request.body, ['hello'])
            self.executed = True

            return data

        self.gw.addService(echo)

        d = self.doRequest('echo', 'hello', type=pyamf.AMF0)

        def check_response(response):
            self.assertTrue(self.executed)

        return d.addCallback(check_response)

    def test_preprocessor(self):
        d = defer.Deferred()

        def pp(sr):
            self.assertIdentical(sr, self.service_request)
            d.callback(None)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, preprocessor=pp)
        self.service_request = gateway.ServiceRequest(None, gw.services['echo'], None)

        gw.preprocessRequest(self.service_request)

        return d

    def test_exposed_preprocessor(self):
        d = defer.Deferred()

        def pp(hr, sr):
            self.assertEqual(hr, 'hello')
            self.assertIdentical(sr, self.service_request)
            d.callback(None)

        pp = gateway.expose_request(pp)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, preprocessor=pp)
        self.service_request = gateway.ServiceRequest(None, gw.services['echo'], None)

        gw.preprocessRequest(self.service_request, http_request='hello')

        return d

    def test_exposed_preprocessor_no_request(self):
        d = defer.Deferred()

        def pp(hr, sr):
            self.assertEqual(hr, None)
            self.assertIdentical(sr, self.service_request)
            d.callback(None)

        pp = gateway.expose_request(pp)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, preprocessor=pp)
        self.service_request = gateway.ServiceRequest(None, gw.services['echo'], None)

        gw.preprocessRequest(self.service_request)

        return d

    def test_authenticate(self):
        d = defer.Deferred()

        def auth(u, p):
            try:
                self.assertEqual(u, 'u')
                self.assertEqual(p, 'p')
            except:
                d.errback(failure.Failure())
            else:
                d.callback(None)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, authenticator=auth)
        self.service_request = gateway.ServiceRequest(None, gw.services['echo'], None)

        gw.authenticateRequest(self.service_request, 'u', 'p')

        return d

    def test_exposed_authenticate(self):
        d = defer.Deferred()

        def auth(request, u, p):
            try:
                self.assertEqual(request, 'foo')
                self.assertEqual(u, 'u')
                self.assertEqual(p, 'p')
            except:
                d.errback(failure.Failure())
            else:
                d.callback(None)

        auth = gateway.expose_request(auth)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, authenticator=auth)
        self.service_request = gateway.ServiceRequest(None, gw.services['echo'], None)

        gw.authenticateRequest(self.service_request, 'u', 'p', http_request='foo')

        return d

    def test_encoding_error(self):
        encode = twisted.remoting.encode

        def force_error(amf_request, context=None):
            raise pyamf.EncodeError

        def echo(request, data):
            return data

        self.gw.addService(echo)

        d = self.doRequest('echo', 'hello')
        twisted.remoting.encode = force_error

        def switch(x):
            twisted.remoting.encode = encode

        d = self.assertFailure(d, error.Error)

        def check(exc):
            self.assertEqual(int(exc.args[0]), http.INTERNAL_SERVER_ERROR)
            self.assertTrue(exc.args[1].startswith('500 Internal Server Error'))

        d.addCallback(check)

        return d.addBoth(switch)

    def test_tuple(self):
        def echo(data):
            return data

        self.gw.addService(echo)
        d = self.doRequest('echo', ('Hi', 'Mom'))

        def cb(response):
            body_response = response['/1']

            self.assertEqual(body_response.status, remoting.STATUS_OK)
            self.assertEqual(body_response.body, ['Hi', 'Mom'])

        return d.addCallback(cb)

    def test_timezone(self):
        import datetime

        self.executed = False

        td = datetime.timedelta(hours=-5)
        now = datetime.datetime.utcnow()

        def echo(d):
            self.assertEqual(d, now + td)
            self.executed = True

            return d

        self.gw.addService(echo)
        self.gw.timezone_offset = -18000

        d = self.doRequest('echo', now)

        def cb(response):
            message = response['/1']

            self.assertEqual(message.status, remoting.STATUS_OK)
            self.assertEqual(message.body, now)

        return d.addCallback(cb)

    def test_double_encode(self):
        """
        See ticket #648
        """
        self.counter = 0

        def service():
            self.counter += 1

        self.gw.addService(service)

        d = self.doRequest('service')

        def cb(result):
            self.assertEqual(self.counter, 1)

        return d.addCallback(cb)


class DummyHTTPRequest:
    def __init__(self):
        self.headers = {}
        self.finished = False

    def setResponseCode(self, status):
        self.status = status

    def setHeader(self, n, v):
        self.headers[n] = v

    def write(self, s):
        self.content = s

    def finish(self):
        self.finished = True


class TwistedGatewayTestCase(BaseTestCase):
    def test_finalise_request(self):
        request = DummyHTTPRequest()
        gw = twisted.TwistedGateway()

        gw._finaliseRequest(request, 200, 'xyz', 'text/plain')

        self.assertEqual(request.status, 200)
        self.assertEqual(request.content, 'xyz')

        self.assertTrue('Content-Type' in request.headers)
        self.assertEqual(request.headers['Content-Type'], 'text/plain')
        self.assertTrue('Content-Length' in request.headers)
        self.assertEqual(request.headers['Content-Length'], '3')

        self.assertTrue(request.finished)

    def test_get_processor(self):
        a3 = pyamf.ASObject({'target': 'null'})
        a0 = pyamf.ASObject({'target': 'foo.bar'})

        gw = twisted.TwistedGateway()

        self.assertTrue(isinstance(gw.getProcessor(a3), twisted.AMF3RequestProcessor))
        self.assertTrue(isinstance(gw.getProcessor(a0), twisted.AMF0RequestProcessor))


class AMF0RequestProcessorTestCase(BaseTestCase):
    """
    """

    def getProcessor(self, *args, **kwargs):
        """
        Return an L{twisted.AMF0RequestProcessor} attached to a gateway.
        Supply the gateway args/kwargs.
        """
        self.gw = twisted.TwistedGateway(*args, **kwargs)
        self.processor = twisted.AMF0RequestProcessor(self.gw)

        return self.processor

    def test_unknown_service_request(self):
        p = self.getProcessor({'echo': lambda x: x})

        request = remoting.Request('sdf')

        d = p(request)

        self.assertTrue(isinstance(d, defer.Deferred))
        response = d.result
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertTrue(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, remoting.ErrorFault))

        self.assertEqual(response.body.code, 'Service.ResourceNotFound')
        self.assertEqual(response.body.description, u'Unknown service sdf')

    def test_error_auth(self):
        def auth(u, p):
            raise IndexError

        p = self.getProcessor({'echo': lambda x: x}, authenticator=auth)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        d = p(request)

        self.assertTrue(isinstance(d, defer.Deferred))

        response = d.result
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertTrue(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, remoting.ErrorFault))
        self.assertEqual(response.body.code, 'IndexError')

    def test_auth_fail(self):
        def auth(u, p):
            return False

        p = self.getProcessor({'echo': lambda x: x}, authenticator=auth)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        d = p(request)

        self.assertTrue(isinstance(d, defer.Deferred))

        def check_response(response):
            self.assertTrue(isinstance(response, remoting.Response))
            self.assertTrue(response.status, remoting.STATUS_ERROR)
            self.assertTrue(isinstance(response.body, remoting.ErrorFault))
            self.assertEqual(response.body.code, 'AuthenticationError')

        d.addCallback(check_response)

        return d

    def test_deferred_auth(self):
        d = defer.Deferred()

        def auth(u, p):
            return reactor.callLater(0, lambda: True)

        p = self.getProcessor({'echo': lambda x: x}, authenticator=auth)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        def cb(result):
            self.assertTrue(result)
            d.callback(None)

        p(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_error_preprocessor(self):
        def preprocessor(service_request):
            raise IndexError

        p = self.getProcessor({'echo': lambda x: x}, preprocessor=preprocessor)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        d = p(request)

        def check_response(response):
            self.assertTrue(isinstance(response, remoting.Response))
            self.assertTrue(response.status, remoting.STATUS_ERROR)
            self.assertTrue(isinstance(response.body, remoting.ErrorFault))
            self.assertEqual(response.body.code, 'IndexError')

        d.addCallback(check_response)

        return d

    def test_deferred_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(u, p):
            return reactor.callLater(0, lambda: True)

        p = self.getProcessor({'echo': lambda x: x}, preprocessor=preprocessor)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        def cb(result):
            self.assertTrue(result)
            d.callback(None)

        p(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(service_request):
            d.callback(None)

        p = self.getProcessor({'echo': lambda x: x}, preprocessor=preprocessor)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        p(request).addErrback(lambda failure: d.errback())

        return d

    def test_exposed_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(http_request, service_request):
            return reactor.callLater(0, lambda: True)

        preprocessor = gateway.expose_request(preprocessor)
        p = self.getProcessor({'echo': lambda x: x}, preprocessor=preprocessor)

        request = remoting.Request('echo', envelope=remoting.Envelope())

        def cb(result):
            self.assertTrue(result)
            d.callback(None)

        p(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_error_body(self):
        def echo(x):
            raise KeyError

        p = self.getProcessor({'echo': echo})
        request = remoting.Request('echo', envelope=remoting.Envelope())

        d = p(request)

        def check_result(response):
            self.assertTrue(isinstance(response, remoting.Response))
            self.assertTrue(response.status, remoting.STATUS_ERROR)
            self.assertTrue(isinstance(response.body, remoting.ErrorFault))
            self.assertEqual(response.body.code, 'KeyError')

        d.addCallback(check_result)

        return d

    def test_error_deferred_body(self):
        d = defer.Deferred()

        def echo(x):
            d2 = defer.Deferred()

            def cb(result):
                raise IndexError

            reactor.callLater(0, lambda: d2.callback(None))

            d2.addCallback(cb)
            return d2

        p = self.getProcessor({'echo': echo}, expose_request=False)

        request = remoting.Request('echo', envelope=remoting.Envelope())
        request.body = ['a']

        def cb(result):
            self.assertTrue(isinstance(result, remoting.Response))
            self.assertTrue(result.status, remoting.STATUS_ERROR)
            self.assertTrue(isinstance(result.body, remoting.ErrorFault))
            self.assertEqual(result.body.code, 'IndexError')

        return p(request).addCallback(cb).addErrback(lambda x: d.errback())


class AMF3RequestProcessorTestCase(BaseTestCase):
    def test_unknown_service_request(self):
        gw = twisted.TwistedGateway({'echo': lambda x: x}, expose_request=False)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='ss')])

        d = proc(request)

        self.assertTrue(isinstance(d, defer.Deferred))
        response = d.result
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertTrue(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, messaging.ErrorMessage))

    def test_error_preprocessor(self):
        def preprocessor(service_request, *args):
            raise IndexError

        gw = twisted.TwistedGateway({'echo': lambda x: x},
            expose_request=False, preprocessor=preprocessor)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        d = proc(request)

        self.assertTrue(isinstance(d, defer.Deferred))
        response = d.result
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertTrue(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, messaging.ErrorMessage))
        self.assertEqual(response.body.faultCode, 'IndexError')

    def test_deferred_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(u, *args):
            d2 = defer.Deferred()
            reactor.callLater(0, lambda: d2.callback(None))

            return d2

        gw = twisted.TwistedGateway({'echo': lambda x: x}, expose_request=False, preprocessor=preprocessor)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        def cb(result):
            self.assertTrue(result)
            d.callback(None)

        proc(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(service_request, *args):
            d.callback(None)

        gw = twisted.TwistedGateway({'echo': lambda x: x}, expose_request=False, preprocessor=preprocessor)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        proc(request).addErrback(lambda failure: d.errback())

        return d

    def test_exposed_preprocessor(self):
        d = defer.Deferred()

        def preprocessor(http_request, service_request):
            return reactor.callLater(0, lambda: True)

        preprocessor = gateway.expose_request(preprocessor)
        gw = twisted.TwistedGateway({'echo': lambda x: x}, expose_request=False, preprocessor=preprocessor)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        def cb(result):
            try:
                self.assertTrue(result)
            except:
                d.errback()
            else:
                d.callback(None)

        proc(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_error_body(self):
        def echo(x):
            raise KeyError

        gw = twisted.TwistedGateway({'echo': echo}, expose_request=False)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        d = proc(request)

        self.assertTrue(isinstance(d, defer.Deferred))
        response = d.result
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertTrue(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, messaging.ErrorMessage))
        self.assertEqual(response.body.faultCode, 'KeyError')

    def test_error_deferred_body(self):
        d = defer.Deferred()

        def echo(x):
            d2 = defer.Deferred()

            def cb(result):
                raise IndexError

            reactor.callLater(0, lambda: d2.callback(None))

            d2.addCallback(cb)
            return d2

        gw = twisted.TwistedGateway({'echo': echo}, expose_request=False)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=['spam.eggs'], operation='echo')])

        def cb(result):
            try:
                self.assertTrue(isinstance(result, remoting.Response))
                self.assertTrue(result.status, remoting.STATUS_ERROR)
                self.assertTrue(isinstance(result.body, messaging.ErrorMessage))
                self.assertEqual(result.body.faultCode, 'IndexError')
            except:
                d.errback()
            else:
                d.callback(None)

        proc(request).addCallback(cb).addErrback(lambda x: d.errback())

        return d

    def test_destination(self):
        d = defer.Deferred()

        gw = twisted.TwistedGateway({'spam.eggs': lambda x: x}, expose_request=False)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.RemotingMessage(body=[None], destination='spam', operation='eggs')])

        def cb(result):
            try:
                self.assertTrue(result)
            except:
                d.errback()
            else:
                d.callback(None)

        proc(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d

    def test_async(self):
        d = defer.Deferred()

        gw = twisted.TwistedGateway({'spam.eggs': lambda x: x}, expose_request=False)
        proc = twisted.AMF3RequestProcessor(gw)

        request = remoting.Request('null', body=[messaging.AsyncMessage(body=[None], destination='spam', operation='eggs')])

        def cb(result):
            msg = result.body

            try:
                self.assertTrue(isinstance(msg, messaging.AcknowledgeMessage))
            except:
                d.errback()
            else:
                d.callback(None)

        proc(request).addCallback(cb).addErrback(lambda failure: d.errback())

        return d
