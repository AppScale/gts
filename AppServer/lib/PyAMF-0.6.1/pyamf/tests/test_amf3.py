# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for AMF3 Implementation.

@since: 0.1.0
"""

import unittest
import datetime

import pyamf
from pyamf import amf3, util, xml, python
from pyamf.tests.util import (
    Spam, EncoderMixIn, DecoderMixIn, ClassCacheClearingTestCase)


class MockAlias(object):
    def __init__(self):
        self.get_attributes = []
        self.get_static_attrs = []
        self.apply_attrs = []

        self.static_attrs = {}
        self.attrs = ({}, {})
        self.create_instance = []
        self.expected_instance = object()

    def getStaticAttrs(self, *args, **kwargs):
        self.get_static_attrs.append([args, kwargs])

        return self.static_attrs

    def getAttributes(self, *args, **kwargs):
        self.get_attributes.append([args, kwargs])

        return self.attrs

    def createInstance(self, *args, **kwargs):
        self.create_instance.append([args, kwargs])

        return self.expected_instance

    def applyAttributes(self, *args, **kwargs):
        self.apply_attrs.append([args, kwargs])


class TypesTestCase(unittest.TestCase):
    """
    Tests the type mappings.
    """
    def test_types(self):
        self.assertEqual(amf3.TYPE_UNDEFINED, '\x00')
        self.assertEqual(amf3.TYPE_NULL, '\x01')
        self.assertEqual(amf3.TYPE_BOOL_FALSE, '\x02')
        self.assertEqual(amf3.TYPE_BOOL_TRUE, '\x03')
        self.assertEqual(amf3.TYPE_INTEGER, '\x04')
        self.assertEqual(amf3.TYPE_NUMBER, '\x05')
        self.assertEqual(amf3.TYPE_STRING, '\x06')
        self.assertEqual(amf3.TYPE_XML, '\x07')
        self.assertEqual(amf3.TYPE_DATE, '\x08')
        self.assertEqual(amf3.TYPE_ARRAY, '\x09')
        self.assertEqual(amf3.TYPE_OBJECT, '\x0a')
        self.assertEqual(amf3.TYPE_XMLSTRING, '\x0b')
        self.assertEqual(amf3.TYPE_BYTEARRAY, '\x0c')


class ContextTestCase(ClassCacheClearingTestCase):
    def test_create(self):
        c = amf3.Context()

        self.assertEqual(c.strings, [])
        self.assertEqual(c.classes, {})
        self.assertEqual(len(c.strings), 0)
        self.assertEqual(len(c.classes), 0)

    def test_add_string(self):
        x = amf3.Context()
        y = 'abc'

        self.assertEqual(x.addString(y), 0)
        self.assertTrue(y in x.strings)
        self.assertEqual(len(x.strings), 1)

        self.assertEqual(x.addString(''), -1)

        self.assertRaises(TypeError, x.addString, 132)

    def test_add_class(self):
        x = amf3.Context()

        alias = pyamf.register_class(Spam, 'spam.eggs')
        y = amf3.ClassDefinition(alias)

        self.assertEqual(x.addClass(y, Spam), 0)
        self.assertEqual(x.classes, {Spam: y})
        self.assertEqual(x.class_ref, {0: y})
        self.assertEqual(len(x.class_ref), 1)

    def test_clear(self):
        x = amf3.Context()
        y = [1, 2, 3]
        z = '<a></a>'

        x.addObject(y)
        x.addString('spameggs')
        x.clear()

        self.assertEqual(x.strings, [])
        self.assertEqual(len(x.strings), 0)
        self.assertFalse('spameggs' in x.strings)

    def test_get_by_reference(self):
        x = amf3.Context()
        y = [1, 2, 3]
        z = {'spam': 'eggs'}

        alias_spam = pyamf.register_class(Spam, 'spam.eggs')

        class Foo:
            pass

        class Bar:
            pass

        alias_foo = pyamf.register_class(Foo, 'foo.bar')

        a = amf3.ClassDefinition(alias_spam)
        b = amf3.ClassDefinition(alias_foo)

        x.addObject(y)
        x.addObject(z)
        x.addString('abc')
        x.addString('def')
        x.addClass(a, Foo)
        x.addClass(b, Bar)

        self.assertEqual(x.getObject(0), y)
        self.assertEqual(x.getObject(1), z)
        self.assertEqual(x.getObject(2), None)
        self.assertRaises(TypeError, x.getObject, '')
        self.assertRaises(TypeError, x.getObject, 2.2323)

        self.assertEqual(x.getString(0), 'abc')
        self.assertEqual(x.getString(1), 'def')
        self.assertEqual(x.getString(2), None)
        self.assertRaises(TypeError, x.getString, '')
        self.assertRaises(TypeError, x.getString, 2.2323)

        self.assertEqual(x.getClass(Foo), a)
        self.assertEqual(x.getClass(Bar), b)
        self.assertEqual(x.getClass(2), None)

        self.assertEqual(x.getClassByReference(0), a)
        self.assertEqual(x.getClassByReference(1), b)
        self.assertEqual(x.getClassByReference(2), None)

        self.assertEqual(x.getObject(2), None)
        self.assertEqual(x.getString(2), None)
        self.assertEqual(x.getClass(2), None)
        self.assertEqual(x.getClassByReference(2), None)

    def test_get_reference(self):
        x = amf3.Context()
        y = [1, 2, 3]
        z = {'spam': 'eggs'}

        spam_alias = pyamf.register_class(Spam, 'spam.eggs')

        class Foo:
            pass

        foo_alias = pyamf.register_class(Foo, 'foo.bar')

        a = amf3.ClassDefinition(spam_alias)
        b = amf3.ClassDefinition(foo_alias)

        ref1 = x.addObject(y)
        ref2 = x.addObject(z)
        x.addString('abc')
        x.addString('def')
        x.addClass(a, Spam)
        x.addClass(b, Foo)

        self.assertEqual(x.getObjectReference(y), ref1)
        self.assertEqual(x.getObjectReference(z), ref2)
        self.assertEqual(x.getObjectReference({}), -1)

        self.assertEqual(x.getStringReference('abc'), 0)
        self.assertEqual(x.getStringReference('def'), 1)
        self.assertEqual(x.getStringReference('asdfas'), -1)

        self.assertEqual(x.getClass(Spam), a)
        self.assertEqual(x.getClass(Foo), b)
        self.assertEqual(x.getClass(object()), None)


class ClassDefinitionTestCase(ClassCacheClearingTestCase):

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)

        self.alias = pyamf.ClassAlias(Spam, defer=True)

    def test_dynamic(self):
        self.assertFalse(self.alias.is_compiled())

        x = amf3.ClassDefinition(self.alias)

        self.assertTrue(x.alias is self.alias)
        self.assertEqual(x.encoding, 2)
        self.assertEqual(x.attr_len, 0)

        self.assertTrue(self.alias.is_compiled())

    def test_static(self):
        self.alias.static_attrs = ['foo', 'bar']
        self.alias.dynamic = False

        x = amf3.ClassDefinition(self.alias)

        self.assertTrue(x.alias is self.alias)
        self.assertEqual(x.encoding, 0)
        self.assertEqual(x.attr_len, 2)

    def test_mixed(self):
        self.alias.static_attrs = ['foo', 'bar']

        x = amf3.ClassDefinition(self.alias)

        self.assertTrue(x.alias is self.alias)
        self.assertEqual(x.encoding, 2)
        self.assertEqual(x.attr_len, 2)

    def test_external(self):
        self.alias.external = True

        x = amf3.ClassDefinition(self.alias)

        self.assertTrue(x.alias is self.alias)
        self.assertEqual(x.encoding, 1)
        self.assertEqual(x.attr_len, 0)


class EncoderTestCase(ClassCacheClearingTestCase, EncoderMixIn):
    """
    Tests the output from the AMF3 L{Encoder<pyamf.amf3.Encoder>} class.
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_list_references(self):
        y = [0, 1, 2, 3]

        self.assertEncoded(y, '\x09\x09\x01\x04\x00\x04\x01\x04\x02\x04\x03')
        self.assertEncoded(y, '\x09\x00', clear=False)
        self.assertEncoded(y, '\x09\x00', clear=False)

    def test_list_proxy_references(self):
        self.encoder.use_proxies = True
        y = [0, 1, 2, 3]

        self.assertEncoded(y, '\n\x07Cflex.messaging.io.ArrayCollection\t\t'
            '\x01\x04\x00\x04\x01\x04\x02\x04\x03')
        self.assertEncoded(y, '\n\x00', clear=False)
        self.assertEncoded(y, '\n\x00', clear=False)

    def test_dict(self):
        self.assertEncoded({'spam': 'eggs'}, '\n\x0b\x01\tspam\x06\teggs\x01')
        self.assertEncoded({'a': u'e', 'b': u'f', 'c': u'g', 'd': u'h'},
            '\n\x0b\x01', ('\x03c\x06\x03g', '\x03b\x06\x03f', '\x03a\x06\x03e',
            '\x03d\x06\x03h'), '\x01')
        self.assertEncoded({12: True, 42: "Testing"}, ('\n\x0b', (
            '\x01\x0542\x06\x0fTesting',
            '\x0512\x03\x01'
        )))

    def test_boolean(self):
        self.assertEncoded(True, '\x03')
        self.assertEncoded(False, '\x02')

    def test_mixed_array(self):
        x = pyamf.MixedArray()
        x.update({0:u'hello', 'spam': u'eggs'})

        self.assertEncoded(x, '\t\x03\tspam\x06\teggs\x01\x06\x0bhello')

        x = pyamf.MixedArray()
        x.update({0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 'a': 'a'})

        self.assertEncoded(x, '\x09\x0d\x03\x61\x06\x00\x01\x04\x00\x04\x01'
            '\x04\x02\x04\x03\x04\x04\x04\x05')

    def test_empty_key_string(self):
        """
        Test to see if there is an empty key in the C{dict}. There is a design
        bug in Flash 9 which means that it cannot read this specific data.

        @bug: See U{http://www.docuverse.com/blog/donpark/2007/05/14/flash-9-amf3-bug}
        for more info.
        """
        def x():
            y = pyamf.MixedArray()
            y.update({'': 1, 0: 1})
            self.encode(y)

        self.failUnlessRaises(pyamf.EncodeError, x)

    def test_object(self):
        self.assertEncoded({'a': u'spam', 'b': 5},
            '\n\x0b\x01\x03a\x06\tspam\x03b\x04\x05\x01')

        pyamf.register_class(Spam, 'org.pyamf.spam')

        obj = Spam()
        obj.baz = 'hello'

        self.assertEncoded(obj,
            '\n\x0b\x1dorg.pyamf.spam\x07baz\x06\x0bhello\x01')

    def test_date(self):
        x = datetime.datetime(2005, 3, 18, 1, 58, 31)

        self.assertEncoded(x, '\x08\x01Bp+6!\x15\x80\x00')
        self.assertEncoded(x, '\x08\x00', clear=False)

        self.assertRaises(pyamf.EncodeError, self.encode, datetime.time(22, 3))

    def test_byte_array(self):
        self.assertEncoded(amf3.ByteArray('hello'), '\x0c\x0bhello')

    def test_xmlstring(self):
        x = xml.fromstring('<a><b>hello world</b></a>')
        self.assertEqual(self.encode(x), '\x0b\x33<a><b>hello world</b></a>')
        self.assertEqual(self.encode(x), '\x0b\x00')

    def test_anonymous(self):
        pyamf.register_class(Spam)

        x = Spam({'spam': 'eggs'})

        self.assertEncoded(x, '\n\x0b\x01\x09spam\x06\x09eggs\x01')

    def test_custom_type(self):
        def write_as_list(list_interface_obj, encoder):
            list_interface_obj.ran = True
            self.assertEqual(id(self.encoder), id(encoder))

            return list(list_interface_obj)

        class ListWrapper(object):
            ran = False

            def __iter__(self):
                return iter([1, 2, 3])

        pyamf.add_type(ListWrapper, write_as_list)
        x = ListWrapper()

        self.assertEncoded(x, '\t\x07\x01\x04\x01\x04\x02\x04\x03')
        self.assertTrue(x.ran)

    def test_old_style_classes(self):
        class Person:
            pass

        pyamf.register_class(Person, 'spam.eggs.Person')

        u = Person()
        u.family_name = 'Doe'
        u.given_name = 'Jane'

        self.assertEncoded(u, '\n\x0b!spam.eggs.Person', (
            '\x17family_name\x06\x07Doe', '\x15given_name\x06\tJane'), '\x01')

    def test_slots(self):
        class Person(object):
            __slots__ = ('family_name', 'given_name')

        u = Person()
        u.family_name = 'Doe'
        u.given_name = 'Jane'

        self.assertEncoded(u, '\n\x0b\x01', ('\x17family_name\x06\x07Doe',
            '\x15given_name\x06\tJane'), '\x01')

    def test_slots_registered(self):
        class Person(object):
            __slots__ = ('family_name', 'given_name')

        pyamf.register_class(Person, 'spam.eggs.Person')

        u = Person()
        u.family_name = 'Doe'
        u.given_name = 'Jane'

        self.assertEncoded(u, '\n\x0b!spam.eggs.Person', (
            '\x17family_name\x06\x07Doe', '\x15given_name\x06\tJane'), '\x01')

    def test_elementtree_tag(self):
        class NotAnElement(object):
            items = lambda self: []

            def __iter__(self):
                return iter([])

        foo = NotAnElement()
        foo.tag = 'foo'
        foo.text = 'bar'
        foo.tail = None

        self.assertEncoded(foo, '\n\x0b\x01', ('\ttext\x06\x07bar',
            '\ttail\x01', '\x07tag\x06\x07foo'), '\x01')

    def test_funcs(self):
        def x():
            pass

        for f in (chr, lambda x: x, x, pyamf, ''.startswith):
            self.assertRaises(pyamf.EncodeError, self.encode, f)

    def test_29b_ints(self):
        """
        Tests for ints that don't fit into 29bits. Reference: #519
        """
        ints = [
            (amf3.MIN_29B_INT - 1, '\x05\xc1\xb0\x00\x00\x01\x00\x00\x00'),
            (amf3.MAX_29B_INT + 1, '\x05A\xb0\x00\x00\x00\x00\x00\x00')
        ]

        for i, val in ints:
            self.buf.truncate()

            self.encoder.writeElement(i)
            self.assertEqual(self.buf.getvalue(), val)

    def test_number(self):
        vals = [
            (0,        '\x04\x00'),
            (0.2,      '\x05\x3f\xc9\x99\x99\x99\x99\x99\x9a'),
            (1,        '\x04\x01'),
            (127,      '\x04\x7f'),
            (128,      '\x04\x81\x00'),
            (0x3fff,   '\x04\xff\x7f'),
            (0x4000,   '\x04\x81\x80\x00'),
            (0x1FFFFF, '\x04\xff\xff\x7f'),
            (0x200000, '\x04\x80\xc0\x80\x00'),
            (0x3FFFFF, '\x04\x80\xff\xff\xff'),
            (0x400000, '\x04\x81\x80\x80\x00'),
            (-1,       '\x04\xff\xff\xff\xff'),
            (42,       '\x04\x2a'),
            (-123,     '\x04\xff\xff\xff\x85'),
            (amf3.MIN_29B_INT, '\x04\xc0\x80\x80\x00'),
            (amf3.MAX_29B_INT, '\x04\xbf\xff\xff\xff'),
            (1.23456789, '\x05\x3f\xf3\xc0\xca\x42\x83\xde\x1b')
        ]

        for i, val in vals:
            self.buf.truncate()

            self.encoder.writeElement(i)
            self.assertEqual(self.buf.getvalue(), val)

    def test_class(self):
        class New(object):
            pass

        class Classic:
            pass

        self.assertRaises(pyamf.EncodeError, self.encoder.writeElement, Classic)
        self.assertRaises(pyamf.EncodeError, self.encoder.writeElement, New)

    def test_proxy(self):
        """
        Test to ensure that only C{dict} objects will be proxied correctly
        """
        self.encoder.use_proxies = True
        bytes = '\n\x07;flex.messaging.io.ObjectProxy\n\x0b\x01\x01'

        self.assertEncoded(pyamf.ASObject(), bytes)
        self.assertEncoded({}, bytes)

    def test_proxy_non_dict(self):
        class Foo(object):
            pass

        self.encoder.use_proxies = True
        bytes = '\n\x0b\x01\x01'

        self.assertEncoded(Foo(), bytes)

    def test_timezone(self):
        d = datetime.datetime(2009, 9, 24, 14, 23, 23)
        self.encoder.timezone_offset = datetime.timedelta(hours=-5)

        self.encoder.writeElement(d)

        self.assertEqual(self.buf.getvalue(), '\x08\x01Br>\xd8\x1f\xff\x80\x00')

    def test_generator(self):
        def foo():
            yield [1, 2, 3]
            yield u'\xff'
            yield pyamf.Undefined

        self.assertEncoded(foo(), '\t\x07\x01\x04\x01\x04\x02\x04\x03\x06\x05'
            '\xc3\xbf\x00')

    def test_iterate(self):
        self.assertRaises(StopIteration, self.encoder.next)

        self.encoder.send('')
        self.encoder.send('hello')
        self.encoder.send(u'ƒøø')

        self.assertEqual(self.encoder.next(), '\x06\x01')
        self.assertEqual(self.encoder.next(), '\x06\x0bhello')
        self.assertEqual(self.encoder.next(), '\x06\r\xc6\x92\xc3\xb8\xc3\xb8')

        self.assertRaises(StopIteration, self.encoder.next)

        self.assertIdentical(iter(self.encoder), self.encoder)
        self.assertEqual(self.buf.getvalue(),
            '\x06\x01\x06\x0bhello\x06\r\xc6\x92\xc3\xb8\xc3\xb8')


