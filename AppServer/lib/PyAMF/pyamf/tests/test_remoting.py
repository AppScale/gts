# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for AMF Remoting.

@since: 0.1.0
"""

import unittest

import pyamf
from pyamf import remoting, util


class DecoderTestCase(unittest.TestCase):
    """
    Tests the decoders.
    """

    def test_client_version(self):
        """
        Tests the AMF client version.
        """
        for x in ('\x00', '\x01', '\x03'):
            try:
                remoting.decode('\x00' + x)
            except IOError:
                pass

    def test_null_msg(self):
        msg = remoting.decode('\x00\x00\x00\x00\x00\x00')

        self.assertEqual(msg.amfVersion, 0)
        self.assertEqual(msg.headers, {})
        self.assertEqual(msg, {})

        y = [x for x in msg]

        self.assertEqual(y, [])

    def test_simple_header(self):
        """
        Test header decoder.
        """
        msg = remoting.decode('\x00\x00\x00\x01\x00\x04name\x00\x00\x00\x00'
            '\x05\x0a\x00\x00\x00\x00\x00\x00')

        self.assertEqual(msg.amfVersion, 0)
        self.assertEqual(len(msg.headers), 1)
        self.assertEqual('name' in msg.headers, True)
        self.assertEqual(msg.headers['name'], [])
        self.assertFalse(msg.headers.is_required('name'))
        self.assertEqual(msg, {})

        y = [x for x in msg]

        self.assertEqual(y, [])

    def test_required_header(self):
        msg = remoting.decode('\x00\x00\x00\x01\x00\x04name\x01\x00\x00\x00'
            '\x05\x0a\x00\x00\x00\x00\x00\x00')

        self.assertTrue(msg.headers.is_required('name'))

    def test_invalid_header_data_length(self):
        remoting.decode('\x00\x00\x00\x01\x00\x04name\x00\x00\x00\x00\x06\x0a'
            '\x00\x00\x00\x00\x00\x00')

        self.failUnlessRaises(pyamf.DecodeError, remoting.decode,
            '\x00\x00\x00\x01\x00\x04name\x00\x00\x00\x00\x06\x0a\x00\x00\x00'
            '\x00\x00\x00', strict=True)

    def test_multiple_headers(self):
        msg = remoting.decode('\x00\x00\x00\x02\x00\x04name\x00\x00\x00\x00'
            '\x05\x0a\x00\x00\x00\x00\x00\x04spam\x01\x00\x00\x00\x01\x05\x00'
            '\x00')

        self.assertEqual(msg.amfVersion, 0)
        self.assertEqual(len(msg.headers), 2)
        self.assertEqual('name' in msg.headers, True)
        self.assertEqual('spam' in msg.headers, True)
        self.assertEqual(msg.headers['name'], [])
        self.assertFalse(msg.headers.is_required('name'))
        self.assertEqual(msg.headers['spam'], None)
        self.assertTrue(msg.headers.is_required('spam'))
        self.assertEqual(msg, {})

        y = [x for x in msg]

        self.assertEqual(y, [])

    def test_simple_body(self):
        self.failUnlessRaises(IOError, remoting.decode,
            '\x00\x00\x00\x00\x00\x01')

        msg = remoting.decode('\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00'
            '\x02/1\x00\x00\x00\x14\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x00'
            '\x00\x01\x61\x02\x00\x01\x61\x00\x00\x09')

        self.assertEqual(msg.amfVersion, 0)
        self.assertEqual(len(msg.headers), 0)
        self.assertEqual(len(msg), 1)
        self.assertTrue('/1' in msg)

        m = msg['/1']

        self.assertEqual(m.target, 'test.test')
        self.assertEqual(m.body, [{'a': 'a'}])

        y = [x for x in msg]

        self.assertEqual(len(y), 1)

        x = y[0]
        self.assertEqual(('/1', m), x)

    def test_invalid_body_data_length(self):
        remoting.decode('\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00\x02/1'
            '\x00\x00\x00\x13\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x00\x00\x01'
            '\x61\x02\x00\x01\x61\x00\x00\x09')

        self.failUnlessRaises(pyamf.DecodeError, remoting.decode,
            '\x00\x00\x00\x00\x00\x01\x00\x09test.test\x00\x02/1\x00\x00\x00'
            '\x13\x0a\x00\x00\x00\x01\x08\x00\x00\x00\x00\x00\x01\x61\x02\x00'
            '\x01\x61\x00\x00\x09', strict=True)

    def test_message_order(self):
        request = util.BufferedByteStream()
        request.write('\x00\x00\x00\x00\x00\x02\x00\x08get_spam\x00\x02/2\x00'
            '\x00\x00\x00\x0a\x00\x00\x00\x00\x00\x04echo\x00\x02/1\x00\x00'
            '\x00\x00\x0a\x00\x00\x00\x01\x02\x00\x0bhello world')
        request.seek(0, 0)

        request_envelope = remoting.decode(request)
        it = iter(request_envelope)

        self.assertEqual(it.next()[0], '/2')
        self.assertEqual(it.next()[0], '/1')

        self.assertRaises(StopIteration, it.next)

    def test_multiple_request_header_references(self):
        msg = remoting.decode(
            '\x00\x00\x00\x01\x00\x0b\x43\x72\x65\x64\x65\x6e\x74\x69\x61\x6c'
            '\x73\x00\x00\x00\x00\x2c\x11\x0a\x0b\x01\x0d\x75\x73\x65\x72\x69'
            '\x64\x06\x1f\x67\x65\x6e\x6f\x70\x72\x6f\x5c\x40\x67\x65\x72\x61'
            '\x72\x64\x11\x70\x61\x73\x73\x77\x6f\x72\x64\x06\x09\x67\x67\x67'
            '\x67\x01\x00\x01\x00\x0b\x63\x72\x65\x61\x74\x65\x47\x72\x6f\x75'
            '\x70\x00\x02\x2f\x31\x00\x00\x00\x1c\x0a\x00\x00\x00\x01\x11\x0a'
            '\x0b\x01\x09\x73\x74\x72\x41\x06\x09\x74\x65\x73\x74\x09\x73\x74'
            '\x72\x42\x06\x02\x01')

        self.assertEqual(msg.amfVersion, 0)
        self.assertEqual(len(msg.headers), 1)
        self.assertEqual(msg.headers['Credentials'],
            {'password': 'gggg', 'userid':'genopro\\@gerard'})
        self.assertEqual(len(msg), 1)
        self.assertTrue('/1' in msg)

        m = msg['/1']

        self.assertEqual(m.target, 'createGroup')
        self.assertEqual(m.body, [{'strB':'test', 'strA':'test'}])

    def test_timezone(self):
        """
        Ensure that the timezone offsets work as expected
        """
        import datetime

        td = datetime.timedelta(hours=-5)

        msg = remoting.decode(
            '\x00\x00\x00\x00\x00\x01\x00\x0b/1/onResult\x00\x04null\x00\x00'
            '\x00\x00\n\x00\x00\x00\x01\x0bBr>\xcc\n~\x00\x00\x00\x00',
            timezone_offset=td)

        self.assertEqual(msg['/1'].body[0],
            datetime.datetime(2009, 9, 24, 10, 52, 12))


class EncoderTestCase(unittest.TestCase):
    """
    Test the encoders.
    """
    def test_basic(self):
        """
        """
        msg = remoting.Envelope(pyamf.AMF0)
        self.assertEqual(remoting.encode(msg).getvalue(), '\x00' * 6)

        msg = remoting.Envelope(pyamf.AMF3)
        self.assertEqual(remoting.encode(msg).getvalue(),
            '\x00\x03' + '\x00' * 4)

    def test_header(self):
        """
        Test encoding of header.
        """
        msg = remoting.Envelope(pyamf.AMF0)

        msg.headers['spam'] = (False, 'eggs')
        self.assertEqual(remoting.encode(msg).getvalue(),
            '\x00\x00\x00\x01\x00\x04spam\x00\x00\x00\x00\x00\n\x00\x00\x00\x02'
            '\x01\x00\x02\x00\x04eggs\x00\x00')

        msg = remoting.Envelope(pyamf.AMF0)

        msg.headers['spam'] = (True, ['a', 'b', 'c'])
        self.assertEqual(remoting.encode(msg).getvalue(),
            '\x00\x00\x00\x01\x00\x04spam\x00\x00\x00\x00\x00\n\x00\x00\x00\x02'
            '\x01\x01\n\x00\x00\x00\x03\x02\x00\x01a\x02\x00\x01b\x02\x00\x01c'
            '\x00\x00')

    def test_request(self):
        """
        Test encoding of request body.
        """
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Request('test.test', body=['hello'])

        self.assertEqual(len(msg), 1)

        x = msg['/1']

        self.assertTrue(isinstance(x, remoting.Request))
        self.assertEqual(x.envelope, msg)
        self.assertEqual(x.target, 'test.test')
        self.assertEqual(x.body, ['hello'])
        self.assertEqual(x.headers, msg.headers)

        self.assertEqual(remoting.encode(msg).getvalue(),
            '\x00\x00\x00\x00\x00\x01\x00\ttest.test\x00\x02/1\x00\x00\x00'
            '\x00\n\x00\x00\x00\x01\x02\x00\x05hello')

    def test_response(self):
        """
        Test encoding of request body.
        """
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Response(body=[1, 2, 3])

        self.assertEqual(len(msg), 1)

        x = msg['/1']

        self.assertTrue(isinstance(x, remoting.Response))
        self.assertEqual(x.envelope, msg)
        self.assertEqual(x.body, [1, 2, 3])
        self.assertEqual(x.status, 0)
        self.assertEqual(x.headers, msg.headers)

        self.assertEqual(remoting.encode(msg).getvalue(), '\x00\x00\x00\x00'
            '\x00\x01\x00\x0b/1/onResult\x00\x04null\x00\x00\x00\x00\n\x00\x00'
            '\x00\x03\x00?\xf0\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00'
            '\x00\x00\x00\x00@\x08\x00\x00\x00\x00\x00\x00')

    def test_message_order(self):
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/3'] = remoting.Request('test.test', body='hello')
        msg['/1'] = remoting.Request('test.test', body='hello')
        msg['/2'] = remoting.Request('test.test', body='hello')

        it = iter(msg)

        self.assertEqual(it.next()[0], '/3')
        self.assertEqual(it.next()[0], '/1')
        self.assertEqual(it.next()[0], '/2')

        self.assertRaises(StopIteration, it.next)

    def test_stream_pos(self):
        """
        Ensure that the stream pointer is placed at the beginning.
        """
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Response(body=[1, 2, 3])

        stream = remoting.encode(msg)
        self.assertEqual(stream.tell(), 0)

    def test_timezone(self):
        """
        Ensure that the timezone offsets work as expected
        """
        import datetime

        d = datetime.datetime(2009, 9, 24, 15, 52, 12)
        td = datetime.timedelta(hours=-5)
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Response(body=[d])

        stream = remoting.encode(msg, timezone_offset=td).getvalue()

        self.assertEqual(stream, '\x00\x00\x00\x00\x00\x01\x00\x0b/1/onResult'
            '\x00\x04null\x00\x00\x00\x00\n\x00\x00\x00\x01\x0bBr>\xdd5\x06'
            '\x00\x00\x00\x00')


class StrictEncodingTestCase(unittest.TestCase):
    def test_request(self):
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Request('test.test', body=['hello'])

        self.assertEqual(remoting.encode(msg, strict=True).getvalue(),
            '\x00\x00\x00\x00\x00\x01\x00\ttest.test\x00\x02/1\x00\x00\x00'
            '\r\n\x00\x00\x00\x01\x02\x00\x05hello')

    def test_response(self):
        msg = remoting.Envelope(pyamf.AMF0)

        msg['/1'] = remoting.Response(['spam'])

        self.assertEqual(remoting.encode(msg, strict=True).getvalue(),
            '\x00\x00\x00\x00\x00\x01\x00\x0b/1/onResult\x00\x04null\x00\x00'
            '\x00\x0c\n\x00\x00\x00\x01\x02\x00\x04spam')


class FaultTestCase(unittest.TestCase):
    def test_exception(self):
        x = remoting.get_fault({'level': 'error', 'code': 'Server.Call.Failed'})

        self.assertRaises(remoting.RemotingCallFailed, x.raiseException)

    def test_kwargs(self):
        # The fact that this doesn't throw an error means that this test passes
        x = remoting.get_fault({'foo': 'bar'})

        self.assertIsInstance(x, remoting.ErrorFault)


class ContextTextCase(unittest.TestCase):
    def test_body_references(self):
        msg = remoting.Envelope(pyamf.AMF0)
        f = ['a', 'b', 'c']

        msg['/1'] = remoting.Request('foo', body=[f])
        msg['/2'] = remoting.Request('bar', body=[f])

        s = remoting.encode(msg).getvalue()
        self.assertEqual(s, '\x00\x00\x00\x00\x00\x02\x00\x03foo\x00\x02/1'
            '\x00\x00\x00\x00\n\x00\x00\x00\x01\n\x00\x00\x00\x03\x02\x00\x01'
            'a\x02\x00\x01b\x02\x00\x01c\x00\x03bar\x00\x02/2\x00\x00\x00\x00'
            '\n\x00\x00\x00\x01\n\x00\x00\x00\x03\x02\x00\x01a\x02\x00\x01b'
            '\x02\x00\x01c')


class FunctionalTestCase(unittest.TestCase):
    def test_encode_bytearray(self):
        from pyamf.amf3 import ByteArray

        stream = ByteArray()

        stream.write('12345678')

        msg = remoting.Envelope(pyamf.AMF0)
        msg['/1'] = remoting.Response([stream])

        self.assertEqual(remoting.encode(msg).getvalue(),
            '\x00\x00\x00\x00\x00\x01\x00\x0b/1/onResult\x00\x04null'
            '\x00\x00\x00\x00\n\x00\x00\x00\x01\x11\x0c\x1112345678')


class ReprTestCase(unittest.TestCase):
    def test_response(self):
        r = remoting.Response(u'€±')

        self.assertEqual(repr(r),
            "<Response status=/onResult>u'\\u20ac\\xb1'</Response>")

    def test_request(self):
        r = remoting.Request(u'€±', [u'å∫ç'])

        self.assertEqual(repr(r),
            "<Request target=u'\\u20ac\\xb1'>[u'\\xe5\\u222b\\xe7']</Request>")

    def test_base_fault(self):
        r = remoting.BaseFault(code=u'å', type=u'å', description=u'å', details=u'å')

        self.assertEqual(repr(r),
            "BaseFault level=None code=u'\\xe5' type=u'\\xe5' description=u'\\xe5'\nTraceback:\nu'\\xe5'")
