import unittest

from mock import patch

from appscale.hermes.stats import models
from appscale.hermes.stats.producers import node_stats


class TestCurrentNodeStats(unittest.TestCase):

  @patch.object(node_stats.appscale_info, 'get_private_ip')
  def test_node_stats(self, mock_get_private_ip):
    # Mocking `get_private_ip`
    mock_get_private_ip.return_value = '10.10.11.12'

    # Calling method under test
    stats = node_stats.NodeStatsSource.get_current()

    # Asserting expectations
    self.assertIsInstance(stats, models.NodeStatsSnapshot)
    self.assertIsInstance(stats.utc_timestamp, float)
    self.assertEqual(stats.private_ip, '10.10.11.12')
    self.assertIsInstance(stats.cpu, models.NodeCPU)
    self.assertIsInstance(stats.memory, models.NodeMemory)
    self.assertIsInstance(stats.swap, models.NodeSwap)
    self.assertIsInstance(stats.disk_io, models.NodeDiskIO)
    self.assertIsInstance(stats.partitions_dict, dict)
    self.assertIsInstance(stats.partitions_dict['/'], models.NodePartition)
    self.assertIsInstance(stats.network, models.NodeNetwork)
    self.assertIsInstance(stats.loadavg, models.NodeLoadAvg)
