import unittest

from stats import node

from mock import patch


class TestCurrentNodeStats(unittest.TestCase):

  @patch.object(node.appscale_info, 'get_private_ip')
  def test_node_stats(self, mock_get_private_ip):
    # Mocking `get_private_ip`
    mock_get_private_ip.return_value = '10.10.11.12'

    # Calling method under test
    stats = node.NodeStats.current()

    # Asserting expectations
    self.assertIsInstance(stats, node.NodeStats)
    self.assertIsInstance(stats.utc_timestamp, float)
    self.assertEqual(stats.private_ip, '10.10.11.12')
    self.assertIsInstance(stats.cpu, node.NodeCPU)
    self.assertIsInstance(stats.memory, node.NodeMemory)
    self.assertIsInstance(stats.swap, node.NodeSwap)
    self.assertIsInstance(stats.disk_io, node.NodeDiskIO)
    self.assertIsInstance(stats.partitions_dict, dict)
    self.assertIsInstance(stats.partitions_dict['/'], node.NodePartition)
    self.assertIsInstance(stats.network, node.NodeNetwork)
    self.assertIsInstance(stats.loadavg, node.NodeLoadAvg)
