from unittest.case import TestCase
from utils.utils import flatten

__author__ = 'hiranya'

class TestUtils(TestCase):
    def test_flatten(self):
        ref = [ 'foo', 'bar', '123' ]
        result = flatten(ref)
        self.assertEquals(ref, result)

        result = flatten([ 'foo', [ 'bar', '123' ] ])
        self.assertEquals(ref, result)

        result = flatten([ ['foo'], [ 'bar', '123' ]])
        self.assertEquals(ref, result)
