# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
WSGI gateway tests.

@since: 0.1.0
"""

import unittest

import pyamf
from pyamf import remoting, util
from pyamf.remoting.gateway.wsgi import WSGIGateway


class WSGIServerTestCase(unittest.TestCase):
    def setUp(self):
        self.gw = WSGIGateway()
        self.executed = False

    def doRequest(self, request, start_response, **kwargs):
        kwargs.setdefault('REQUEST_METHOD', 'POST')
        kwargs.setdefault('CONTENT_LENGTH', str(len(request)))

        kwargs['wsgi.input'] = request

        def sr(status, headers):
            r = None

            if start_response:
                r = start_response(status, headers)

            self.executed = True

            return r

        return self.gw(kwargs, sr)

    def makeRequest(self, service, body, raw=False):
        if not raw:
            body = [body]

        e = remoting.Envelope(pyamf.AMF3)
        e['/1'] = remoting.Request(service, body=body)

        return remoting.encode(e)

    def test_request_method(self):
        def bad_response(status, headers):
            self.assertEqual(status, '400 Bad Request')
            self.executed = True

        self.gw({'REQUEST_METHOD': 'GET'}, bad_response)
        self.assertTrue(self.executed)

        self.assertRaises(KeyError, self.gw, {'REQUEST_METHOD': 'POST'},
            lambda *args: None)

    def test_bad_request(self):
        request = util.BufferedByteStream()
        request.write('Bad request')
        request.seek(0, 0)

        def start_response(status, headers):
            self.assertEqual(status, '400 Bad Request')

        self.doRequest(request, start_response)
        self.assertTrue(self.executed)

    def test_unknown_request(self):
        request = self.makeRequest('test.test', [], raw=True)

        def start_response(status, headers):
            self.executed = True
            self.assertEqual(status, '200 OK')
            self.assertTrue(('Content-Type', 'application/x-amf') in headers)

        response = self.doRequest(request, start_response)

        envelope = remoting.decode(''.join(response))

        message = envelope['/1']

        self.assertEqual(message.status, remoting.STATUS_ERROR)
        body = message.body

        self.assertTrue(isinstance(body, remoting.ErrorFault))
        self.assertEqual(body.code, 'Service.ResourceNotFound')
        self.assertTrue(self.executed)

    def test_eof_decode(self):
        request = util.BufferedByteStream()

        def start_response(status, headers):
            self.assertEqual(status, '400 Bad Request')
            self.assertTrue(('Content-Type', 'text/plain') in headers)

        response = self.doRequest(request, start_response)

        self.assertEqual(response, ['400 Bad Request\n\nThe request body was unable to be successfully decoded.'])
        self.assertTrue(self.executed)

    def _raiseException(self, e, *args, **kwargs):
        raise e()

    def _restoreDecode(self):
        remoting.decode = self.old_method

    def test_really_bad_decode(self):
        self.old_method = remoting.decode
        remoting.decode = lambda *args, **kwargs: self._raiseException(Exception, *args, **kwargs)
        self.addCleanup(self._restoreDecode)

        request = util.BufferedByteStream()

        def start_response(status, headers):
            self.assertEqual(status, '500 Internal Server Error')
            self.assertTrue(('Content-Type', 'text/plain') in headers)

        response = self.doRequest(request, start_response)

        self.assertEqual(response, ['500 Internal Server Error\n\nAn unexpec'
            'ted error occurred whilst decoding.'])
        self.assertTrue(self.executed)

    def test_expected_exceptions_decode(self):
        self.old_method = remoting.decode
        self.addCleanup(self._restoreDecode)
        request = util.BufferedByteStream()

        for x in (KeyboardInterrupt, SystemExit):
            remoting.decode = lambda *args, **kwargs: self._raiseException(x, *args, **kwargs)

            self.assertRaises(x, self.doRequest, request, None)

    def test_expose_request(self):
        self.gw.expose_request = True

        def echo(http_request, data):
            self.assertTrue('pyamf.request' in http_request)
            request = http_request['pyamf.request']

            self.assertTrue(isinstance(request, remoting.Request))

            self.assertEqual(request.target, 'echo')
            self.assertEqual(request.body, ['hello'])

        self.gw.addService(echo)
        self.doRequest(self.makeRequest('echo', 'hello'), None)

        self.assertTrue(self.executed)

    def test_timezone(self):
        import datetime

        td = datetime.timedelta(hours=-5)
        now = datetime.datetime.utcnow()

        def echo(d):
            self.assertEqual(d, now + td)

            return d

        self.gw.addService(echo)
        self.gw.timezone_offset = -18000

        response = self.doRequest(self.makeRequest('echo', now), None)
        envelope = remoting.decode(''.join(response))
        message = envelope['/1']

        self.assertEqual(message.body, now)
