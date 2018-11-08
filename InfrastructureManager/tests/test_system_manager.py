import json
from flexmock import flexmock
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

from appscale.infrastructure.system_manager import (StatsKeys, SystemManager)


class TestInfrastructureManager(TestCase):

  def test_get_cpu_usage(self):
    expected_keys = [StatsKeys.CPU, StatsKeys.IDLE, StatsKeys.SYSTEM,
                     StatsKeys.USER, StatsKeys.COUNT]
    actual = SystemManager().get_cpu_usage()
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_disk_usage(self):
    expected_keys = [
      StatsKeys.TOTAL, StatsKeys.FREE, StatsKeys.USED
    ]
    actual = SystemManager().get_disk_usage()
    actual_keys = []

    # Example: {'disk': [ {'/': {'used': 3513118720, 'free': 5747404800}} ]}
    if len(actual.values()[0]) > 0:
      for key in actual.values()[0][0].values()[0].keys():
        actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_memory_usage(self):
    expected_keys = [
      StatsKeys.MEMORY, StatsKeys.AVAILABLE, StatsKeys.USED, StatsKeys.TOTAL
    ]
    actual = SystemManager().get_memory_usage()
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))

  def test_get_swap_usage(self):
    expected_keys = [
      StatsKeys.SWAP, StatsKeys.FREE, StatsKeys.USED
    ]
    actual = SystemManager().get_swap_usage()
    actual_keys = [actual.keys()[0]]
    for key in actual.values()[0].keys():
      actual_keys.append(key)

    self.assertSetEqual(set(expected_keys), set(actual_keys))
