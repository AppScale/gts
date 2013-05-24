# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Google Web App gateway tests.

@since: 0.3.1
"""

import unittest
import os

from StringIO import StringIO

try:
    from google.appengine.ext import webapp
    from pyamf.remoting.gateway import google as google
except ImportError:
    webapp = None

if os.environ.get('SERVER_SOFTWARE', None) is None:
    # we're not being run in appengine environment (at one that we are known to
    # work in)
    webapp = None


import pyamf
from pyamf import remoting


class BaseTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        if not webapp:
            self.skipTest("'google' is not available")


class WebAppGatewayTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        self.gw = google.WebAppGateway()

        self.environ = {
            'wsgi.input': StringIO(),
            'wsgi.output': StringIO()
        }

        self.request = webapp.Request(self.environ)
        self.response = webapp.Response()

        self.gw.initialize(self.request, self.response)

    def test_get(self):
        self.gw.get()

        self.assertEqual(self.response.__dict__['_Response__status'][0], 405)

    def test_bad_request(self):
        self.environ['wsgi.input'].write('Bad request')
        self.environ['wsgi.input'].seek(0, 0)

        self.gw.post()
        self.assertEqual(self.response.__dict__['_Response__status'][0], 400)

    def test_unknown_request(self):
        self.environ['wsgi.input'].write(
            '\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00\x02/1\x00\x00\x00'
            '\x14\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x00\x00\x01\x61\x02\x00'
            '\x01\x61\x00\x00\x09')
        self.environ['wsgi.input'].seek(0, 0)

        self.gw.post()

        self.assertEqual(self.response.__dict__['_Response__status'][0], 200)

        envelope = remoting.decode(self.response.out.getvalue())
        message = envelope['/1']

        self.assertEqual(message.status, remoting.STATUS_ERROR)
        body = message.body

        self.assertTrue(isinstance(body, remoting.ErrorFault))
        self.assertEqual(body.code, 'Service.ResourceNotFound')

    def test_expose_request(self):
        self.executed = False

        def test(request):
            self.assertEqual(self.request, request)
            self.assertTrue(hasattr(self.request, 'amf_request'))

            self.executed = True

        self.gw.expose_request = True
        self.gw.addService(test, 'test.test')

        self.environ['wsgi.input'].write('\x00\x00\x00\x00\x00\x01\x00\x09'
            'test.test\x00\x02/1\x00\x00\x00\x05\x0a\x00\x00\x00\x00')
        self.environ['wsgi.input'].seek(0, 0)

        self.gw.post()

        self.assertTrue(self.executed)

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

        msg = remoting.Envelope(amfVersion=pyamf.AMF0)
        msg['/1'] = remoting.Request(target='echo', body=[now])

        stream = remoting.encode(msg)
        self.environ['wsgi.input'] = stream
        self.gw.post()

        envelope = remoting.decode(self.response.out.getvalue())
        message = envelope['/1']

        self.assertEqual(message.body, now)
        self.assertTrue(self.executed)
