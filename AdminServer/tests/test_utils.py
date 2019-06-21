import unittest

from appscale.admin import utils
from appscale.admin.constants import InvalidQueueConfiguration


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

  def test_validate_queue(self):
    valid_queues = [
      {'name': 'queue-1', 'rate': '5/s'},
      {'name': 'fooqueue', 'rate': '1/s',
       'retry_parameters': {'task_retry_limit': 7, 'task_age_limit': '2d'}},
      {'name': 'fooqueue', 'mode': 'pull'}
    ]
    invalid_queues = [
      {'name': 'a' * 101, 'rate': '5/s'},  # Name is too long.
      {'name': '*', 'rate': '5/s'},  # Invalid characters in name.
      {'name': 'fooqueue', 'rate': '5/y'},  # Invalid unit of time.
      {'name': 'fooqueue'},  # Push queues must specify rate.
      {'name': 'fooqueue', 'mode': 'pull',
       'retry_parameters': {'task_retry_limit': 'a'}}  # Invalid retry value.
    ]
    for queue in valid_queues:
      utils.validate_queue(queue)

    for queue in invalid_queues:
      self.assertRaises(InvalidQueueConfiguration, utils.validate_queue, queue)
