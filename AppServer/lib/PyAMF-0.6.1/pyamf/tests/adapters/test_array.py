# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for the L{array} L{pyamf.adapters._array} module.

@since: 0.5
"""

try:
    import array
except ImportError:
    array = None

import unittest

import pyamf


class ArrayTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        if not array:
            self.skipTest("'array' not available")

        self.orig = ['f', 'o', 'o']

        self.obj = array.array('c')

        self.obj.append('f')
        self.obj.append('o')
        self.obj.append('o')

    def encdec(self, encoding):
        return pyamf.decode(pyamf.encode(self.obj, encoding=encoding),
            encoding=encoding).next()

    def test_amf0(self):
        self.assertEqual(self.encdec(pyamf.AMF0), self.orig)

    def test_amf3(self):
        self.assertEqual(self.encdec(pyamf.AMF3), self.orig)
