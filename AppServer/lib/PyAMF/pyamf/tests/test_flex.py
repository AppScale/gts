# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Flex compatibility tests.

@since: 0.1.0
"""

import unittest

import pyamf
from pyamf import flex, util, amf3, amf0
from pyamf.tests.util import EncoderMixIn


class ArrayCollectionTestCase(unittest.TestCase, EncoderMixIn):
    """
    Tests for L{flex.ArrayCollection}
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        unittest.TestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_create(self):
        self.assertEqual(flex.ArrayCollection(), [])
        self.assertEqual(flex.ArrayCollection([1, 2, 3]), [1, 2, 3])
        self.assertEqual(flex.ArrayCollection(('a', 'b', 'b')), ['a', 'b', 'b'])

        class X(object):
            def __iter__(self):
                return iter(['foo', 'bar', 'baz'])

        self.assertEqual(flex.ArrayCollection(X()), ['foo', 'bar', 'baz'])

        self.assertRaises(TypeError, flex.ArrayCollection,
            {'first': 'Matt', 'last': 'Matthews'})

    def test_encode_amf3(self):
        x = flex.ArrayCollection()
        x.append('eggs')

        self.assertEncoded(x,
            '\n\x07Cflex.messaging.io.ArrayCollection\t\x03\x01\x06\teggs')

    def test_encode_amf0(self):
        self.encoder = pyamf.get_encoder(pyamf.AMF0)
        self.buf = self.encoder.stream

        x = flex.ArrayCollection()
        x.append('eggs')

        self.assertEncoded(x,
            '\x11\n\x07Cflex.messaging.io.ArrayCollection\t\x03\x01\x06\teggs')

    def test_decode_amf3(self):
        stream = util.BufferedByteStream(
            '\n\x07Cflex.messaging.io.ArrayCollection\t\x03\x01\x06\teggs')
        decoder = amf3.Decoder(stream)
        x = decoder.readElement()

        self.assertEqual(x.__class__, flex.ArrayCollection)
        self.assertEqual(x, ['eggs'])

    def test_decode_proxy(self):
        stream = util.BufferedByteStream(
            '\x0a\x07;flex.messaging.io.ObjectProxy\x09\x01\x03a\x06\x09spam'
            '\x03b\x04\x05\x01')
        decoder = amf3.Decoder(stream)
        decoder.use_proxies = True

        x = decoder.readElement()

        self.assertEqual(x.__class__, pyamf.MixedArray)
        self.assertEqual(x, {'a': 'spam', 'b': 5})

    def test_decode_amf0(self):
        stream = util.BufferedByteStream(
            '\x11\n\x07Cflex.messaging.io.ArrayCollection\t\x03\x01\x06\teggs')
        decoder = amf0.Decoder(stream)
        x = decoder.readElement()

        self.assertEqual(x.__class__, flex.ArrayCollection)
        self.assertEqual(x, ['eggs'])

    def test_source_attr(self):
        s = ('\n\x07Cflex.messaging.io.ArrayCollection\n\x0b\x01\rsource'
            '\t\x05\x01\x06\x07foo\x06\x07bar\x01')

        x = pyamf.decode(s, encoding=pyamf.AMF3).next()

        self.assertTrue(isinstance(x, flex.ArrayCollection))
        self.assertEqual(x, ['foo', 'bar'])

    def test_readonly_length_property(self):
        a = flex.ArrayCollection()

        self.assertRaises(AttributeError, setattr, a, 'length', 3)


