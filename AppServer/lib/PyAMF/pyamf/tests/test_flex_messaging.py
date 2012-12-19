# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Flex Messaging compatibility tests.

@since: 0.3.2
"""

import unittest
import datetime
import uuid

import pyamf
from pyamf.flex import messaging


class AbstractMessageTestCase(unittest.TestCase):
    def test_repr(self):
        a = messaging.AbstractMessage()

        a.body = u'é,è'

        try:
            repr(a)
        except:
            raise


class EncodingTestCase(unittest.TestCase):
    """
    Encoding tests for L{messaging}
    """

    def test_AcknowledgeMessage(self):
        m = messaging.AcknowledgeMessage()
        m.correlationId = '1234'

        self.assertEqual(pyamf.encode(m).getvalue(),
            '\n\x81\x0bUflex.messaging.messages.AcknowledgeMessage\tbody'
            '\x11clientId\x17destination\x0fheaders\x13messageId\x13timestamp'
            '\x15timeToLive\x1bcorrelationId\x01\x01\x01\n\x0b\x01\x01\x01\x01'
            '\x01\x06\t1234\x01')

    def test_CommandMessage(self):
        m = messaging.CommandMessage(operation='foo.bar')

        self.assertEqual(pyamf.encode(m).getvalue(),
            '\n\x81\x1bMflex.messaging.messages.CommandMessage\x1bcorrelationId'
            '\tbody\x11clientId\x17destination\x0fheaders\x13messageId\x13'
            'timestamp\x15timeToLive\x13operation\x01\x01\x01\x01\n\x0b\x01\x01'
            '\x01\x01\x01\x06\x0ffoo.bar\x01')

    def test_ErrorMessage(self):
        m = messaging.ErrorMessage(faultString='ValueError')

        self.assertEqual(pyamf.encode(m).getvalue(),
            '\n\x81[Iflex.messaging.messages.ErrorMessage\x1bcorrelationId\x15'
            'timeToLive\x13timestamp\x13messageId\x0fheaders\x17destination'
            '\x11clientId\tbody\x19extendedData\x13faultCode\x17faultDetail'
            '\x17faultString\x13rootCause\x01\x01\x01\x01\n\x0b\x01\x01\x01'
            '\x01\x01\n\x05\x01\x01\x01\x06\x15ValueError\n\x05\x01\x01')

    def test_RemotingMessage(self):
        m = messaging.RemotingMessage(source='foo.bar')

        self.assertEqual(pyamf.encode(m).getvalue(),
            '\n\x81\x1bOflex.messaging.messages.RemotingMessage\x15timeToLive'
            '\x13timestamp\x13messageId\x0fheaders\x17destination\x11clientId'
            '\tbody\x13operation\rsource\x01\x01\x01\n\x0b\x01\x01\x01\x01\x01'
            '\x01\x06\x0ffoo.bar\x01')


class SmallMessageTestCase(unittest.TestCase):
    """
    Tests for L{messaging.SmallMessageMixIn}
    """

    def setUp(self):
        self.decoder = pyamf.get_decoder(pyamf.AMF3)
        self.buffer = self.decoder.stream

    def test_acknowledge(self):
        bytes = ('\n\x07\x07DSK\xa8\x03\n\x0b\x01%DSMessagingVersion\x05?\xf0'
            '\x00\x00\x00\x00\x00\x00\tDSId\x06IEE0D161D-C11D-25CB-8DBE-3B77B'
            '54B55D9\x01\x05Br3&m\x85\x10\x00\x0c!\xee\r\x16\x1d\xc1(&[\xc9'
            '\x80RK\x9bE\xc6\xc4\x0c!\xee\r\x16\x1d\xc1=\x8e\xa3\xe0\x10\xef'
            '\xad;\xe5\xc5j\x02\x0c!S\x84\x83\xdb\xa9\xc8\xcaM`\x952f\xdbQ'
            '\xc9<\x00')
        self.buffer.write(bytes)
        self.buffer.seek(0)

        msg = self.decoder.readElement()

        self.assertTrue(isinstance(msg, messaging.AcknowledgeMessageExt))
        self.assertEqual(msg.body, None)
        self.assertEqual(msg.destination, None)
        self.assertEqual(msg.timeToLive, None)

        self.assertEqual(msg.timestamp, datetime.datetime(2009, 8, 19, 11, 24, 43, 985000))
        self.assertEqual(msg.headers, {
            'DSMessagingVersion': 1.0,
            'DSId': u'EE0D161D-C11D-25CB-8DBE-3B77B54B55D9'
        })
        self.assertEqual(msg.clientId, uuid.UUID('ee0d161d-c128-265b-c980-524b9b45c6c4'))
        self.assertEqual(msg.messageId, uuid.UUID('ee0d161d-c13d-8ea3-e010-efad3be5c56a'))
        self.assertEqual(msg.correlationId, uuid.UUID('538483db-a9c8-ca4d-6095-3266db51c93c'))
        self.assertEqual(self.buffer.remaining(), 0)

        # now encode the msg to check that encoding is byte for byte the same
        buffer = pyamf.encode(msg, encoding=pyamf.AMF3).getvalue()

        self.assertEqual(buffer, bytes)

    def test_command(self):
        bytes = ('\n\x07\x07DSC\x88\x02\n\x0b\x01\tDSId\x06IEE0D161D-C11D-'
            '25CB-8DBE-3B77B54B55D9\x01\x0c!\xc0\xdf\xb7|\xd6\xee$1s\x152f'
            '\xe11\xa8f\x01\x06\x01\x01\x04\x02')

        self.buffer.write(bytes)
        self.buffer.seek(0)

        msg = self.decoder.readElement()

        self.assertTrue(isinstance(msg, messaging.CommandMessageExt))
        self.assertEqual(msg.body, None)
        self.assertEqual(msg.destination, None)
        self.assertEqual(msg.timeToLive, None)

        self.assertEqual(msg.timestamp, None)
        self.assertEqual(msg.headers, {
            'DSId': u'EE0D161D-C11D-25CB-8DBE-3B77B54B55D9'
        })
        self.assertEqual(msg.clientId, None)
        self.assertEqual(msg.messageId, uuid.UUID('c0dfb77c-d6ee-2431-7315-3266e131a866'))
        self.assertEqual(msg.correlationId, u'')
        self.assertEqual(self.buffer.remaining(), 0)

        # now encode the msg to check that encoding is byte for byte the same
        buffer = pyamf.encode(msg, encoding=pyamf.AMF3).getvalue()

        self.assertEqual(buffer, bytes)

    def test_async(self):
        pass

    def test_getmessage(self):
        """
        Tests for `getSmallMessage`
        """
        for cls in ['AbstractMessage', 'ErrorMessage', 'RemotingMessage']:
            cls = getattr(messaging, cls)
            self.assertRaises(NotImplementedError, cls().getSmallMessage)

        kwargs = {
            'body': {'foo': 'bar'},
            'clientId': 'spam',
            'destination': 'eggs',
            'headers': {'blarg': 'whoop'},
            'messageId': 'baz',
            'timestamp': 1234,
            'timeToLive': 99
        }

        # test async
        a = messaging.AsyncMessage(correlationId='yay', **kwargs)
        m = a.getSmallMessage()

        k = kwargs.copy()
        k.update({'correlationId': 'yay'})

        self.assertTrue(isinstance(m, messaging.AsyncMessageExt))
        self.assertEqual(m.__dict__, k)

        # test command
        a = messaging.CommandMessage(operation='yay', **kwargs)
        m = a.getSmallMessage()

        k = kwargs.copy()
        k.update({'operation': 'yay', 'correlationId': None})

        self.assertTrue(isinstance(m, messaging.CommandMessageExt))
        self.assertEqual(m.__dict__, k)

        # test ack
        a = messaging.AcknowledgeMessage(**kwargs)
        m = a.getSmallMessage()

        k = kwargs.copy()
        k.update({'correlationId': None})

        self.assertTrue(isinstance(m, messaging.AcknowledgeMessageExt))
        self.assertEqual(m.__dict__, k)
