# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for AMF utilities.

@since: 0.1.0
"""

import unittest

import pyamf
from pyamf import codec

try:
    unicode
except NameError:
    # py3k
    unicode = str
    str = bytes


class TestObject(object):
    def __init__(self):
        self.name = 'test'


class DummyAlias(pyamf.ClassAlias):
    pass


class IndexedCollectionTestCase(unittest.TestCase):
    """
    Tests for L{codec.IndexedCollection}
    """

    def setUp(self):
        self.collection = codec.IndexedCollection()

    def test_clear(self):
        o = object()

        self.assertEqual(self.collection.getReferenceTo(o), -1)

        self.collection.append(o)
        self.assertEqual(self.collection.getReferenceTo(o), 0)

        self.collection.clear()

        self.assertEqual(self.collection.getReferenceTo(o), -1)

    def test_append(self):
        n = 5

        for i in range(0, n):
            test_obj = TestObject()

            test_obj.name = i

            self.collection.append(test_obj)

        self.assertEqual(len(self.collection), n)

        for i in range(0, n):
            self.assertEqual(i, self.collection[i].name)

    def test_get_reference_to(self):
        test_obj = TestObject()

        self.collection.append(test_obj)

        idx = self.collection.getReferenceTo(test_obj)

        self.assertEqual(0, idx)
        self.assertEqual(-1, self.collection.getReferenceTo(TestObject()))

    def test_get_by_reference(self):
        test_obj = TestObject()
        idx = self.collection.append(test_obj)

        self.assertIdentical(test_obj, self.collection.getByReference(idx))

        idx = self.collection.getReferenceTo(test_obj)

        self.assertIdentical(test_obj, self.collection.getByReference(idx))
        self.assertRaises(TypeError, self.collection.getByReference, 'bad ref')

        self.assertEqual(None, self.collection.getByReference(74))

    def test_len(self):
        self.assertEqual(0, len(self.collection))

        self.collection.append([])

        self.assertEqual(1, len(self.collection))

        self.collection.append({})

        self.assertEqual(2, len(self.collection))

        self.collection.clear()
        self.assertEqual(0, len(self.collection))

    def test_repr(self):
        x = "0x%x" % id(self.collection)

        self.assertEqual(repr(self.collection),
            '<pyamf.codec.IndexedCollection size=0 %s>' % (x,))

    def test_contains(self):
        o = object()

        self.assertFalse(o in self.collection)

        self.collection.append(o)

        self.assertTrue(o in self.collection)

    def test_eq(self):
        self.assertEqual(self.collection, [])
        self.assertRaises(NotImplementedError, self.collection.__eq__, self)

    def test_hash(self):
        class A(object):
            def __hash__(self):
                return 1

        self.collection = codec.IndexedCollection(True)

        o = A()

        self.assertEqual(self.collection.getReferenceTo(o), -1)

        self.collection.append(o)
        self.assertEqual(self.collection.getReferenceTo(o), 0)

        self.collection.clear()

        self.assertEqual(self.collection.getReferenceTo(o), -1)


class ContextTestCase(unittest.TestCase):
    """
    Tests for L{codec.Context}
    """

    def setUp(self):
        self.context = codec.Context()

    def test_add(self):
        y = [1, 2, 3]

        self.assertEqual(self.context.getObjectReference(y), -1)
        self.assertEqual(self.context.addObject(y), 0)
        self.assertEqual(self.context.getObjectReference(y), 0)

    def test_clear(self):
        y = [1, 2, 3]

        self.context.addObject(y)

        self.assertEqual(self.context.getObjectReference(y), 0)

        self.context.clear()

        self.assertEqual(self.context.getObjectReference(y), -1)

    def test_get_by_reference(self):
        y = [1, 2, 3]
        z = {'spam': 'eggs'}

        self.context.addObject(y)
        self.context.addObject(z)

        self.assertIdentical(self.context.getObject(0), y)
        self.assertIdentical(self.context.getObject(1), z)
        self.assertIdentical(self.context.getObject(2), None)

        for t in ['', 2.2323]:
            self.assertRaises(TypeError, self.context.getObject, t)

    def test_get_reference(self):
        y = [1, 2, 3]
        z = {'spam': 'eggs'}

        ref1 = self.context.addObject(y)
        ref2 = self.context.addObject(z)

        self.assertIdentical(self.context.getObjectReference(y), ref1)
        self.assertIdentical(self.context.getObjectReference(z), ref2)
        self.assertEqual(self.context.getObjectReference({}), -1)

    def test_no_alias(self):
        class A:
            pass

        alias = self.context.getClassAlias(A)

        self.assertTrue(isinstance(alias, pyamf.ClassAlias))
        self.assertIdentical(alias.klass, A)

    def test_registered_alias(self):
        class A:
            pass

        pyamf.register_class(A)
        self.addCleanup(pyamf.unregister_class, A)

        alias = self.context.getClassAlias(A)

        self.assertTrue(isinstance(alias, pyamf.ClassAlias))
        self.assertIdentical(alias.klass, A)

    def test_registered_deep(self):
        class A:
            pass

        class B(A):
            pass

        pyamf.register_alias_type(DummyAlias, A)
        self.addCleanup(pyamf.unregister_alias_type, DummyAlias)
        alias = self.context.getClassAlias(B)

        self.assertTrue(isinstance(alias, DummyAlias))
        self.assertIdentical(alias.klass, B)

    def test_get_class_alias(self):
        class A:
            pass

        alias1 = self.context.getClassAlias(A)
        alias2 = self.context.getClassAlias(A)

        self.assertIdentical(alias1, alias2)

    def test_string(self):
        s = 'foo'.encode('ascii')
        u = self.context.getStringForBytes(s)

        self.assertTrue(type(u) is unicode)
        self.assertEqual(u, s.decode('ascii'))

        i = self.context.getStringForBytes(s)

        self.assertIdentical(u, i)

        self.context.clear()

        i = self.context.getStringForBytes(s)

        self.assertFalse(u is i)

    def test_bytes(self):
        s = 'foo'.decode('ascii')

        b = self.context.getBytesForString(s)

        self.assertTrue(type(b) is str)
        self.assertEqual(b, s.encode('ascii'))

        i = self.context.getBytesForString(s)

        self.assertIdentical(i, b)

        self.context.clear()

        i = self.context.getBytesForString(s)

        self.assertNotIdentical(i, s)
