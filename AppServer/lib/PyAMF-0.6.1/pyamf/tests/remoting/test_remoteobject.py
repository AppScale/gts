# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
RemoteObject Tests.

@since: 0.1
"""

import unittest

import pyamf
from pyamf import remoting
from pyamf.remoting import amf3, gateway
from pyamf.flex import messaging


class RandomIdGeneratorTestCase(unittest.TestCase):
    def test_generate(self):
        x = []

        for i in range(5):
            id_ = amf3.generate_random_id()

            self.assertTrue(id_ not in x)
            x.append(id_)


class AcknowlegdementGeneratorTestCase(unittest.TestCase):
    def test_generate(self):
        ack = amf3.generate_acknowledgement()

        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertTrue(ack.messageId is not None)
        self.assertTrue(ack.clientId is not None)
        self.assertTrue(ack.timestamp is not None)

    def test_request(self):
        ack = amf3.generate_acknowledgement(pyamf.ASObject(messageId='123123'))

        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertTrue(ack.messageId is not None)
        self.assertTrue(ack.clientId is not None)
        self.assertTrue(ack.timestamp is not None)

        self.assertEqual(ack.correlationId, '123123')


class RequestProcessorTestCase(unittest.TestCase):
    def test_create(self):
        rp = amf3.RequestProcessor('xyz')
        self.assertEqual(rp.gateway, 'xyz')

    def test_ping(self):
        message = messaging.CommandMessage(operation=5)
        rp = amf3.RequestProcessor(None)
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertEqual(ack.body, True)

    def test_request(self):
        def echo(x):
            return x

        gw = gateway.BaseGateway({'echo': echo})
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertEqual(ack.body, 'spam.eggs')

    def test_error(self):
        def echo(x):
            raise TypeError('foo')

        gw = gateway.BaseGateway({'echo': echo})
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertFalse(gw.debug)
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(ack, messaging.ErrorMessage))
        self.assertEqual(ack.faultCode, 'TypeError')
        self.assertEqual(ack.faultString, 'foo')

    def test_error_debug(self):
        def echo(x):
            raise TypeError('foo')

        gw = gateway.BaseGateway({'echo': echo}, debug=True)
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(gw.debug)
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(ack, messaging.ErrorMessage))
        self.assertEqual(ack.faultCode, 'TypeError')
        self.assertNotEquals(ack.extendedData, None)

    def test_too_many_args(self):
        def spam(bar):
            return bar

        gw = gateway.BaseGateway({'spam': spam})
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['eggs', 'baz'], operation='spam')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(ack, messaging.ErrorMessage))
        self.assertEqual(ack.faultCode, 'TypeError')

    def test_preprocess(self):
        def echo(x):
            return x

        self.called = False

        def preproc(sr, *args):
            self.called = True

            self.assertEqual(args, ('spam.eggs',))
            self.assertTrue(isinstance(sr, gateway.ServiceRequest))

        gw = gateway.BaseGateway({'echo': echo}, preprocessor=preproc)
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertEqual(ack.body, 'spam.eggs')
        self.assertTrue(self.called)

    def test_fail_preprocess(self):
        def preproc(sr, *args):
            raise IndexError

        def echo(x):
            return x

        gw = gateway.BaseGateway({'echo': echo}, preprocessor=preproc)
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(ack, messaging.ErrorMessage))

    def test_destination(self):
        def echo(x):
            return x

        gw = gateway.BaseGateway({'spam.eggs': echo})
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=[None], destination='spam', operation='eggs')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))
        self.assertEqual(ack.body, None)

    def test_disconnect(self):
        message = messaging.CommandMessage(operation=12)
        rp = amf3.RequestProcessor(None)
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))

    def test_async(self):
        message = messaging.AsyncMessage()
        rp = amf3.RequestProcessor(None)
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_OK)
        self.assertTrue(isinstance(ack, messaging.AcknowledgeMessage))

    def test_error_unicode_message(self):
        """
        See #727
        """
        def echo(x):
            raise TypeError(u'ƒøø')

        gw = gateway.BaseGateway({'echo': echo})
        rp = amf3.RequestProcessor(gw)
        message = messaging.RemotingMessage(body=['spam.eggs'], operation='echo')
        request = remoting.Request('null', body=[message])

        response = rp(request)
        ack = response.body

        self.assertFalse(gw.debug)
        self.assertTrue(isinstance(response, remoting.Response))
        self.assertEqual(response.status, remoting.STATUS_ERROR)
        self.assertTrue(isinstance(ack, messaging.ErrorMessage))
        self.assertEqual(ack.faultCode, 'TypeError')
        self.assertEqual(ack.faultString, u'ƒøø')
