# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for L{pyamf.version}
"""

import unittest

from pyamf import versions


class VersionTestCase(unittest.TestCase):
    """
    Tests for L{pyamf.version.get_version}
    """

    def test_version(self):
        self.assertEqual(versions.get_version((0, 0)), '0.0')
        self.assertEqual(versions.get_version((0, 1)), '0.1')
        self.assertEqual(versions.get_version((3, 2)), '3.2')
        self.assertEqual(versions.get_version((3, 2, 1)), '3.2.1')

        self.assertEqual(versions.get_version((3, 2, 1, 'alpha')), '3.2.1alpha')

        self.assertEqual(versions.get_version((3, 2, 1, 'final')), '3.2.1final')

    def test_class(self):
        V = versions.Version

        v1 = V(0, 1)

        self.assertEqual(v1, (0, 1))
        self.assertEqual(str(v1), '0.1')

        v2 = V(3, 2, 1, 'final')

        self.assertEqual(v2, (3, 2, 1, 'final'))
        self.assertEqual(str(v2), '3.2.1final')

        self.assertTrue(v2 > v1)
