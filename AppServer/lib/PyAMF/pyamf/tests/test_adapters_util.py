# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for the adapters.util module.

@since: 0.4
"""

import unittest

from pyamf.adapters import util

# check for set function in python 2.3
import __builtin__

if not hasattr(__builtin__, 'set'):
    from sets import Set as set


class Iterable(object):
    """
    A generic iterable class that supports .. iterating.
    """

    def __init__(self, iterable):
        self.iterable = iterable

    def __iter__(self):
        return iter(self.iterable)

    def keys(self):
        return self.iterable.keys()

    def values(self):
        return self.iterable.values()

    def __getitem__(self, name):
        return self.iterable.__getitem__(name)


class HelperTestCase(unittest.TestCase):
    def setUp(self):
        self.encoder = object()

    def test_to_list(self):
        self.assertEqual(util.to_list(Iterable([1, 2, 3]), self.encoder), [1, 2, 3])
        self.assertEqual(util.to_list(['a', 'b'], self.encoder), ['a', 'b'])
        self.assertEqual(util.to_list('a', self.encoder), ['a'])

        obj = object()
        self.assertRaises(TypeError, util.to_list, obj, self.encoder)

    def test_to_set(self):
        self.assertEqual(util.to_set(Iterable([1, 2, 3]), self.encoder), set([1, 2, 3]))
        self.assertEqual(util.to_set(['a', 'b'], self.encoder), set(['a', 'b']))
        self.assertEqual(util.to_set('a', self.encoder), set('a'))

        obj = object()
        self.assertRaises(TypeError, util.to_set, obj, self.encoder)

    def test_to_dict(self):
        self.assertEqual(util.to_dict(Iterable({'a': 'b'}), self.encoder), {'a': 'b'})

        obj = object()
        self.assertRaises(TypeError, util.to_dict, obj, self.encoder)

    def test_to_tuple(self):
        self.assertEqual(util.to_tuple(Iterable((1, 2, 3)), self.encoder), (1, 2, 3))

        obj = object()
        self.assertRaises(TypeError, util.to_tuple, obj, self.encoder)
