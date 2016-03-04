import json
from flexmock import flexmock
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

from system_manager import JSONTags
from system_manager import SystemManager
from utils import utils


class TestInfrastructureManager(TestCase):

  def test_get_cpu_usage(self):
    flexmock(utils).should_receive("get_secret").and_return("fake secret")

    expected_keys = [
      JSONTags.CPU, JSONTags.IDLE, JSONTags.SYSTEM, JSONTags.USER
    ]
    actual = json.loads(SystemManager().get_cpu_usage("fake secret"))
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_disk_usage(self):
    flexmock(utils).should_receive("get_secret").and_return("fake secret")

    expected_keys = [
      JSONTags.DISK, JSONTags.FREE, JSONTags.USED
    ]
    actual = json.loads(SystemManager().get_disk_usage("fake secret"))
    actual_keys = [actual.keys()[0]]

    # Example: {'disk': [ {'/': {'used': 3513118720, 'free': 5747404800}} ]}
    if len(actual.values()[0]) > 0:
      for key in actual.values()[0][0].values()[0].keys():
        actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_memory_usage(self):
    flexmock(utils).should_receive("get_secret").and_return("fake secret")

    expected_keys = [
      JSONTags.MEMORY, JSONTags.AVAILABLE, JSONTags.USED
    ]
    actual = json.loads(SystemManager().get_memory_usage("fake secret"))
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_swap_usage(self):
    flexmock(utils).should_receive("get_secret").and_return("fake secret")

    expected_keys = [
      JSONTags.SWAP, JSONTags.FREE, JSONTags.USED
    ]
    actual = json.loads(SystemManager().get_swap_usage("fake secret"))
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))
