# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for Remoting client.

@since: 0.1.0
"""

import unittest
import urllib2

import pyamf
from pyamf import remoting, util
from pyamf.remoting import client


class ServiceMethodProxyTestCase(unittest.TestCase):
    def test_create(self):
        x = client.ServiceMethodProxy('a', 'b')

        self.assertEqual(x.service, 'a')
        self.assertEqual(x.name, 'b')

    def test_call(self):
        tc = self

        class TestService(object):
            def __init__(self, s, args):
                self.service = s
                self.args = args

            def _call(self, service, *args):
                tc.assertTrue(self.service, service)
                tc.assertTrue(self.args, args)

        x = client.ServiceMethodProxy(None, None)
        ts = TestService(x, [1, 2, 3])
        x.service = ts

        x(1, 2, 3)

    def test_str(self):
        x = client.ServiceMethodProxy('spam', 'eggs')
        self.assertEqual(str(x), 'spam.eggs')

        x = client.ServiceMethodProxy('spam', None)
        self.assertEqual(str(x), 'spam')


class ServiceProxyTestCase(unittest.TestCase):
    def test_create(self):
        x = client.ServiceProxy('spam', 'eggs')

        self.assertEqual(x._gw, 'spam')
        self.assertEqual(x._name, 'eggs')
        self.assertEqual(x._auto_execute, True)

        x = client.ServiceProxy('hello', 'world', True)

        self.assertEqual(x._gw, 'hello')
        self.assertEqual(x._name, 'world')
        self.assertEqual(x._auto_execute, True)

        x = client.ServiceProxy(ord, chr, False)

        self.assertEqual(x._gw, ord)
        self.assertEqual(x._name, chr)
        self.assertEqual(x._auto_execute, False)

    def test_getattr(self):
        x = client.ServiceProxy(None, None)
        y = x.spam

        self.assertTrue(isinstance(y, client.ServiceMethodProxy))
        self.assertEqual(y.name, 'spam')

    def test_call(self):
        class DummyGateway(object):
            def __init__(self, tc):
                self.tc = tc

            def addRequest(self, method_proxy, *args):
                self.tc.assertEqual(method_proxy, self.method_proxy)
                self.tc.assertEqual(args, self.args)

                self.request = {'method_proxy': method_proxy, 'args': args}
                return self.request

            def execute_single(self, request):
                self.tc.assertEqual(request, self.request)

                return pyamf.ASObject(body=None, status=None)

        gw = DummyGateway(self)
        x = client.ServiceProxy(gw, 'test')
        y = x.spam

        gw.method_proxy = y
        gw.args = ()

        y()
        gw.args = (1, 2, 3)

        y(1, 2, 3)

    def test_service_call(self):
        class DummyGateway(object):
            def __init__(self, tc):
                self.tc = tc

            def addRequest(self, method_proxy, *args):
                self.tc.assertEqual(method_proxy.service, self.x)
                self.tc.assertEqual(method_proxy.name, None)

                return pyamf.ASObject(method_proxy=method_proxy, args=args)

            def execute_single(self, request):
                return pyamf.ASObject(body=None, status=None)

        gw = DummyGateway(self)
        x = client.ServiceProxy(gw, 'test')
        gw.x = x

        x()

    def test_pending_call(self):
        class DummyGateway(object):
            def __init__(self, tc):
                self.tc = tc

            def addRequest(self, method_proxy, *args):
                self.tc.assertEqual(method_proxy, self.method_proxy)
                self.tc.assertEqual(args, self.args)

                self.request = pyamf.ASObject(method_proxy=method_proxy, args=args)

                return self.request

        gw = DummyGateway(self)
        x = client.ServiceProxy(gw, 'test', False)
        y = x.eggs

        gw.method_proxy = y
        gw.args = ()

        res = y()

        self.assertEqual(id(gw.request), id(res))

    def test_str(self):
        x = client.ServiceProxy(None, 'test')

        self.assertEqual(str(x), 'test')

    def test_error(self):
        class DummyGateway(object):
            def __init__(self, tc):
                self.tc = tc

            def addRequest(self, method_proxy, *args):
                self.request = pyamf.ASObject(method_proxy=method_proxy, args=args)

                return self.request

            def execute_single(self, request):
                body = remoting.ErrorFault(code='TypeError', description='foobar')

                return remoting.Response(status=remoting.STATUS_ERROR, body=body)

        gw = DummyGateway(self)

        proxy = client.ServiceProxy(gw, 'test')

        self.assertRaises(TypeError, proxy)


class RequestWrapperTestCase(unittest.TestCase):
    def test_create(self):
        x = client.RequestWrapper(1, 2, 3, 4)

        self.assertEqual(x.gw, 1)
        self.assertEqual(x.id, 2)
        self.assertEqual(x.service, 3)
        self.assertEqual(x.args, (4,))

    def test_str(self):
        x = client.RequestWrapper(None, '/1', None, None)

        self.assertEqual(str(x), '/1')

    def test_null_response(self):
        x = client.RequestWrapper(None, None, None, None)

        self.assertRaises(AttributeError, getattr, x, 'result')

    def test_set_response(self):
        x = client.RequestWrapper(None, None, None, None)

        y = pyamf.ASObject(body='spam.eggs')

        x.setResponse(y)

        self.assertEqual(x.response, y)
        self.assertEqual(x.result, 'spam.eggs')


class MockOpener(object):
    """
    opener for urllib2.install_opener
    """

    def __init__(self, test, response=None):
        self.test = test
        self.response = response

    def open(self, request, data=None, timeout=None):
        if self.response.code != 200:
            raise urllib2.URLError(self.response.code)

        self.request = request
        self.data = data

        return self.response


class MockHeaderCollection(object):

    def __init__(self, headers):
        self.headers = headers

    def getheader(self, name):
        return self.headers.get(name, None)

    def __repr__(self):
        return repr(self.headers)


class MockResponse(object):
    """
    """

    headers = None
    body = None

    def info(self):
        return MockHeaderCollection(self.headers)

    def read(self, amount):
        return self.body[0:amount]


class BaseServiceTestCase(unittest.TestCase):
    """
    """

    canned_response = ('\x00\x00\x00\x00\x00\x01\x00\x0b/1/onResult\x00'
        '\x04null\x00\x00\x00\x00\n\x00\x00\x00\x03\x00?\xf0\x00\x00'
        '\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00@\x08\x00'
        '\x00\x00\x00\x00\x00')

    headers = {
        'Content-Type': 'application/x-amf',
    }

    def setUp(self):
        unittest.TestCase.setUp(self)

        self.response = MockResponse()
        self.opener = MockOpener(self, self.response)

        self.gw = client.RemotingService('http://example.org/amf-gateway', opener=self.opener.open)

        self.headers = self.__class__.headers.copy()
        self.headers['Content-Length'] = len(self.canned_response)

        self.setResponse(200, self.canned_response, self.headers)

    def setResponse(self, status, body, headers=None):
        self.response.code = status
        self.response.body = body
        self.response.headers = headers or {
            'Content-Type': remoting.CONTENT_TYPE
        }


class RemotingServiceTestCase(BaseServiceTestCase):
    """
    """

    def test_create(self):
        self.assertRaises(TypeError, client.RemotingService)
        x = client.RemotingService('http://example.org')

        self.assertEqual(x.url, ('http', 'example.org', '', '', '', ''))

        # amf version
        x = client.RemotingService('http://example.org', pyamf.AMF3)
        self.assertEqual(x.amf_version, pyamf.AMF3)

    def test_schemes(self):
        x = client.RemotingService('http://example.org')
        self.assertEqual(x.url, ('http', 'example.org', '', '', '', ''))

        x = client.RemotingService('https://example.org')
        self.assertEqual(x.url, ('https', 'example.org', '', '', '', ''))

        self.assertRaises(ValueError, client.RemotingService,
            'ftp://example.org')

    def test_port(self):
        x = client.RemotingService('http://example.org:8080')

        self.assertEqual(x.url, ('http', 'example.org:8080', '', '', '', ''))

    def test_get_service(self):
        x = client.RemotingService('http://example.org')

        y = x.getService('spam')

        self.assertTrue(isinstance(y, client.ServiceProxy))
        self.assertEqual(y._name, 'spam')
        self.assertEqual(y._gw, x)

        self.assertRaises(TypeError, x.getService, 1)

    def test_add_request(self):
        gw = client.RemotingService('http://spameggs.net')

        self.assertEqual(gw.request_number, 1)
        self.assertEqual(gw.requests, [])
        service = gw.getService('baz')
        wrapper = gw.addRequest(service, 1, 2, 3)

        self.assertEqual(gw.requests, [wrapper])
        self.assertEqual(wrapper.gw, gw)
        self.assertEqual(gw.request_number, 2)
        self.assertEqual(wrapper.id, '/1')
        self.assertEqual(wrapper.service, service)
        self.assertEqual(wrapper.args, (1, 2, 3))

        # add 1 arg
        wrapper2 = gw.addRequest(service, None)

        self.assertEqual(gw.requests, [wrapper, wrapper2])
        self.assertEqual(wrapper2.gw, gw)
        self.assertEqual(gw.request_number, 3)
        self.assertEqual(wrapper2.id, '/2')
        self.assertEqual(wrapper2.service, service)
        self.assertEqual(wrapper2.args, (None,))

        # add no args
        wrapper3 = gw.addRequest(service)

        self.assertEqual(gw.requests, [wrapper, wrapper2, wrapper3])
        self.assertEqual(wrapper3.gw, gw)
        self.assertEqual(gw.request_number, 4)
        self.assertEqual(wrapper3.id, '/3')
        self.assertEqual(wrapper3.service, service)
        self.assertEqual(wrapper3.args, tuple())

    def test_remove_request(self):
        gw = client.RemotingService('http://spameggs.net')
        self.assertEqual(gw.requests, [])

        service = gw.getService('baz')
        wrapper = gw.addRequest(service, 1, 2, 3)
        self.assertEqual(gw.requests, [wrapper])

        gw.removeRequest(wrapper)
        self.assertEqual(gw.requests, [])

        wrapper = gw.addRequest(service, 1, 2, 3)
        self.assertEqual(gw.requests, [wrapper])

        gw.removeRequest(service, 1, 2, 3)
        self.assertEqual(gw.requests, [])

        self.assertRaises(LookupError, gw.removeRequest, service, 1, 2, 3)

    def test_get_request(self):
        gw = client.RemotingService('http://spameggs.net')

        service = gw.getService('baz')
        wrapper = gw.addRequest(service, 1, 2, 3)

        wrapper2 = gw.getRequest(str(wrapper))
        self.assertEqual(wrapper, wrapper2)

        wrapper2 = gw.getRequest('/1')
        self.assertEqual(wrapper, wrapper2)

        wrapper2 = gw.getRequest(wrapper.id)
        self.assertEqual(wrapper, wrapper2)

    def test_get_amf_request(self):
        gw = client.RemotingService('http://example.org', pyamf.AMF3)

        service = gw.getService('baz')
        method_proxy = service.gak
        wrapper = gw.addRequest(method_proxy, 1, 2, 3)

        envelope = gw.getAMFRequest([wrapper])

        self.assertEqual(envelope.amfVersion, pyamf.AMF3)
        self.assertEqual(envelope.keys(), ['/1'])

        request = envelope['/1']
        self.assertEqual(request.target, 'baz.gak')
        self.assertEqual(request.body, [1, 2, 3])

        envelope2 = gw.getAMFRequest(gw.requests)

        self.assertEqual(envelope2.amfVersion, pyamf.AMF3)
        self.assertEqual(envelope2.keys(), ['/1'])

        request = envelope2['/1']
        self.assertEqual(request.target, 'baz.gak')
        self.assertEqual(request.body, [1, 2, 3])

    def test_execute_single(self):
        service = self.gw.getService('baz', auto_execute=False)
        wrapper = service.gak()

        response = self.gw.execute_single(wrapper)
        self.assertEqual(self.gw.requests, [])

        r = self.opener.request

        self.assertEqual(r.headers, {
            'Content-type': remoting.CONTENT_TYPE,
            'User-agent': client.DEFAULT_USER_AGENT
        })
        self.assertEqual(r.get_method(), 'POST')
        self.assertEqual(r.get_full_url(), 'http://example.org/amf-gateway')

        self.assertEqual(r.get_data(), '\x00\x00\x00\x00\x00\x01\x00\x07'
            'baz.gak\x00\x02/1\x00\x00\x00\x00\x0a\x00\x00\x00\x00')

        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertEqual(response.body, [1, 2, 3])

    def test_execute(self):
        baz = self.gw.getService('baz', auto_execute=False)
        spam = self.gw.getService('spam', auto_execute=False)
        wrapper = baz.gak()
        wrapper2 = spam.eggs()

        self.assertTrue(wrapper)
        self.assertTrue(wrapper2)

        response = self.gw.execute()
        self.assertTrue(response)
        self.assertEqual(self.gw.requests, [])

        r = self.opener.request

        self.assertEqual(r.headers, {
            'Content-type': remoting.CONTENT_TYPE,
            'User-agent': client.DEFAULT_USER_AGENT
        })
        self.assertEqual(r.get_method(), 'POST')
        self.assertEqual(r.get_full_url(), 'http://example.org/amf-gateway')

        self.assertEqual(r.get_data(), '\x00\x00\x00\x00\x00\x02\x00\x07'
            'baz.gak\x00\x02/1\x00\x00\x00\x00\n\x00\x00\x00\x00\x00\tspam.'
            'eggs\x00\x02/2\x00\x00\x00\x00\n\x00\x00\x00\x00')

    def test_get_response(self):
        self.setResponse(200, '\x00\x00\x00\x00\x00\x00\x00\x00')

        self.gw._getResponse(None)

        self.setResponse(404, '', {})

        self.assertRaises(remoting.RemotingError, self.gw._getResponse, None)

        # bad content type
        self.setResponse(200, '<html></html>', {'Content-Type': 'text/html'})

        self.assertRaises(remoting.RemotingError, self.gw._getResponse, None)

    def test_credentials(self):
        self.assertFalse('Credentials' in self.gw.headers)
        self.gw.setCredentials('spam', 'eggs')
        self.assertTrue('Credentials' in self.gw.headers)
        self.assertEqual(self.gw.headers['Credentials'],
            {'userid': u'spam', 'password': u'eggs'})

        envelope = self.gw.getAMFRequest([])
        self.assertTrue('Credentials' in envelope.headers)

        cred = envelope.headers['Credentials']

        self.assertEqual(cred, self.gw.headers['Credentials'])

    def test_append_url_header(self):
        self.setResponse(200, '\x00\x00\x00\x01\x00\x12AppendToGatewayUrl'
            '\x01\x00\x00\x00\x00\x02\x00\x05hello\x00\x00\x00\x00', {
            'Content-Type': 'application/x-amf'})

        response = self.gw._getResponse(None)
        self.assertTrue(response)

        self.assertEqual(self.gw.original_url,
            'http://example.org/amf-gatewayhello')

    def test_replace_url_header(self):
        self.setResponse(200, '\x00\x00\x00\x01\x00\x11ReplaceGatewayUrl\x01'
            '\x00\x00\x00\x00\x02\x00\x10http://spam.eggs\x00\x00\x00\x00',
            {'Content-Type': 'application/x-amf'})

        response = self.gw._getResponse(None)
        self.assertTrue(response)
        self.assertEqual(self.gw.original_url, 'http://spam.eggs')

    def test_add_http_header(self):
        self.assertEqual(self.gw.http_headers, {})

        self.gw.addHTTPHeader('ETag', '29083457239804752309485')

        self.assertEqual(self.gw.http_headers, {
            'ETag': '29083457239804752309485'
        })

    def test_remove_http_header(self):
        self.gw.http_headers = {
            'Set-Cookie': 'foo-bar'
        }

        self.gw.removeHTTPHeader('Set-Cookie')

        self.assertEqual(self.gw.http_headers, {})
        self.assertRaises(KeyError, self.gw.removeHTTPHeader, 'foo-bar')

    def test_http_request_headers(self):
        self.gw.addHTTPHeader('ETag', '29083457239804752309485')

        expected_headers = {
            'Etag': '29083457239804752309485',
            'Content-type': 'application/x-amf',
            'User-agent': self.gw.user_agent
        }

        self.setResponse(200, '\x00\x00\x00\x01\x00\x11ReplaceGatewayUrl'
            '\x01\x00\x00\x00\x00\x02\x00\x10http://spam.eggs\x00\x00\x00\x00')

        self.gw.execute()

        request = self.opener.request

        self.assertEqual(expected_headers, request.headers)

    def test_empty_content_length(self):
        self.setResponse(200, '\x00\x00\x00\x01\x00\x11ReplaceGatewayUrl\x01'
            '\x00\x00\x00\x00\x02\x00\x10http://spam.eggs\x00\x00\x00\x00', {
            'Content-Type': 'application/x-amf',
            'Content-Length': ''
        })

        response = self.gw._getResponse(None)
        self.assertTrue(response)

    def test_bad_content_length(self):
        # test a really borked content-length header
        self.setResponse(200, self.canned_response, {
            'Content-Type': 'application/x-amf',
            'Content-Length': 'asdfasdf'
        })

        self.assertRaises(ValueError, self.gw._getResponse, None)


class GZipTestCase(BaseServiceTestCase):
    """
    Tests for gzipping responses
    """

    def setUp(self):
        import gzip

        env = remoting.Envelope(pyamf.AMF3)
        r = remoting.Response(['foo' * 50000] * 200)

        env['/1'] = r

        response = remoting.encode(env).getvalue()

        buf = util.BufferedByteStream()
        x = gzip.GzipFile(fileobj=buf, mode='wb')

        x.write(response)

        x.close()

        self.canned_response = buf.getvalue()

        BaseServiceTestCase.setUp(self)

        self.headers['Content-Encoding'] = 'gzip'

    def test_good_response(self):
        self.gw._getResponse(None)

    def test_bad_response(self):
        self.headers['Content-Length'] = len('foobar')
        self.setResponse(200, 'foobar', self.headers)

        self.assertRaises(IOError, self.gw._getResponse, None)