class ArrayCollectionAPITestCase(unittest.TestCase):
    def test_addItem(self):
        a = flex.ArrayCollection()
        self.assertEqual(a, [])
        self.assertEqual(a.length, 0)

        a.addItem('hi')
        self.assertEqual(a, ['hi'])
        self.assertEqual(a.length, 1)

    def test_addItemAt(self):
        a = flex.ArrayCollection()
        self.assertEqual(a, [])

        self.assertRaises(IndexError, a.addItemAt, 'foo', -1)
        self.assertRaises(IndexError, a.addItemAt, 'foo', 1)

        a.addItemAt('foo', 0)
        self.assertEqual(a, ['foo'])
        a.addItemAt('bar', 0)
        self.assertEqual(a, ['bar', 'foo'])
        self.assertEqual(a.length, 2)

    def test_getItemAt(self):
        a = flex.ArrayCollection(['a', 'b', 'c'])

        self.assertEqual(a.getItemAt(0), 'a')
        self.assertEqual(a.getItemAt(1), 'b')
        self.assertEqual(a.getItemAt(2), 'c')

        self.assertRaises(IndexError, a.getItemAt, -1)
        self.assertRaises(IndexError, a.getItemAt, 3)

    def test_getItemIndex(self):
        a = flex.ArrayCollection(['a', 'b', 'c'])

        self.assertEqual(a.getItemIndex('a'), 0)
        self.assertEqual(a.getItemIndex('b'), 1)
        self.assertEqual(a.getItemIndex('c'), 2)
        self.assertEqual(a.getItemIndex('d'), -1)

    def test_removeAll(self):
        a = flex.ArrayCollection(['a', 'b', 'c'])
        self.assertEqual(a.length, 3)

        a.removeAll()

        self.assertEqual(a, [])
        self.assertEqual(a.length, 0)

    def test_removeItemAt(self):
        a = flex.ArrayCollection(['a', 'b', 'c'])

        self.assertRaises(IndexError, a.removeItemAt, -1)
        self.assertRaises(IndexError, a.removeItemAt, 3)

        self.assertEqual(a.removeItemAt(1), 'b')
        self.assertEqual(a, ['a', 'c'])
        self.assertEqual(a.length, 2)
        self.assertEqual(a.removeItemAt(1), 'c')
        self.assertEqual(a, ['a'])
        self.assertEqual(a.length, 1)
        self.assertEqual(a.removeItemAt(0), 'a')
        self.assertEqual(a, [])
        self.assertEqual(a.length, 0)

    def test_setItemAt(self):
        a = flex.ArrayCollection(['a', 'b', 'c'])

        self.assertEqual(a.setItemAt('d', 1), 'b')
        self.assertEqual(a, ['a', 'd', 'c'])
        self.assertEqual(a.length, 3)


class ObjectProxyTestCase(unittest.TestCase, EncoderMixIn):

    amf_type = pyamf.AMF3

    def setUp(self):
        unittest.TestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_encode(self):
        x = flex.ObjectProxy(pyamf.MixedArray(a='spam', b=5))

        self.assertEncoded(x, '\n\x07;flex.messaging.io.ObjectProxy\n\x0b\x01',
            ('\x03a\x06\tspam', '\x03b\x04\x05', '\x01'))

    def test_decode(self):
        stream = util.BufferedByteStream(
            '\x0a\x07;flex.messaging.io.ObjectProxy\x09\x01\x03a\x06\x09spam'
            '\x03b\x04\x05\x01')
        decoder = amf3.Decoder(stream)

        x = decoder.readElement()

        self.assertEqual(x.__class__, flex.ObjectProxy)
        self.assertEqual(x._amf_object, {'a': 'spam', 'b': 5})

    def test_decode_proxy(self):
        stream = util.BufferedByteStream(
            '\x0a\x07;flex.messaging.io.ObjectProxy\x09\x01\x03a\x06\x09spam'
            '\x03b\x04\x05\x01')
        decoder = amf3.Decoder(stream)
        decoder.use_proxies = True

        x = decoder.readElement()

        self.assertEqual(x.__class__, pyamf.MixedArray)
        self.assertEqual(x, {'a': 'spam', 'b': 5})

    def test_get_attrs(self):
        x = flex.ObjectProxy()

        self.assertEqual(x._amf_object, pyamf.ASObject())

        x._amf_object = None
        self.assertEqual(x._amf_object, None)

    def test_repr(self):
        x = flex.ObjectProxy()

        self.assertEqual(repr(x), '<flex.messaging.io.ObjectProxy {}>')

        x = flex.ObjectProxy(u'ƒøø')

        self.assertEqual(repr(x), "<flex.messaging.io.ObjectProxy u'\\u0192\\xf8\\xf8'>")
