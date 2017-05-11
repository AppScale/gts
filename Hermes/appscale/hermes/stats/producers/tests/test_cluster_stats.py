import json
import os

from mock import patch, MagicMock
from tornado import testing, gen

from appscale.hermes.stats.producers import (
  cluster_stats, node_stats, process_stats, proxy_stats,
  converter)
from appscale.hermes.stats.subscribers import cache

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test-data')


def get_stats_from_file(json_file_name, stats_class):
  with open(os.path.join(TEST_DATA_DIR, json_file_name)) as json_file:
    raw_dict = json.load(json_file)
    stats_dict = {
      ip: [
        converter.stats_from_dict(stats_class, snapshot)
        for snapshot in snapshots
      ]
      for ip, snapshots in raw_dict.iteritems()
    }
    return raw_dict, stats_dict


class TestClusterNodeStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_all_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_verbose_cluster_node_stats(self, mock_fetch, mock_get_all_ips,
                                      mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_all_ips.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )

    # Initialize stats source
    local_cache = cache.StatsCache(10)
    cluster_stats_source = cluster_stats.ClusterNodesStatsSource(local_cache)

    # === The first request for cluster stats ===

    # Put list of NodeStatsSnapshot into local cache
    local_cache.bulk_receive(stats_test_data['192.168.33.10'][0:2])

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11'][0:1]))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test the first time
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_slave.body), {})
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node/cache'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']

    self.assertEqual(len(local_stats), 2)
    self.assertIsInstance(local_stats[0], node_stats.NodeStatsSnapshot)
    self.assertEqual(local_stats[0].utc_timestamp, 1494248091.0)
    self.assertEqual(local_stats[1].utc_timestamp, 1494248150.0)

    self.assertEqual(len(slave_stats), 1)
    self.assertIsInstance(slave_stats[0], node_stats.NodeStatsSnapshot)
    self.assertEqual(slave_stats[0].utc_timestamp, 1494248082.0)

    # === The second request for cluster stats ===

    # Put list of NodeStatsSnapshot into local cache
    local_cache.bulk_receive(stats_test_data['192.168.33.10'][2:3])

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11'][1:3]))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_slave.body), {'last_utc_timestamp': 1494248082.0}
    )
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node/cache'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']

    self.assertEqual(len(local_stats), 1)
    self.assertEqual(local_stats[0].utc_timestamp, 1494248198.0)

    self.assertEqual(len(slave_stats), 2)
    self.assertEqual(slave_stats[0].utc_timestamp, 1494248136.0)
    self.assertEqual(slave_stats[1].utc_timestamp, 1494248187.0)

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_all_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_filtered_cluster_node_stats(self, mock_fetch, mock_get_all_ips,
                                       mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_all_ips.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )

    # Initialize stats source
    local_cache = cache.StatsCache(10)
    include_lists = {
      'node': ['cpu', 'memory'],
      'node.cpu': ['percent', 'count'],
      'node.memory': ['available']
    }
    cluster_stats_source = cluster_stats.ClusterNodesStatsSource(
      local_cache, include_lists=include_lists, limit=1, fetch_latest_only=True
    )

    # Put list of NodeStatsSnapshot into local cache
    local_cache.bulk_receive(stats_test_data['192.168.33.10'])

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11'][2:3]))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_slave.body),
      {
        'limit': 1,
        'include_lists': include_lists,
        'fetch_latest_only': True
      })
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node/cache'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']

    self.assertEqual(len(local_stats), 1)
    self.assertEqual(len(slave_stats), 1)


class TestClusterProcessesStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_all_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_verbose_cluster_processes_stats(self, mock_fetch, mock_get_all_ips,
                                           mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_all_ips.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )

    # Initialize stats source
    local_cache = cache.StatsCache(10)
    cluster_stats_source = cluster_stats.ClusterProcessesStatsSource(local_cache)

    # Put list of ProcessesStatsSnapshot into local cache
    local_cache.bulk_receive(stats_test_data['192.168.33.10'])

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_slave.body), {})
    self.assertEqual(
      request_to_slave.url,
      'http://192.168.33.11:4378/stats/local/processes/cache'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']

    self.assertEqual(len(local_stats), 1)
    self.assertIsInstance(local_stats[0], process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(local_stats[0].processes_stats), 24)
    self.assertEqual(local_stats[0].utc_timestamp, 1494248000.0)

    self.assertEqual(len(slave_stats), 1)
    self.assertIsInstance(slave_stats[0], process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(slave_stats[0].processes_stats), 10)
    self.assertEqual(slave_stats[0].utc_timestamp, 1494248091.0)

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_all_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_filtered_cluster_processes_stats(self, mock_fetch, mock_get_all_ips,
                                            mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_all_ips.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )

    # Initialize stats source
    local_cache = cache.StatsCache(10)
    include_lists = {
      'process': ['monit_name', 'unified_service_name', 'application_id',
                  'port', 'cpu', 'memory', 'children_stats_sum'],
      'process.cpu': ['user', 'system', 'percent'],
      'process.memory': ['resident', 'virtual', 'unique'],
      'process.children_stats_sum': ['cpu', 'memory'],
    }
    cluster_stats_source = cluster_stats.ClusterProcessesStatsSource(
      local_cache, include_lists=include_lists, limit=1, fetch_latest_only=True
    )

    # Put list of ProcessesStatsSnapshot into local cache
    local_cache.bulk_receive(stats_test_data['192.168.33.10'])

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_slave.body),
      {
        'limit': 1,
        'include_lists': include_lists,
        'fetch_latest_only': True
      })
    self.assertEqual(
      request_to_slave.url,
      'http://192.168.33.11:4378/stats/local/processes/cache'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']

    self.assertEqual(len(local_stats), 1)
    self.assertEqual(len(slave_stats), 1)


class TestClusterProxiesStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_load_balancer_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_verbose_cluster_proxies_stats(self, mock_fetch, mock_get_lb_ips,
                                         mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_lb_ips.return_value = ['192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]

    # Initialize stats source
    cluster_stats_source = cluster_stats.ClusterProxiesStatsSource()

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_lb = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_lb.body), {})
    self.assertEqual(
      request_to_lb.url, 'http://192.168.33.11:4378/stats/local/proxies/cache'
    )
    self.assertDictContainsSubset(
      request_to_lb.headers, {'Appscale-Secret': 'secret'}
    )

    lb_stats = stats['192.168.33.11']

    self.assertEqual(len(lb_stats), 1)
    self.assertIsInstance(lb_stats[0], proxy_stats.ProxiesStatsSnapshot)
    self.assertEqual(len(lb_stats[0].proxies_stats), 5)
    self.assertEqual(lb_stats[0].utc_timestamp, 1494248097.0)


  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.appscale_info, 'get_load_balancer_ips')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_filtered_cluster_proxies_stats(self, mock_fetch, mock_get_lb_ips,
                                          mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_get_lb_ips.return_value = ['192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'

    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]

    # Initialize stats source
    include_lists = {
      'proxy': ['name', 'unified_service_name', 'application_id',
                'frontend', 'backend'],
      'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
      'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
    }
    cluster_stats_source = cluster_stats.ClusterProxiesStatsSource(
      include_lists=include_lists, limit=1, fetch_latest_only=True
    )

    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']))
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats = yield cluster_stats_source.get_current_async()

    # ASSERTING EXPECTATIONS
    request_to_lb = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_lb.body),
      {
        'limit': 1,
        'include_lists': include_lists,
        'fetch_latest_only': True
      })
    self.assertEqual(
      request_to_lb.url, 'http://192.168.33.11:4378/stats/local/proxies/cache'
    )
    self.assertDictContainsSubset(
      request_to_lb.headers, {'Appscale-Secret': 'secret'}
    )

    lb_stats = stats['192.168.33.11']
    self.assertEqual(len(lb_stats), 1)