class DecoderTestCase(ClassCacheClearingTestCase, DecoderMixIn):
    """
    Tests the output from the AMF3 L{Decoder<pyamf.amf3.Decoder>} class.
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        DecoderMixIn.setUp(self)

    def test_undefined(self):
        self.assertDecoded(pyamf.Undefined, '\x00')

    def test_number(self):
        self.assertDecoded(0, '\x04\x00')
        self.assertDecoded(0.2, '\x05\x3f\xc9\x99\x99\x99\x99\x99\x9a')
        self.assertDecoded(1, '\x04\x01')
        self.assertDecoded(-1, '\x04\xff\xff\xff\xff')
        self.assertDecoded(42, '\x04\x2a')

        # two ways to represent -123, as an int and as a float
        self.assertDecoded(-123, '\x04\xff\xff\xff\x85')
        self.assertDecoded(-123, '\x05\xc0\x5e\xc0\x00\x00\x00\x00\x00')

        self.assertDecoded(1.23456789, '\x05\x3f\xf3\xc0\xca\x42\x83\xde\x1b')

    def test_integer(self):
        self.assertDecoded(0, '\x04\x00')
        self.assertDecoded(0x35, '\x04\x35')
        self.assertDecoded(0x7f, '\x04\x7f')
        self.assertDecoded(0x80, '\x04\x81\x00')
        self.assertDecoded(0xd4, '\x04\x81\x54')
        self.assertDecoded(0x3fff, '\x04\xff\x7f')
        self.assertDecoded(0x4000, '\x04\x81\x80\x00')
        self.assertDecoded(0x1a53f, '\x04\x86\xca\x3f')
        self.assertDecoded(0x1fffff, '\x04\xff\xff\x7f')
        self.assertDecoded(0x200000, '\x04\x80\xc0\x80\x00')
        self.assertDecoded(-0x01, '\x04\xff\xff\xff\xff')
        self.assertDecoded(-0x2a, '\x04\xff\xff\xff\xd6')
        self.assertDecoded(0xfffffff, '\x04\xbf\xff\xff\xff')
        self.assertDecoded(-0x10000000, '\x04\xc0\x80\x80\x00')

    def test_infinites(self):
        x = self.decode('\x05\xff\xf8\x00\x00\x00\x00\x00\x00')
        self.assertTrue(python.isNaN(x))

        x = self.decode('\x05\xff\xf0\x00\x00\x00\x00\x00\x00')
        self.assertTrue(python.isNegInf(x))

        x = self.decode('\x05\x7f\xf0\x00\x00\x00\x00\x00\x00')
        self.assertTrue(python.isPosInf(x))

    def test_boolean(self):
        self.assertDecoded(True, '\x03')
        self.assertDecoded(False, '\x02')

    def test_null(self):
        self.assertDecoded(None, '\x01')

    def test_string(self):
        self.assertDecoded('', '\x06\x01')
        self.assertDecoded('hello', '\x06\x0bhello')
        self.assertDecoded(
            u'ღმერთსი შემვედრე, ნუთუ კვლა დამხსნას სოფლისა შრომასა, ცეცხლს',
            '\x06\x82\x45\xe1\x83\xa6\xe1\x83\x9b\xe1\x83\x94\xe1\x83\xa0'
            '\xe1\x83\x97\xe1\x83\xa1\xe1\x83\x98\x20\xe1\x83\xa8\xe1\x83'
            '\x94\xe1\x83\x9b\xe1\x83\x95\xe1\x83\x94\xe1\x83\x93\xe1\x83'
            '\xa0\xe1\x83\x94\x2c\x20\xe1\x83\x9c\xe1\x83\xa3\xe1\x83\x97'
            '\xe1\x83\xa3\x20\xe1\x83\x99\xe1\x83\x95\xe1\x83\x9a\xe1\x83'
            '\x90\x20\xe1\x83\x93\xe1\x83\x90\xe1\x83\x9b\xe1\x83\xae\xe1'
            '\x83\xa1\xe1\x83\x9c\xe1\x83\x90\xe1\x83\xa1\x20\xe1\x83\xa1'
            '\xe1\x83\x9d\xe1\x83\xa4\xe1\x83\x9a\xe1\x83\x98\xe1\x83\xa1'
            '\xe1\x83\x90\x20\xe1\x83\xa8\xe1\x83\xa0\xe1\x83\x9d\xe1\x83'
            '\x9b\xe1\x83\x90\xe1\x83\xa1\xe1\x83\x90\x2c\x20\xe1\x83\xaa'
            '\xe1\x83\x94\xe1\x83\xaa\xe1\x83\xae\xe1\x83\x9a\xe1\x83\xa1')

    def test_mixed_array(self):
        y = self.decode('\x09\x09\x03\x62\x06\x00\x03\x64\x06\x02\x03\x61'
            '\x06\x04\x03\x63\x06\x06\x01\x04\x00\x04\x01\x04\x02\x04\x03')

        self.assertTrue(isinstance(y,pyamf.MixedArray))
        self.assertEqual(y,
            {'a': u'a', 'b': u'b', 'c': u'c', 'd': u'd', 0: 0, 1: 1, 2: 2, 3: 3})

    def test_string_references(self):
        self.assertDecoded('hello', '\x06\x0bhello')
        self.assertDecoded('hello', '\x06\x00', clear=False)
        self.assertDecoded('hello', '\x06\x00', clear=False)

    def test_xmlstring(self):
        self.buf.write('\x0b\x33<a><b>hello world</b></a>')
        self.buf.seek(0, 0)
        x = self.decoder.readElement()

        self.assertEqual(xml.tostring(x), '<a><b>hello world</b></a>')

        self.buf.truncate()
        self.buf.write('\x0b\x00')
        self.buf.seek(0, 0)
        y = self.decoder.readElement()

        self.assertEqual(x, y)

    def test_xmlstring_references(self):
        self.buf.write('\x0b\x33<a><b>hello world</b></a>\x0b\x00')
        self.buf.seek(0, 0)
        x = self.decoder.readElement()
        y = self.decoder.readElement()

        self.assertEqual(id(x), id(y))

    def test_list(self):
        self.assertDecoded([], '\x09\x01\x01')
        self.assertDecoded([0, 1, 2, 3],
            '\x09\x09\x01\x04\x00\x04\x01\x04\x02\x04\x03')
        self.assertDecoded(["Hello", 2, 3, 4, 5], '\x09\x0b\x01\x06\x0b\x48'
            '\x65\x6c\x6c\x6f\x04\x02\x04\x03\x04\x04\x04\x05')

    def test_list_references(self):
        y = [0, 1, 2, 3]
        z = [0, 1, 2]

        self.assertDecoded(y, '\x09\x09\x01\x04\x00\x04\x01\x04\x02\x04\x03')
        self.assertDecoded(y, '\x09\x00', clear=False)
        self.assertDecoded(z, '\x09\x07\x01\x04\x00\x04\x01\x04\x02', clear=False)
        self.assertDecoded(z, '\x09\x02', clear=False)

    def test_dict(self):
        self.assertDecoded({'a': u'a', 'b': u'b', 'c': u'c', 'd': u'd'},
            '\n\x0b\x01\x03a\x06\x00\x03c\x06\x02\x03b\x06\x04\x03d\x06\x06\x01')

        self.assertDecoded({0: u'hello', 'foo': u'bar'}, '\x09\x03\x07\x66\x6f'
            '\x6f\x06\x07\x62\x61\x72\x01\x06\x0b\x68\x65\x6c\x6c\x6f')
        self.assertDecoded({0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 'a': 'a'},
            '\x09\x0d\x03\x61\x06\x00\x01\x04\x00\x04\x01\x04\x02\x04\x03\x04'
            '\x04\x04\x05')
        self.assertDecoded({'a': u'a', 'b': u'b', 'c': u'c', 'd': u'd',
            0: 0, 1: 1, 2: 2, 3: 3},
            '\x09\x09\x03\x62\x06\x00\x03\x64\x06\x02\x03\x61\x06\x04\x03\x63'
            '\x06\x06\x01\x04\x00\x04\x01\x04\x02\x04\x03')
        self.assertDecoded({'a': 1, 'b': 2}, '\x0a\x0b\x01\x03\x62\x04\x02\x03'
            '\x61\x04\x01\x01')
        self.assertDecoded({'baz': u'hello'}, '\x0a\x0b\x01\x07\x62\x61\x7a'
            '\x06\x0b\x68\x65\x6c\x6c\x6f\x01')
        self.assertDecoded({'baz': u'hello'}, '\x0a\x13\x01\x07\x62\x61\x7a'
            '\x06\x0b\x68\x65\x6c\x6c\x6f')

        bytes = '\x0a\x0b\x01\x07\x62\x61\x7a\x06\x0b\x68\x65\x6c\x6c\x6f\x01'

        self.buf.write(bytes)
        self.buf.seek(0)
        d = self.decoder.readElement()

    def test_object(self):
        pyamf.register_class(Spam, 'org.pyamf.spam')

        self.buf.truncate(0)
        self.buf.write(
            '\x0a\x13\x1dorg.pyamf.spam\x07baz\x06\x0b\x68\x65\x6c\x6c\x6f')
        self.buf.seek(0)

        obj = self.decoder.readElement()

        self.assertEqual(obj.__class__, Spam)

        self.failUnless(hasattr(obj, 'baz'))
        self.assertEqual(obj.baz, 'hello')

    def test_byte_array(self):
        self.assertDecoded(amf3.ByteArray('hello'), '\x0c\x0bhello')

    def test_date(self):
        import datetime

        self.assertDecoded(datetime.datetime(2005, 3, 18, 1, 58, 31),
            '\x08\x01Bp+6!\x15\x80\x00')

    def test_not_strict(self):
        self.assertFalse(self.decoder.strict)

        # write a typed object to the stream
        self.buf.write('\n\x0b\x13spam.eggs\x07foo\x06\x07bar\x01')
        self.buf.seek(0)

        self.assertFalse('spam.eggs' in pyamf.CLASS_CACHE)

        obj = self.decoder.readElement()

        self.assertTrue(isinstance(obj, pyamf.TypedObject))
        self.assertEqual(obj.alias, 'spam.eggs')
        self.assertEqual(obj, {'foo': 'bar'})

    def test_strict(self):
        self.decoder.strict = True

        self.assertTrue(self.decoder.strict)

        # write a typed object to the stream
        self.buf.write('\n\x0b\x13spam.eggs\x07foo\x06\x07bar\x01')
        self.buf.seek(0)

        self.assertFalse('spam.eggs' in pyamf.CLASS_CACHE)

        self.assertRaises(pyamf.UnknownClassAlias, self.decoder.readElement)

    def test_slots(self):
        class Person(object):
            __slots__ = ('family_name', 'given_name')

        pyamf.register_class(Person, 'spam.eggs.Person')

        self.buf.write('\n+!spam.eggs.Person\x17family_name\x15given_name\x06'
            '\x07Doe\x06\tJane\x02\x06\x06\x04\x06\x08\x01')
        self.buf.seek(0)

        foo = self.decoder.readElement()

        self.assertTrue(isinstance(foo, Person))
        self.assertEqual(foo.family_name, 'Doe')
        self.assertEqual(foo.given_name, 'Jane')
        self.assertEqual(self.buf.remaining(), 0)

    def test_default_proxy_flag(self):
        amf3.use_proxies_default = True
        decoder = amf3.Decoder(self.buf, context=self.context)
        self.assertTrue(decoder.use_proxies)
        amf3.use_proxies_default = False
        decoder = amf3.Decoder(self.buf, context=self.context)
        self.assertFalse(decoder.use_proxies)

    def test_ioerror_buffer_position(self):
        """
        Test to ensure that if an IOError is raised by `readElement` that
        the original position of the stream is restored.
        """
        bytes = pyamf.encode(u'foo', [1, 2, 3], encoding=pyamf.AMF3).getvalue()

        self.buf.write(bytes[:-1])
        self.buf.seek(0)

        self.decoder.readElement()
        self.assertEqual(self.buf.tell(), 5)

        self.assertRaises(IOError, self.decoder.readElement)
        self.assertEqual(self.buf.tell(), 5)

    def test_timezone(self):
        self.decoder.timezone_offset = datetime.timedelta(hours=-5)

        self.buf.write('\x08\x01Br>\xc6\xf5w\x80\x00')
        self.buf.seek(0)

        f = self.decoder.readElement()

        self.assertEqual(f, datetime.datetime(2009, 9, 24, 9, 23, 23))

    def test_iterate(self):
        self.assertRaises(StopIteration, self.decoder.next)

        self.decoder.send('\x01')
        self.decoder.send('\x03')
        self.decoder.send('\x02')

        self.assertEqual(self.decoder.next(), None)
        self.assertEqual(self.decoder.next(), True)
        self.assertEqual(self.decoder.next(), False)

        self.assertRaises(StopIteration, self.decoder.next)

        self.assertIdentical(iter(self.decoder), self.decoder)

    def test_bad_type(self):
        self.assertRaises(pyamf.DecodeError, self.decode, '\xff')

    def test_kwargs(self):
        """
        Python <= 3 demand that kwargs keys be bytes instead of unicode/string.
        """
        def f(**kwargs):
            self.assertEqual(kwargs, {'spam': 'eggs'})

        kwargs = self.decode('\n\x0b\x01\tspam\x06\teggs\x01')

        f(**kwargs)


class ObjectEncodingTestCase(ClassCacheClearingTestCase, EncoderMixIn):
    """
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_object_references(self):
        obj = pyamf.ASObject(a='b')

        self.encoder.writeElement(obj)
        pos = self.buf.tell()
        self.encoder.writeElement(obj)
        self.assertEqual(self.buf.getvalue()[pos:], '\x0a\x00')
        self.buf.truncate()

        self.encoder.writeElement(obj)
        self.assertEqual(self.buf.getvalue(), '\x0a\x00')
        self.buf.truncate()

    def test_class_references(self):
        alias = pyamf.register_class(Spam, 'abc.xyz')

        x = Spam({'spam': 'eggs'})
        y = Spam({'foo': 'bar'})

        self.encoder.writeElement(x)

        cd = self.context.getClass(Spam)

        self.assertTrue(cd.alias is alias)

        self.assertEqual(self.buf.getvalue(), '\n\x0b\x0fabc.xyz\tspam\x06\teggs\x01')

        pos = self.buf.tell()
        self.encoder.writeElement(y)
        self.assertEqual(self.buf.getvalue()[pos:], '\n\x01\x07foo\x06\x07bar\x01')

    def test_static(self):
        alias = pyamf.register_class(Spam, 'abc.xyz')

        alias.dynamic = False

        x = Spam({'spam': 'eggs'})
        self.encoder.writeElement(x)
        self.assertEqual(self.buf.getvalue(), '\n\x03\x0fabc.xyz')
        pyamf.unregister_class(Spam)
        self.buf.truncate()
        self.encoder.context.clear()

        alias = pyamf.register_class(Spam, 'abc.xyz')
        alias.dynamic = False
        alias.static_attrs = ['spam']

        x = Spam({'spam': 'eggs', 'foo': 'bar'})
        self.encoder.writeElement(x)
        self.assertEqual(self.buf.getvalue(), '\n\x13\x0fabc.xyz\tspam\x06\teggs')

    def test_dynamic(self):
        pyamf.register_class(Spam, 'abc.xyz')

        x = Spam({'spam': 'eggs'})
        self.encoder.writeElement(x)

        self.assertEqual(self.buf.getvalue(), '\n\x0b\x0fabc.xyz\tspam\x06\teggs\x01')

    def test_combined(self):
        alias = pyamf.register_class(Spam, 'abc.xyz')

        alias.static_attrs = ['spam']

        x = Spam({'spam': 'foo', 'eggs': 'bar'})
        self.encoder.writeElement(x)

        buf = self.buf.getvalue()

        self.assertEqual(buf, '\n\x1b\x0fabc.xyz\tspam\x06\x07foo\teggs\x06\x07bar\x01')

    def test_external(self):
        alias = pyamf.register_class(Spam, 'abc.xyz')

        alias.external = True

        x = Spam({'spam': 'eggs'})
        self.encoder.writeElement(x)

        buf = self.buf.getvalue()

        # an inline object with and inline class-def, encoding = 0x01, 1 attr

        self.assertEqual(buf[:2], '\x0a\x07')
        # class alias name
        self.assertEqual(buf[2:10], '\x0fabc.xyz')

        self.assertEqual(len(buf), 10)

    def test_anonymous_class_references(self):
        """
        Test to ensure anonymous class references with static attributes
        are encoded propertly
        """
        class Foo:
            class __amf__:
                static = ('name', 'id', 'description')

        x = Foo()
        x.id = 1
        x.name = 'foo'
        x.description = None

        y = Foo()
        y.id = 2
        y.name = 'bar'
        y.description = None

        self.encoder.writeElement([x, y])

        self.assertEqual(self.buf.getvalue(),
            '\t\x05\x01\n;\x01\tname\x05id\x17description\x06\x07foo\x04\x01'
            '\x01\x01\n\x01\x06\x07bar\x04\x02\x01\x01')


