# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Django gateway tests.

@since: 0.1.0
"""

import unittest
import sys
import os

try:
    from django import http
    from pyamf.remoting.gateway import django
except ImportError:
    django = None

import pyamf
from pyamf import remoting, util


class BaseTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        if not django:
            self.skipTest("'django' not available")


class DjangoGatewayTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        import new

        self.mod_name = '%s.%s' % (__name__, 'settings')
        sys.modules[self.mod_name] = new.module(self.mod_name)

        self.old_env = os.environ.get('DJANGO_SETTINGS_MODULE', None)

        os.environ['DJANGO_SETTINGS_MODULE'] = self.mod_name

    def tearDown(self):
        if self.old_env is not None:
            os.environ['DJANGO_SETTINGS_MODULE'] = self.old_env

        del sys.modules[self.mod_name]

    def test_csrf(self):
        gw = django.DjangoGateway()

        self.assertTrue(gw.csrf_exempt)

    def test_settings(self):
        from django import conf

        settings_mod = sys.modules[self.mod_name]

        settings_mod.DEBUG = True
        settings_mod.AMF_TIME_OFFSET = 1000

        old_settings = conf.settings
        conf.settings = conf.Settings(self.mod_name)

        gw = django.DjangoGateway()

        try:
            self.assertTrue(gw.debug)
            self.assertEqual(gw.timezone_offset, 1000)
        finally:
            conf.settings = old_settings

    def test_request_method(self):
        gw = django.DjangoGateway()

        http_request = http.HttpRequest()
        http_request.method = 'GET'

        http_response = gw(http_request)
        self.assertEqual(http_response.status_code, 405)

    def test_bad_request(self):
        gw = django.DjangoGateway()

        request = util.BufferedByteStream()
        request.write('Bad request')
        request.seek(0, 0)

        http_request = http.HttpRequest()
        http_request.method = 'POST'
        http_request.raw_post_data = request.getvalue()

        http_response = gw(http_request)
        self.assertEqual(http_response.status_code, 400)

    def test_unknown_request(self):
        gw = django.DjangoGateway()

        request = util.BufferedByteStream()
        request.write('\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00'
            '\x02/1\x00\x00\x00\x14\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x00'
            '\x00\x01\x61\x02\x00\x01\x61\x00\x00\x09')
        request.seek(0, 0)

        http_request = http.HttpRequest()
        http_request.method = 'POST'
        http_request.raw_post_data = request.getvalue()

        http_response = gw(http_request)
        envelope = remoting.decode(http_response.content)

        message = envelope['/1']

        self.assertEqual(message.status, remoting.STATUS_ERROR)
        body = message.body

        self.assertTrue(isinstance(body, remoting.ErrorFault))
        self.assertEqual(body.code, 'Service.ResourceNotFound')

    def test_expose_request(self):
        http_request = http.HttpRequest()
        self.executed = False

        def test(request):
            self.assertEqual(http_request, request)
            self.assertTrue(hasattr(request, 'amf_request'))
            self.executed = True

        gw = django.DjangoGateway({'test.test': test}, expose_request=True)

        request = util.BufferedByteStream()
        request.write('\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00'
            '\x02/1\x00\x00\x00\x05\x0a\x00\x00\x00\x00')
        request.seek(0, 0)

        http_request.method = 'POST'
        http_request.raw_post_data = request.getvalue()

        gw(http_request)

        self.assertTrue(self.executed)

    def _raiseException(self, e, *args, **kwargs):
        raise e()

    def test_really_bad_decode(self):
        self.old_method = remoting.decode
        remoting.decode = lambda *args, **kwargs: self._raiseException(Exception, *args, **kwargs)

        http_request = http.HttpRequest()
        http_request.method = 'POST'
        http_request.raw_post_data = ''

        gw = django.DjangoGateway()

        try:
            http_response = gw(http_request)
        except:
            remoting.decode = self.old_method

            raise

        remoting.decode = self.old_method

        self.assertTrue(isinstance(http_response, http.HttpResponseServerError))
        self.assertEqual(http_response.status_code, 500)
        self.assertEqual(http_response.content, '500 Internal Server Error\n\nAn unexpected error occurred.')

    def test_expected_exceptions_decode(self):
        self.old_method = remoting.decode

        gw = django.DjangoGateway()

        http_request = http.HttpRequest()
        http_request.method = 'POST'
        http_request.raw_post_data = ''

        try:
            for x in (KeyboardInterrupt, SystemExit):
                remoting.decode = lambda *args, **kwargs: self._raiseException(x, *args, **kwargs)
                self.assertRaises(x, gw, http_request)
        except:
            remoting.decode = self.old_method

            raise

        remoting.decode = self.old_method

    def test_timezone(self):
        import datetime

        http_request = http.HttpRequest()
        self.executed = False

        td = datetime.timedelta(hours=-5)
        now = datetime.datetime.utcnow()

        def echo(d):
            self.assertEqual(d, now + td)
            self.executed = True

            return d

        gw = django.DjangoGateway({'test.test': echo}, timezone_offset=-18000,
            expose_request=False)

        msg = remoting.Envelope(amfVersion=pyamf.AMF0)
        msg['/1'] = remoting.Request(target='test.test', body=[now])

        http_request.method = 'POST'
        http_request.raw_post_data = remoting.encode(msg).getvalue()

        res = remoting.decode(gw(http_request).content)
        self.assertTrue(self.executed)

        self.assertEqual(res['/1'].body, now)
