from mock import patch

from appscale.hermes.producers import node_stats


@patch('appscale.common.appscale_info.get_private_ip')
def test_node_stats(mock_get_private_ip):
  # Mocking `get_private_ip`
  mock_get_private_ip.return_value = '10.10.11.12'

  # Calling method under test
  stats = node_stats.NodeStatsSource.get_current()

  # Asserting expectations
  assert isinstance(stats, node_stats.NodeStatsSnapshot)
  assert isinstance(stats.utc_timestamp, float)
  assert stats.private_ip == '10.10.11.12'
  assert isinstance(stats.cpu, node_stats.NodeCPU)
  assert isinstance(stats.memory, node_stats.NodeMemory)
  assert isinstance(stats.swap, node_stats.NodeSwap)
  assert isinstance(stats.disk_io, node_stats.NodeDiskIO)
  assert isinstance(stats.partitions_dict, dict)
  assert isinstance(stats.partitions_dict['/'], node_stats.NodePartition)
  assert isinstance(stats.network, node_stats.NodeNetwork)
  assert isinstance(stats.loadavg, node_stats.NodeLoadAvg)
