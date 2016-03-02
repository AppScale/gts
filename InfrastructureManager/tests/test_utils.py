from utils import utils
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

class TestUtils(TestCase):

  def test_flatten(self):
    ref = ['foo', 'bar', '123']
    result = utils.flatten(ref)
    self.assertEquals(ref, result)

    result = utils.flatten(['foo', ['bar', '123']])
    self.assertEquals(ref, result)

    result = utils.flatten([['foo'], ['bar', '123']])
    self.assertEquals(ref, result)

  def test_random_alphanumeric(self):
    result = utils.get_random_alphanumeric()
    self.assertEquals(len(result), 10)
    for ch in result:
      self.assertTrue(ch.isalnum())

    result = utils.get_random_alphanumeric(15)
    self.assertEqual(len(result), 15)
    for ch in result:
      self.assertTrue(ch.isalnum())

  def test_obscure_string(self):
    result = utils.obscure_string('1234567890')
    self.assertEquals(result, '******7890')
    result = utils.obscure_string(None)
    self.assertTrue(result is None)
    result = utils.obscure_string('123')
    self.assertEquals(result, '123')
    result = utils.obscure_string('abcd')
    self.assertEquals(result, 'abcd')
