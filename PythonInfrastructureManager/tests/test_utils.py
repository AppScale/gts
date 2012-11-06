from unittest.case import TestCase
from utils.utils import flatten, get_random_alphanumeric

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

    def test_random_alphanumeric(self):
        result = get_random_alphanumeric()
        self.assertEquals(len(result), 10)
        for ch in result:
            self.assertTrue(ch.isalnum())

        result = get_random_alphanumeric(15)
        self.assertEqual(len(result), 15)
        for ch in result:
            self.assertTrue(ch.isalnum())
