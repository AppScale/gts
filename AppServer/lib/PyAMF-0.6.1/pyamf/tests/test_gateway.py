# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
General gateway tests.

@since: 0.1.0
"""

import unittest
import sys

import pyamf
from pyamf import remoting
from pyamf.remoting import gateway, amf0


class TestService(object):
    def spam(self):
        return 'spam'

    def echo(self, x):
        return x


class FaultTestCase(unittest.TestCase):
    def test_create(self):
        x = remoting.ErrorFault()

        self.assertEqual(x.code, '')
        self.assertEqual(x.details, '')
        self.assertEqual(x.description, '')

        x = remoting.ErrorFault(code=404, details='Not Found', description='Spam eggs')

        self.assertEqual(x.code, 404)
        self.assertEqual(x.details, 'Not Found')
        self.assertEqual(x.description, 'Spam eggs')

    def test_build(self):
        fault = None

        try:
            raise TypeError("Unknown type")
        except TypeError:
            fault = amf0.build_fault(*sys.exc_info())

        self.assertTrue(isinstance(fault, remoting.ErrorFault))
        self.assertEqual(fault.level, 'error')
        self.assertEqual(fault.code, 'TypeError')
        self.assertEqual(fault.details, None)

    def test_build_traceback(self):
        fault = None

        try:
            raise TypeError("Unknown type")
        except TypeError:
            fault = amf0.build_fault(include_traceback=True, *sys.exc_info())

        self.assertTrue(isinstance(fault, remoting.ErrorFault))
        self.assertEqual(fault.level, 'error')
        self.assertEqual(fault.code, 'TypeError')
        self.assertTrue("\\n" not in fault.details)

    def test_encode(self):
        encoder = pyamf.get_encoder(pyamf.AMF0)
        decoder = pyamf.get_decoder(pyamf.AMF0)
        decoder.stream = encoder.stream

        try:
            raise TypeError("Unknown type")
        except TypeError:
            encoder.writeElement(amf0.build_fault(*sys.exc_info()))

        buffer = encoder.stream
        buffer.seek(0, 0)

        fault = decoder.readElement()
        old_fault = amf0.build_fault(*sys.exc_info())

        self.assertEqual(fault.level, old_fault.level)
        self.assertEqual(fault.type, old_fault.type)
        self.assertEqual(fault.code, old_fault.code)
        self.assertEqual(fault.details, old_fault.details)
        self.assertEqual(fault.description, old_fault.description)

    def test_explicit_code(self):
        class X(Exception):
            _amf_code = 'Server.UnknownResource'

        try:
            raise X()
        except X:
            fault = amf0.build_fault(*sys.exc_info())

        self.assertEqual(fault.code, 'Server.UnknownResource')


class ServiceWrapperTestCase(unittest.TestCase):
    def test_create(self):
        x = gateway.ServiceWrapper('blah')

        self.assertEqual(x.service, 'blah')

    def test_create_preprocessor(self):
        x = gateway.ServiceWrapper('blah', preprocessor=ord)

        self.assertEqual(x.preprocessor, ord)

    def test_cmp(self):
        x = gateway.ServiceWrapper('blah')
        y = gateway.ServiceWrapper('blah')
        z = gateway.ServiceWrapper('bleh')

        self.assertEqual(x, y)
        self.assertNotEquals(y, z)

    def test_call(self):
        def add(x, y):
            self.assertEqual(x, 1)
            self.assertEqual(y, 2)

            return x + y

        x = gateway.ServiceWrapper(add)

        self.assertTrue(callable(x))
        self.assertEqual(x(None, [1, 2]), 3)

        x = gateway.ServiceWrapper('blah')

        self.assertRaises(gateway.UnknownServiceMethodError, x, None, [])

        x = gateway.ServiceWrapper(TestService)

        self.assertRaises(gateway.UnknownServiceMethodError, x, None, [])
        self.assertEqual(x('spam', []), 'spam')

        self.assertRaises(gateway.UnknownServiceMethodError, x, 'xyx', [])
        self.assertRaises(gateway.InvalidServiceMethodError, x, '_private', [])

        self.assertEqual(x('echo', [x]), x)


class ServiceRequestTestCase(unittest.TestCase):
    def test_create(self):
        sw = gateway.ServiceWrapper(TestService)
        request = remoting.Envelope()

        x = gateway.ServiceRequest(request, sw, None)

        self.assertEqual(x.request, request)
        self.assertEqual(x.service, sw)
        self.assertEqual(x.method, None)

    def test_call(self):
        sw = gateway.ServiceWrapper(TestService)
        request = remoting.Envelope()

        x = gateway.ServiceRequest(request, sw, None)

        self.assertRaises(gateway.UnknownServiceMethodError, x)

        x = gateway.ServiceRequest(request, sw, 'spam')
        self.assertEqual(x(), 'spam')

        x = gateway.ServiceRequest(request, sw, 'echo')
        self.assertEqual(x(x), x)


class ServiceCollectionTestCase(unittest.TestCase):
    def test_contains(self):
        x = gateway.ServiceCollection()

        self.assertFalse(TestService in x)
        self.assertFalse('spam.eggs' in x)

        x['spam.eggs'] = gateway.ServiceWrapper(TestService)

        self.assertTrue(TestService in x)
        self.assertTrue('spam.eggs' in x)


class BaseGatewayTestCase(unittest.TestCase):
    def test_create(self):
        x = gateway.BaseGateway()
        self.assertEqual(x.services, {})

        x = gateway.BaseGateway({})
        self.assertEqual(x.services, {})

        x = gateway.BaseGateway({})
        self.assertEqual(x.services, {})

        x = gateway.BaseGateway({'x': TestService})
        self.assertEqual(x.services, {'x': TestService})

        x = gateway.BaseGateway({}, timezone_offset=-180)
        self.assertEqual(x.timezone_offset, -180)

        self.assertRaises(TypeError, gateway.BaseGateway, [])
        self.assertRaises(TypeError, gateway.BaseGateway, foo='bar')

    def test_add_service(self):
        gw = gateway.BaseGateway()
        self.assertEqual(gw.services, {})

        gw.addService(TestService)
        self.assertTrue(TestService in gw.services)
        self.assertTrue('TestService' in gw.services)

        del gw.services['TestService']

        gw.addService(TestService, 'spam.eggs')
        self.assertTrue(TestService in gw.services)
        self.assertTrue('spam.eggs' in gw.services)

        del gw.services['spam.eggs']

        class SpamService(object):
            def __str__(self):
                return 'spam'

            def __call__(*args, **kwargs):
                pass

        x = SpamService()

        gw.addService(x)
        self.assertTrue(x in gw.services)
        self.assertTrue('spam' in gw.services)

        del gw.services['spam']

        self.assertEqual(gw.services, {})

        self.assertRaises(TypeError, gw.addService, 1)

        import new

        temp = new.module('temp')
        gw.addService(temp)

        self.assertTrue(temp in gw.services)
        self.assertTrue('temp' in gw.services)

        del gw.services['temp']

        self.assertEqual(gw.services, {})

    def test_remove_service(self):
        gw = gateway.BaseGateway({'test': TestService})
        self.assertTrue('test' in gw.services)
        wrapper = gw.services['test']

        gw.removeService('test')

        self.assertFalse('test' in gw.services)
        self.assertFalse(TestService in gw.services)
        self.assertFalse(wrapper in gw.services)
        self.assertEqual(gw.services, {})

        gw = gateway.BaseGateway({'test': TestService})
        self.assertTrue(TestService in gw.services)
        wrapper = gw.services['test']

        gw.removeService(TestService)

        self.assertFalse('test' in gw.services)
        self.assertFalse(TestService in gw.services)
        self.assertFalse(wrapper in gw.services)
        self.assertEqual(gw.services, {})

        gw = gateway.BaseGateway({'test': TestService})
        self.assertTrue(TestService in gw.services)
        wrapper = gw.services['test']

        gw.removeService(wrapper)

        self.assertFalse('test' in gw.services)
        self.assertFalse(TestService in gw.services)
        self.assertFalse(wrapper in gw.services)
        self.assertEqual(gw.services, {})

        x = TestService()
        gw = gateway.BaseGateway({'test': x})

        gw.removeService(x)

        self.assertFalse('test' in gw.services)
        self.assertEqual(gw.services, {})

        self.assertRaises(NameError, gw.removeService, 'test')
        self.assertRaises(NameError, gw.removeService, TestService)
        self.assertRaises(NameError, gw.removeService, wrapper)

    def test_service_request(self):
        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()

        message = remoting.Request('spam', [], envelope=envelope)
        self.assertRaises(gateway.UnknownServiceError, gw.getServiceRequest,
            message, 'spam')

        message = remoting.Request('test.spam', [], envelope=envelope)
        sr = gw.getServiceRequest(message, 'test.spam')

        self.assertTrue(isinstance(sr, gateway.ServiceRequest))
        self.assertEqual(sr.request, envelope)
        self.assertEqual(sr.service, TestService)
        self.assertEqual(sr.method, 'spam')

        message = remoting.Request('test')
        sr = gw.getServiceRequest(message, 'test')

        self.assertTrue(isinstance(sr, gateway.ServiceRequest))
        self.assertEqual(sr.request, None)
        self.assertEqual(sr.service, TestService)
        self.assertEqual(sr.method, None)

        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()
        message = remoting.Request('test')

        sr = gw.getServiceRequest(message, 'test')

        self.assertTrue(isinstance(sr, gateway.ServiceRequest))
        self.assertEqual(sr.request, None)
        self.assertEqual(sr.service, TestService)
        self.assertEqual(sr.method, None)

        # try to access an unknown service
        message = remoting.Request('spam')
        self.assertRaises(gateway.UnknownServiceError, gw.getServiceRequest,
            message, 'spam')

        # check x.x calls
        message = remoting.Request('test.test')
        sr = gw.getServiceRequest(message, 'test.test')

        self.assertTrue(isinstance(sr, gateway.ServiceRequest))
        self.assertEqual(sr.request, None)
        self.assertEqual(sr.service, TestService)
        self.assertEqual(sr.method, 'test')

    def test_long_service_name(self):
        gw = gateway.BaseGateway({'a.c.b.d': TestService})
        envelope = remoting.Envelope()

        message = remoting.Request('a.c.b.d', [], envelope=envelope)
        sr = gw.getServiceRequest(message, 'a.c.b.d.spam')

        self.assertTrue(isinstance(sr, gateway.ServiceRequest))
        self.assertEqual(sr.request, envelope)
        self.assertEqual(sr.service, TestService)
        self.assertEqual(sr.method, 'spam')

    def test_get_response(self):
        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()

        self.assertRaises(NotImplementedError, gw.getResponse, envelope)

    def test_process_request(self):
        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()

        request = remoting.Request('test.spam', envelope=envelope)

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_unknown_service(self):
        # Test a non existant service call
        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()

        request = remoting.Request('nope', envelope=envelope)
        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertFalse(gw.debug)
        self.assertTrue(isinstance(response, remoting.Message))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, remoting.ErrorFault))

        self.assertEqual(response.body.code, 'Service.ResourceNotFound')
        self.assertEqual(response.body.description, 'Unknown service nope')
        self.assertEqual(response.body.details, None)

    def test_debug_traceback(self):
        # Test a non existant service call
        gw = gateway.BaseGateway({'test': TestService}, debug=True)
        envelope = remoting.Envelope()

        # Test a non existant service call
        request = remoting.Request('nope', envelope=envelope)
        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertTrue(isinstance(response, remoting.Message))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, remoting.ErrorFault))

        self.assertEqual(response.body.code, 'Service.ResourceNotFound')
        self.assertEqual(response.body.description, 'Unknown service nope')
        self.assertNotEquals(response.body.details, None)

    def test_malformed_credentials_header(self):
        gw = gateway.BaseGateway({'test': TestService})
        envelope = remoting.Envelope()

        request = remoting.Request('test.spam', envelope=envelope)
        request.headers['Credentials'] = {'spam': 'eggs'}

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(response.body, remoting.ErrorFault))

        self.assertEqual(response.body.code, 'KeyError')

    def test_authenticate(self):
        gw = gateway.BaseGateway({'test': TestService})
        sr = gateway.ServiceRequest(None, gw.services['test'], None)

        self.assertTrue(gw.authenticateRequest(sr, None, None))

        def auth(u, p):
            if u == 'spam' and p == 'eggs':
                return True

            return False

        gw = gateway.BaseGateway({'test': TestService}, authenticator=auth)

        self.assertFalse(gw.authenticateRequest(sr, None, None))
        self.assertTrue(gw.authenticateRequest(sr, 'spam', 'eggs'))

    def test_null_target(self):
        gw = gateway.BaseGateway({})

        request = remoting.Request(None)
        processor = gw.getProcessor(request)

        from pyamf.remoting import amf3

        self.assertTrue(isinstance(processor, amf3.RequestProcessor))

    def test_empty_target(self):
        gw = gateway.BaseGateway({})

        request = remoting.Request('')
        processor = gw.getProcessor(request)

        from pyamf.remoting import amf3

        self.assertTrue(isinstance(processor, amf3.RequestProcessor))


class QueryBrowserTestCase(unittest.TestCase):
    def test_request(self):
        gw = gateway.BaseGateway()
        echo = lambda x: x

        gw.addService(echo, 'echo', description='This is a test')

        envelope = remoting.Envelope()
        request = remoting.Request('echo')
        envelope['/1'] = request

        request.headers['DescribeService'] = None

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'This is a test')


class AuthenticatorTestCase(unittest.TestCase):
    def setUp(self):
        self.called = False

    def tearDown(self):
        if self.called is False:
            self.fail("authenticator not called")

    def _auth(self, username, password):
        self.called = True

        if username == 'fred' and password == 'wilma':
            return True

        return False

    def test_gateway(self):
        gw = gateway.BaseGateway(authenticator=self._auth)
        echo = lambda x: x

        gw.addService(echo, 'echo')

        envelope = remoting.Envelope()
        request = remoting.Request('echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_service(self):
        gw = gateway.BaseGateway()
        echo = lambda x: x

        gw.addService(echo, 'echo', authenticator=self._auth)

        envelope = remoting.Envelope()
        request = remoting.Request('echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_class_decorator(self):
        class TestService:
            def echo(self, x):
                return x

        TestService.echo = gateway.authenticate(TestService.echo, self._auth)

        gw = gateway.BaseGateway({'test': TestService})

        envelope = remoting.Envelope()
        request = remoting.Request('test.echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_func_decorator(self):
        def echo(x):
            return x

        echo = gateway.authenticate(echo, self._auth)

        gw = gateway.BaseGateway({'echo': echo})

        envelope = remoting.Envelope()
        request = remoting.Request('echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_expose_request_decorator(self):
        def echo(x):
            return x

        def exposed_auth(request, username, password):
            return self._auth(username, password)

        exposed_auth = gateway.expose_request(exposed_auth)

        echo = gateway.authenticate(echo, exposed_auth)
        gw = gateway.BaseGateway({'echo': echo})

        envelope = remoting.Envelope()
        request = remoting.Request('echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')

    def test_expose_request_keyword(self):
        def echo(x):
            return x

        def exposed_auth(request, username, password):
            return self._auth(username, password)

        echo = gateway.authenticate(echo, exposed_auth, expose_request=True)
        gw = gateway.BaseGateway({'echo': echo})

        envelope = remoting.Envelope()
        request = remoting.Request('echo', body=['spam'])
        envelope.headers['Credentials'] = dict(userid='fred', password='wilma')
        envelope['/1'] = request

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')


class ExposeRequestTestCase(unittest.TestCase):
    def test_default(self):
        gw = gateway.BaseGateway()

        gw.addService(lambda x: x, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertFalse(gw.mustExposeRequest(service_request))

    def test_gateway(self):
        gw = gateway.BaseGateway(expose_request=True)

        gw.addService(lambda x: x, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertTrue(gw.mustExposeRequest(service_request))

    def test_service(self):
        gw = gateway.BaseGateway()

        gw.addService(lambda x: x, 'test', expose_request=True)

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertTrue(gw.mustExposeRequest(service_request))

    def test_decorator(self):
        def echo(x):
            return x

        gateway.expose_request(echo)

        gw = gateway.BaseGateway()

        gw.addService(echo, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertTrue(gw.mustExposeRequest(service_request))


class PreProcessingTestCase(unittest.TestCase):
    def _preproc(self):
        pass

    def test_default(self):
        gw = gateway.BaseGateway()

        gw.addService(lambda x: x, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertEqual(gw.getPreprocessor(service_request), None)

    def test_global(self):
        gw = gateway.BaseGateway(preprocessor=self._preproc)

        gw.addService(lambda x: x, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertEqual(gw.getPreprocessor(service_request), self._preproc)

    def test_service(self):
        gw = gateway.BaseGateway()

        gw.addService(lambda x: x, 'test', preprocessor=self._preproc)

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertEqual(gw.getPreprocessor(service_request), self._preproc)

    def test_decorator(self):
        def echo(x):
            return x

        gateway.preprocess(echo, self._preproc)

        gw = gateway.BaseGateway()

        gw.addService(echo, 'test')

        envelope = remoting.Envelope()
        request = remoting.Request('test')
        envelope['/1'] = request

        service_request = gateway.ServiceRequest(envelope, gw.services['test'], None)

        self.assertEqual(gw.getPreprocessor(service_request), self._preproc)

    def test_call(self):
        def preproc(sr, *args):
            self.called = True

            self.assertEqual(args, tuple())
            self.assertTrue(isinstance(sr, gateway.ServiceRequest))

        gw = gateway.BaseGateway({'test': TestService}, preprocessor=preproc)
        envelope = remoting.Envelope()

        request = remoting.Request('test.spam', envelope=envelope)

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, 'spam')
        self.assertTrue(self.called)

    def test_fail(self):
        def preproc(sr, *args):
            raise IndexError

        gw = gateway.BaseGateway({'test': TestService}, preprocessor=preproc)
        envelope = remoting.Envelope()

        request = remoting.Request('test.spam', envelope=envelope)

        processor = gw.getProcessor(request)
        response = processor(request)

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
