from os import environ
from unittest.case import TestCase
from utils.utils import flatten, get_random_alphanumeric, obscure_string, get_obscured_env

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

    def test_obscure_string(self):
        result = obscure_string('1234567890')
        self.assertEquals(result, '******7890')
        result = obscure_string(None)
        self.assertTrue(result is None)
        result = obscure_string('123')
        self.assertEquals(result, '123')
        result = obscure_string('abcd')
        self.assertEquals(result, 'abcd')

    def test_get_obscured_env(self):
        result = get_obscured_env()
        self.assertTrue(result is not None and len(result) > 0)

        environ['TEST_VAR_1'] = 'forward_unto_dawn'
        environ['TEST_VAR_2'] = 'truth_and_reconciliation'
        result = get_obscured_env()
        self.assertTrue(result.find('forward_unto_dawn') != -1)
        self.assertTrue(result.find('truth_and_reconciliation') != -1)

        result = get_obscured_env(['TEST_VAR_1'])
        self.assertTrue(result.find('TEST_VAR_1=*************dawn') != -1)
        self.assertTrue(result.find('forward_unto_dawn') == -1)

        result = get_obscured_env(['TEST_VAR_1', 'TEST_VAR_2'])
        self.assertTrue(result.find('TEST_VAR_1=*************dawn') != -1)
        self.assertTrue(result.find('TEST_VAR_2=********************tion') != -1)
        self.assertTrue(result.find('forward_unto_dawn') == -1)
        self.assertTrue(result.find('truth_and_reconciliation') == -1)

        original = get_obscured_env()
        result = get_obscured_env(['NON_EXISTING_BOGUS_VARIABLE'])
        self.assertEquals(original, result)