class ObjectDecodingTestCase(ClassCacheClearingTestCase, DecoderMixIn):
    """
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        DecoderMixIn.setUp(self)

    def test_object_references(self):
        self.buf.write('\x0a\x23\x01\x03a\x03b\x06\x09spam\x04\x05')
        self.buf.seek(0, 0)

        obj1 = self.decoder.readElement()

        self.buf.truncate()
        self.buf.write('\n\x00')
        self.buf.seek(0, 0)

        obj2 = self.decoder.readElement()

        self.assertEqual(id(obj1), id(obj2))

    def test_static(self):
        pyamf.register_class(Spam, 'abc.xyz')

        self.buf.write('\x0a\x13\x0fabc.xyz\x09spam\x06\x09eggs')
        self.buf.seek(0, 0)

        obj = self.decoder.readElement()

        class_def = self.context.getClass(Spam)

        self.assertEqual(class_def.static_properties, ['spam'])

        self.assertTrue(isinstance(obj, Spam))
        self.assertEqual(obj.__dict__, {'spam': 'eggs'})

    def test_dynamic(self):
        pyamf.register_class(Spam, 'abc.xyz')

        self.buf.write('\x0a\x0b\x0fabc.xyz\x09spam\x06\x09eggs\x01')
        self.buf.seek(0, 0)

        obj = self.decoder.readElement()

        class_def = self.context.getClass(Spam)

        self.assertEqual(class_def.static_properties, [])

        self.assertTrue(isinstance(obj, Spam))
        self.assertEqual(obj.__dict__, {'spam': 'eggs'})

    def test_combined(self):
        """
        This tests an object encoding with static properties and dynamic
        properties
        """
        pyamf.register_class(Spam, 'abc.xyz')

        self.buf.write(
            '\x0a\x1b\x0fabc.xyz\x09spam\x06\x09eggs\x07baz\x06\x07nat\x01')
        self.buf.seek(0, 0)

        obj = self.decoder.readElement()

        class_def = self.context.getClass(Spam)

        self.assertEqual(class_def.static_properties, ['spam'])

        self.assertTrue(isinstance(obj, Spam))
        self.assertEqual(obj.__dict__, {'spam': 'eggs', 'baz': 'nat'})

    def test_external(self):
        alias = pyamf.register_class(Spam, 'abc.xyz')
        alias.external = True

        self.buf.write('\x0a\x07\x0fabc.xyz')
        self.buf.seek(0)
        x = self.decoder.readElement()

        self.assertTrue(isinstance(x, Spam))
        self.assertEqual(x.__dict__, {})


class DataOutputTestCase(unittest.TestCase, EncoderMixIn):
    """
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        EncoderMixIn.setUp(self)

        self.x = amf3.DataOutput(self.encoder)

    def test_create(self):
        self.assertEqual(self.x.encoder, self.encoder)
        self.assertEqual(self.x.stream, self.buf)

    def test_boolean(self):
        self.x.writeBoolean(True)
        self.assertEqual(self.buf.getvalue(), '\x01')
        self.buf.truncate()

        self.x.writeBoolean(False)
        self.assertEqual(self.buf.getvalue(), '\x00')

    def test_byte(self):
        for y in xrange(10):
            self.x.writeByte(y)

        self.assertEqual(self.buf.getvalue(),
            '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')

    def test_double(self):
        self.x.writeDouble(0.0)
        self.assertEqual(self.buf.getvalue(), '\x00' * 8)
        self.buf.truncate()

        self.x.writeDouble(1234.5678)
        self.assertEqual(self.buf.getvalue(), '@\x93JEm\\\xfa\xad')

    def test_float(self):
        self.x.writeFloat(0.0)
        self.assertEqual(self.buf.getvalue(), '\x00' * 4)
        self.buf.truncate()

        self.x.writeFloat(1234.5678)
        self.assertEqual(self.buf.getvalue(), 'D\x9aR+')

    def test_int(self):
        self.x.writeInt(0)
        self.assertEqual(self.buf.getvalue(), '\x00\x00\x00\x00')
        self.buf.truncate()

        self.x.writeInt(-12345)
        self.assertEqual(self.buf.getvalue(), '\xff\xff\xcf\xc7')
        self.buf.truncate()

        self.x.writeInt(98)
        self.assertEqual(self.buf.getvalue(), '\x00\x00\x00b')

    def test_multi_byte(self):
        # TODO nick: test multiple charsets
        self.x.writeMultiByte('this is a test', 'utf-8')
        self.assertEqual(self.buf.getvalue(), u'this is a test')
        self.buf.truncate()

        self.x.writeMultiByte(u'ἔδωσαν', 'utf-8')
        self.assertEqual(self.buf.getvalue(), '\xe1\xbc\x94\xce\xb4\xcf'
            '\x89\xcf\x83\xce\xb1\xce\xbd')

    def test_object(self):
        obj = pyamf.MixedArray(spam='eggs')

        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(), '\t\x01\tspam\x06\teggs\x01')
        self.buf.truncate()

        # check references
        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(), '\t\x00')
        self.buf.truncate()

    def test_object_proxy(self):
        self.encoder.use_proxies = True
        obj = {'spam': 'eggs'}

        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(),
            '\n\x07;flex.messaging.io.ObjectProxy\n\x0b\x01\tspam\x06\teggs\x01')
        self.buf.truncate()

        # check references
        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(), '\n\x00')
        self.buf.truncate()

    def test_object_proxy_mixed_array(self):
        self.encoder.use_proxies = True
        obj = pyamf.MixedArray(spam='eggs')

        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(),
            '\n\x07;flex.messaging.io.ObjectProxy\n\x0b\x01\tspam\x06\teggs\x01')
        self.buf.truncate()

        # check references
        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(), '\n\x00')
        self.buf.truncate()

    def test_object_proxy_inside_list(self):
        self.encoder.use_proxies = True
        obj = [{'spam': 'eggs'}]

        self.x.writeObject(obj)
        self.assertEqual(self.buf.getvalue(),
            '\n\x07Cflex.messaging.io.ArrayCollection\t\x03\x01\n\x07;'
            'flex.messaging.io.ObjectProxy\n\x0b\x01\tspam\x06\teggs\x01')

    def test_short(self):
        self.x.writeShort(55)
        self.assertEqual(self.buf.getvalue(), '\x007')
        self.buf.truncate()

        self.x.writeShort(-55)
        self.assertEqual(self.buf.getvalue(), '\xff\xc9')

    def test_uint(self):
        self.x.writeUnsignedInt(55)
        self.assertEqual(self.buf.getvalue(), '\x00\x00\x007')
        self.buf.truncate()

        self.assertRaises(OverflowError, self.x.writeUnsignedInt, -55)

    def test_utf(self):
        self.x.writeUTF(u'ἔδωσαν')

        self.assertEqual(self.buf.getvalue(), '\x00\r\xe1\xbc\x94\xce'
            '\xb4\xcf\x89\xcf\x83\xce\xb1\xce\xbd')

    def test_utf_bytes(self):
        self.x.writeUTFBytes(u'ἔδωσαν')

        self.assertEqual(self.buf.getvalue(),
            '\xe1\xbc\x94\xce\xb4\xcf\x89\xcf\x83\xce\xb1\xce\xbd')


