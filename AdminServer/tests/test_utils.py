import unittest

from appscale.admin import utils


class TestUtils(unittest.TestCase):
  def test_apply_mask_to_version(self):
    given_version = {'runtime': 'python27',
                     'appscaleExtensions': {'httpPort': 80}}
    desired_fields = ['appscaleExtensions.httpPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80}})

    given_version = {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}}
    desired_fields = ['appscaleExtensions.httpPort',
                      'appscaleExtensions.httpsPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}})

    given_version = {'runtime': 'python27'}
    desired_fields = ['appscaleExtensions.httpPort',
                      'appscaleExtensions.httpsPort']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields), {})

    given_version = {'runtime': 'python27',
                     'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}}
    desired_fields = ['appscaleExtensions']
    self.assertDictEqual(
      utils.apply_mask_to_version(given_version, desired_fields),
      {'appscaleExtensions': {'httpPort': 80, 'httpsPort': 443}})
