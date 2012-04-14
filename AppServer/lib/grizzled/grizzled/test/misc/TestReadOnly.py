#!/usr/bin/python2.4
# $Id: 5a432ced2c81b94f1e4793cbec98258787f6bc92 $

"""
Tester.
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import google3
from grizzled.misc import ReadOnly, ReadOnlyObjectError

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class Something(object):
    def __init__(self, a=1, b=2):
        self.a = a
        self.b = b

class TestReadOnly(object):

    def setUp(self):
        self.something = Something(10, 20)
        assert self.something.a == 10
        assert self.something.b == 20

        self.something.a += 1
        assert self.something.a == 11

        self.r = ReadOnly(self.something)

    def testClassAttr(self):
        assert self.r.__class__ is Something

    def testIsinstance(self):
        assert isinstance(self.r, Something)

    def testReadOnlyAccess1(self):
        try:
            self.r.a += 1
            assert False, 'Expected a ReadOnlyObjectError'
        except ReadOnlyObjectError, ex:
            print 'Got expected %s' % ex

    def testReadOnlyAccess2(self):
        try:
            self.r.a = 200
            assert False, 'Expected a ReadOnlyObjectError'
        except ReadOnlyObjectError, ex:
            print 'Got expected %s' % ex