class DataInputTestCase(unittest.TestCase):
    def setUp(self):
        self.buf = util.BufferedByteStream()
        self.decoder = amf3.Decoder(self.buf)

    def test_create(self):
        x = amf3.DataInput(self.decoder)

        self.assertEqual(x.decoder, self.decoder)
        self.assertEqual(x.stream, self.buf)
        self.assertEqual(x.stream, self.decoder.stream)

    def _test(self, bytes, value, func, *params):
        self.buf.write(bytes)
        self.buf.seek(0)

        self.assertEqual(func(*params), value)
        self.buf.truncate()

    def test_boolean(self):
        x = amf3.DataInput(self.decoder)

        self.buf.write('\x01')
        self.buf.seek(-1, 2)
        self.assertEqual(x.readBoolean(), True)

        self.buf.write('\x00')
        self.buf.seek(-1, 2)
        self.assertEqual(x.readBoolean(), False)

    def test_byte(self):
        x = amf3.DataInput(self.decoder)

        self.buf.write('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09')
        self.buf.seek(0)

        for y in xrange(10):
            self.assertEqual(x.readByte(), y)

    def test_double(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x00' * 8, 0.0, x.readDouble)
        self._test('@\x93JEm\\\xfa\xad', 1234.5678, x.readDouble)

    def test_float(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x00' * 4, 0.0, x.readFloat)
        self._test('?\x00\x00\x00', 0.5, x.readFloat)

    def test_int(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x00\x00\x00\x00', 0, x.readInt)
        self._test('\xff\xff\xcf\xc7', -12345, x.readInt)
        self._test('\x00\x00\x00b', 98, x.readInt)

    def test_multi_byte(self):
        # TODO nick: test multiple charsets
        x = amf3.DataInput(self.decoder)

        self._test(u'this is a test', u'this is a test', x.readMultiByte,
            14, 'utf-8')
        self._test('\xe1\xbc\x94\xce\xb4\xcf\x89\xcf\x83\xce\xb1\xce\xbd',
            u'ἔδωσαν', x.readMultiByte, 13, 'utf-8')

    def test_object(self):
        x = amf3.DataInput(self.decoder)

        self._test('\t\x01\x09spam\x06\x09eggs\x01', {'spam': 'eggs'}, x.readObject)
        # check references
        self._test('\t\x00', {'spam': 'eggs'}, x.readObject)

    def test_short(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x007', 55, x.readShort)
        self._test('\xff\xc9', -55, x.readShort)

    def test_uint(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x00\x00\x007', 55, x.readUnsignedInt)

    def test_utf(self):
        x = amf3.DataInput(self.decoder)

        self._test('\x00\x0bhello world', u'hello world', x.readUTF)
        self._test('\x00\r\xe1\xbc\x94\xce\xb4\xcf\x89\xcf\x83\xce\xb1\xce\xbd',
            u'ἔδωσαν', x.readUTF)

    def test_utf_bytes(self):
        x = amf3.DataInput(self.decoder)

        self._test('\xe1\xbc\x94\xce\xb4\xcf\x89\xcf\x83\xce\xb1\xce\xbd',
            u'ἔδωσαν', x.readUTFBytes, 13)


class ClassInheritanceTestCase(ClassCacheClearingTestCase, EncoderMixIn):
    """
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_simple(self):
        class A(object):
            pass

        alias = pyamf.register_class(A, 'A')
        alias.static_attrs = ['a']

        class B(A):
            pass

        alias = pyamf.register_class(B, 'B')
        alias.static_attrs = ['b']

        x = B()
        x.a = 'spam'
        x.b = 'eggs'

        self.assertEncoded(x,
            '\n+\x03B\x03a\x03b\x06\tspam\x06\teggs\x01')

    def test_deep(self):
        class A(object):
            pass

        alias = pyamf.register_class(A, 'A')
        alias.static_attrs = ['a']

        class B(A):
            pass

        alias = pyamf.register_class(B, 'B')
        alias.static_attrs = ['b']

        class C(B):
            pass

        alias = pyamf.register_class(C, 'C')
        alias.static_attrs = ['c']

        x = C()
        x.a = 'spam'
        x.b = 'eggs'
        x.c = 'foo'

        self.assertEncoded(x,
            '\n;\x03C\x03b\x03a\x03c\x06\teggs\x06\tspam\x06\x07foo\x01')


class ComplexEncodingTestCase(unittest.TestCase, EncoderMixIn):
    """
    """

    amf_type = pyamf.AMF3

    class TestObject(object):
        def __init__(self):
            self.number = None
            self.test_list = ['test']
            self.sub_obj = None
            self.test_dict = {'test': 'ignore'}

        def __repr__(self):
            return '<TestObject %r @ 0x%x>' % (self.__dict__, id(self))

    class TestSubObject(object):
        def __init__(self):
            self.number = None

        def __repr__(self):
            return '<TestSubObject %r @ 0x%x>' % (self.__dict__, id(self))

    def setUp(self):
        EncoderMixIn.setUp(self)

        pyamf.register_class(self.TestObject, 'test_complex.test')
        pyamf.register_class(self.TestSubObject, 'test_complex.sub')

    def tearDown(self):
        EncoderMixIn.tearDown(self)

        pyamf.unregister_class(self.TestObject)
        pyamf.unregister_class(self.TestSubObject)

    def build_complex(self, max=5):
        test_objects = []

        for i in range(0, max):
            test_obj = self.TestObject()
            test_obj.number = i
            test_obj.sub_obj = self.TestSubObject()
            test_obj.sub_obj.number = i
            test_objects.append(test_obj)

        return test_objects

    def complex_test(self):
        to_cd = self.context.getClass(self.TestObject)
        tso_cd = self.context.getClass(self.TestSubObject)

        self.assertIdentical(to_cd.alias.klass, self.TestObject)
        self.assertIdentical(tso_cd.alias.klass, self.TestSubObject)

        self.assertEqual(self.context.getClassByReference(3), None)

    def complex_encode_decode_test(self, decoded):
        for obj in decoded:
            self.assertEqual(self.TestObject, obj.__class__)
            self.assertEqual(self.TestSubObject, obj.sub_obj.__class__)

    def test_complex_dict(self):
        complex = {'element': 'ignore', 'objects': self.build_complex()}

        self.encoder.writeElement(complex)
        self.complex_test()

    def test_complex_encode_decode_dict(self):
        complex = {'element': 'ignore', 'objects': self.build_complex()}
        self.encoder.writeElement(complex)
        encoded = self.encoder.stream.getvalue()

        context = amf3.Context()
        decoded = amf3.Decoder(encoded, context).readElement()

        self.complex_encode_decode_test(decoded['objects'])

    def test_class_refs(self):
        a = self.TestSubObject()
        b = self.TestSubObject()

        self.encoder.writeObject(a)

        cd = self.context.getClass(self.TestSubObject)

        self.assertIdentical(self.context.getClassByReference(0), cd)
        self.assertEqual(self.context.getClassByReference(1), None)

        self.encoder.writeElement({'foo': 'bar'})

        cd2 = self.context.getClass(dict)
        self.assertIdentical(self.context.getClassByReference(1), cd2)
        self.assertEqual(self.context.getClassByReference(2), None)

        self.encoder.writeElement({})

        self.assertIdentical(self.context.getClassByReference(0), cd)
        self.assertIdentical(self.context.getClassByReference(1), cd2)
        self.assertEqual(self.context.getClassByReference(2), None)

        self.encoder.writeElement(b)

        self.assertIdentical(self.context.getClassByReference(0), cd)
        self.assertIdentical(self.context.getClassByReference(1), cd2)
        self.assertEqual(self.context.getClassByReference(2), None)

        c = self.TestObject()

        self.encoder.writeElement(c)
        cd3 = self.context.getClass(self.TestObject)

        self.assertIdentical(self.context.getClassByReference(0), cd)
        self.assertIdentical(self.context.getClassByReference(1), cd2)
        self.assertIdentical(self.context.getClassByReference(2), cd3)


class ExceptionEncodingTestCase(ClassCacheClearingTestCase, EncoderMixIn):
    """
    Tests for encoding exceptions.
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        ClassCacheClearingTestCase.setUp(self)
        EncoderMixIn.setUp(self)

    def test_exception(self):
        try:
            raise Exception('foo bar')
        except Exception, e:
            self.encoder.writeElement(e)

        self.assertEqual(self.buf.getvalue(), '\n\x0b\x01\x0fmessage\x06'
            '\x0ffoo bar\tname\x06\x13Exception\x01')

    def test_user_defined(self):
        class FooBar(Exception):
            pass

        try:
            raise FooBar('foo bar')
        except Exception, e:
            self.encoder.writeElement(e)

        self.assertEqual(self.buf.getvalue(), '\n\x0b\x01\x0fmessage\x06'
            '\x0ffoo bar\tname\x06\rFooBar\x01')

    def test_typed(self):
        class XYZ(Exception):
            pass

        pyamf.register_class(XYZ, 'foo.bar')

        try:
            raise XYZ('blarg')
        except Exception, e:
            self.encoder.writeElement(e)

        self.assertEqual(self.buf.getvalue(), '\n\x0b\x0ffoo.bar\x0f'
            'message\x06\x0bblarg\tname\x06\x07XYZ\x01')


class ByteArrayTestCase(unittest.TestCase):
    """
    Tests for L{amf3.ByteArray}
    """

    def test_write_context(self):
        """
        @see: #695
        """
        obj = {'foo': 'bar'}
        b = amf3.ByteArray()

        b.writeObject(obj)

        bytes = b.getvalue()
        b.stream.truncate()

        b.writeObject(obj)
        self.assertEqual(b.getvalue(), bytes)

    def test_context(self):
        b = amf3.ByteArray()
        c = b.context

        obj = {'foo': 'bar'}

        c.addObject(obj)

        b.writeObject(obj)

        self.assertEqual(b.getvalue(), '\n\x0b\x01\x07foo\x06\x07bar\x01')

    def test_read_context(self):
        """
        @see: #695
        """
        obj = {'foo': 'bar'}
        b = amf3.ByteArray()

        b.stream.write('\n\x0b\x01\x07foo\x06\x07bar\x01\n\x00')
        b.stream.seek(0)

        self.assertEqual(obj, b.readObject())
        self.assertRaises(pyamf.ReferenceError, b.readObject)
