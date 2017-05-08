import json
from mock import patch, MagicMock, Mock
from tornado import testing

from appscale.hermes.stats.producers import (
  cluster_stats, node_stats, process_stats, proxy_stats
)
from appscale.hermes.stats.subscribers import cache


def get_stats_from_file(json_file_name, node_ip, from_dict_converter):
  with open(json_file_name) as json_file:
    per_node_stats_dict = {
      node_ip: from_dict_converter(per_node_stats_dict)
      for node_ip, in json.load(json_file).iteritems()
    }


class TestCurrentClusterNodeStats(testing.AsyncTestCase):

  @testing.gen_test
  @patch.object(node_stats.appscale_info, 'get_private_ip')
  @patch.object(node_stats.appscale_info, 'get_all_ips')
  def test_verbose_cluster_node_stats(self, mock_get_all_ips,
                                      mock_get_private_ip):
    # Mocking appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_all_ips.return_value = ['192.168.33.10', '192.168.33.11']

    # Mocking local node stats cache
    local_cache = MagicMock(spec=cache.StatsCache)
    local_cache.get_stats_after.return_value = [

    ]

    # Calling method under test
    stats = cluster_stats.ClusterNodesStatsSource(local_cache).get_current_async()

    # Asserting expectations
    self.assertIsInstance(stats, dict)
    for key, value in stats.iteritems():
      self.assertIsInstance(key, str)  # key should be node IP
      self.assertIsInstance(value, str)  #
    self.assertIsInstance(stats.utc_timestamp, float)
    self.assertEqual(stats.private_ip, '10.10.11.12')
    self.assertIsInstance(stats.cpu, node_stats.NodeCPU)
    self.assertIsInstance(stats.memory, node_stats.NodeMemory)
    self.assertIsInstance(stats.swap, node_stats.NodeSwap)
    self.assertIsInstance(stats.disk_io, node_stats.NodeDiskIO)
    self.assertIsInstance(stats.partitions_dict, dict)
    self.assertIsInstance(stats.partitions_dict['/'], node_stats.NodePartition)
    self.assertIsInstance(stats.network, node_stats.NodeNetwork)
    self.assertIsInstance(stats.loadavg, node_stats.NodeLoadAvg)
