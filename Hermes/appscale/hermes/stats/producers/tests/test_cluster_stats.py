import json
import os

from mock import patch, MagicMock
from tornado import testing, gen

from appscale.hermes.stats import converter
from appscale.hermes.stats.converter import IncludeLists
from appscale.hermes.stats.producers import (
  cluster_stats, node_stats, process_stats, proxy_stats
)

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test-data')


def get_stats_from_file(json_file_name, stats_class):
  with open(os.path.join(TEST_DATA_DIR, json_file_name)) as json_file:
    raw_dict = json.load(json_file)
    stats_dict = {
      ip: converter.stats_from_dict(stats_class, snapshot)
      for ip, snapshot in raw_dict.iteritems()
    }
    return raw_dict, stats_dict


class TestClusterNodeStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_nodes_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @patch.object(node_stats.NodeStatsSource, 'get_current')
  @testing.gen_test
  def test_verbose_cluster_node_stats(self, mock_get_current, mock_fetch,
                                      mock_ips_getter, mock_get_private_ip,
                                      mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )
    # Mock local source
    mock_get_current.return_value = stats_test_data['192.168.33.10']
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test
    stats, failures = yield cluster_stats.cluster_nodes_stats.get_current()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_slave.body), {})
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )
    self.assertEqual(failures, {})

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    self.assertIsInstance(local_stats, node_stats.NodeStatsSnapshot)
    self.assertEqual(local_stats.utc_timestamp, 1494248091.0)
    self.assertIsInstance(slave_stats, node_stats.NodeStatsSnapshot)
    self.assertEqual(slave_stats.utc_timestamp, 1494248082.0)

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_nodes_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @patch.object(node_stats.NodeStatsSource, 'get_current')
  @testing.gen_test
  def test_failure_of_node(self, mock_get_current, mock_fetch,
                           mock_ips_getter, mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )[1]
    # Mock local source
    mock_get_current.return_value = stats_test_data['192.168.33.10']
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(code=500, reason="Timeout error")
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test
    stats, failures = yield cluster_stats.cluster_nodes_stats.get_current()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_slave.body), {})
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    self.assertNotIn('192.168.33.11', stats)
    self.assertIsInstance(local_stats, node_stats.NodeStatsSnapshot)
    self.assertEqual(local_stats.utc_timestamp, 1494248091.0)
    self.assertEqual(failures, {'192.168.33.11': '500 Timeout error'})


  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_nodes_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @patch.object(node_stats.NodeStatsSource, 'get_current')
  @testing.gen_test
  def test_filtered_cluster_node_stats(self, mock_get_current, mock_fetch,
                                       mock_ips_getter, mock_get_private_ip,
                                       mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )
    # Mock local source
    mock_get_current.return_value = stats_test_data['192.168.33.10']
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response
    #Prepare raw dict with include lists
    raw_include_lists = {
      'node': ['cpu', 'memory'],
      'node.cpu': ['percent', 'count'],
      'node.memory': ['available']
    }

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get stats with filtered set of fields
    include_lists = IncludeLists(raw_include_lists)
    stats, failures = yield cluster_stats.cluster_nodes_stats.get_current(
      max_age=10, include_lists=include_lists
    )

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_slave.body),
      {
        'max_age': 10,
        'include_lists': raw_include_lists,
      })
    self.assertEqual(
      request_to_slave.url, 'http://192.168.33.11:4378/stats/local/node'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )
    self.assertEqual(failures, {})

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    self.assertIsInstance(local_stats, node_stats.NodeStatsSnapshot)
    self.assertEqual(local_stats.utc_timestamp, 1494248091.0)
    self.assertIsInstance(slave_stats, node_stats.NodeStatsSnapshot)
    self.assertEqual(slave_stats.utc_timestamp, 1494248082.0)


class TestClusterProcessesStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_processes_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @patch.object(process_stats.ProcessesStatsSource, 'get_current')
  @testing.gen_test
  def test_verbose_cluster_processes_stats(self, mock_get_current, mock_fetch,
                                           mock_ips_getter, mock_get_private_ip,
                                           mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )
    # Mock local source
    mock_get_current.return_value = stats_test_data['192.168.33.10']
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats, failures = yield cluster_stats.cluster_processes_stats.get_current()

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_slave.body), {})
    self.assertEqual(
      request_to_slave.url,
      'http://192.168.33.11:4378/stats/local/processes'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )
    self.assertEqual(failures, {})

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    self.assertIsInstance(local_stats, process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(local_stats.processes_stats), 24)
    self.assertEqual(local_stats.utc_timestamp, 1494248000.0)
    self.assertIsInstance(slave_stats, process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(slave_stats.processes_stats), 10)
    self.assertEqual(slave_stats.utc_timestamp, 1494248091.0)

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_processes_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @patch.object(process_stats.ProcessesStatsSource, 'get_current')
  @testing.gen_test
  def test_filtered_cluster_processes_stats(self, mock_get_current, mock_fetch,
                                           mock_ips_getter, mock_get_private_ip,
                                           mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.10', '192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )
    # Mock local source
    mock_get_current.return_value = stats_test_data['192.168.33.10']
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response
    #Prepare raw dict with include lists
    raw_include_lists = {
      'process': ['monit_name', 'unified_service_name', 'application_id',
                  'port', 'cpu', 'memory', 'children_stats_sum'],
      'process.cpu': ['user', 'system', 'percent'],
      'process.memory': ['resident', 'virtual', 'unique'],
      'process.children_stats_sum': ['cpu', 'memory'],
    }

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get stats with filtered set of fields
    include_lists = IncludeLists(raw_include_lists)
    stats, failures = yield cluster_stats.cluster_processes_stats.get_current(
      max_age=15, include_lists=include_lists
    )
    self.assertEqual(failures, {})

    # ASSERTING EXPECTATIONS
    request_to_slave = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_slave.body),
      {
        'max_age': 15,
        'include_lists': raw_include_lists,
      })
    self.assertEqual(
      request_to_slave.url,
      'http://192.168.33.11:4378/stats/local/processes'
    )
    self.assertDictContainsSubset(
      request_to_slave.headers, {'Appscale-Secret': 'secret'}
    )

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    self.assertIsInstance(local_stats, process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(local_stats.processes_stats), 24)
    self.assertEqual(local_stats.utc_timestamp, 1494248000.0)
    self.assertIsInstance(slave_stats, process_stats.ProcessesStatsSnapshot)
    self.assertEqual(len(slave_stats.processes_stats), 10)
    self.assertEqual(slave_stats.utc_timestamp, 1494248091.0)


class TestClusterProxiesStatsProducer(testing.AsyncTestCase):

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_proxies_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_verbose_cluster_proxies_stats(self, mock_fetch, mock_ips_getter,
                                         mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get the latest stats
    stats, failures = yield cluster_stats.cluster_proxies_stats.get_current()

    # ASSERTING EXPECTATIONS
    request_to_lb = mock_fetch.call_args[0][0]
    self.assertEqual(json.loads(request_to_lb.body), {})
    self.assertEqual(
      request_to_lb.url, 'http://192.168.33.11:4378/stats/local/proxies'
    )
    self.assertDictContainsSubset(
      request_to_lb.headers, {'Appscale-Secret': 'secret'}
    )
    self.assertEqual(failures, {})

    lb_stats = stats['192.168.33.11']
    self.assertIsInstance(lb_stats, proxy_stats.ProxiesStatsSnapshot)
    self.assertEqual(len(lb_stats.proxies_stats), 5)
    self.assertEqual(lb_stats.utc_timestamp, 1494248097.0)

  @patch.object(cluster_stats, 'options')
  @patch.object(cluster_stats.appscale_info, 'get_private_ip')
  @patch.object(cluster_stats.cluster_proxies_stats, 'ips_getter')
  @patch.object(cluster_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_filtered_cluster_proxies_stats(self, mock_fetch, mock_ips_getter,
                                          mock_get_private_ip, mock_options):
    # Mock appscale_info functions for getting IPs
    mock_get_private_ip.return_value = '192.168.33.10'
    mock_ips_getter.return_value = ['192.168.33.11']
    # Mock secret
    mock_options.secret = 'secret'
    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]
    #Prepare raw dict with include lists
    raw_include_lists = {
      'proxy': ['name', 'unified_service_name', 'application_id',
                'frontend', 'backend'],
      'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
      'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
    }
    # Mock AsyncHTTPClient.fetch using raw stats dictionaries from test data
    response = MagicMock(body=json.dumps(raw_test_data['192.168.33.11']),
                         code=200, reason='OK')
    future_response = gen.Future()
    future_response.set_result(response)
    mock_fetch.return_value = future_response

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    # Call method under test to get stats with filtered set of fields
    include_lists = IncludeLists(raw_include_lists)
    stats, failures = yield cluster_stats.cluster_proxies_stats.get_current(
      max_age=18, include_lists=include_lists
    )

    # ASSERTING EXPECTATIONS
    request_to_lb = mock_fetch.call_args[0][0]
    self.assertEqual(
      json.loads(request_to_lb.body),
      {
        'max_age': 18,
        'include_lists': raw_include_lists,
      })
    self.assertEqual(
      request_to_lb.url, 'http://192.168.33.11:4378/stats/local/proxies'
    )
    self.assertDictContainsSubset(
      request_to_lb.headers, {'Appscale-Secret': 'secret'}
    )
    self.assertEqual(failures, {})

    lb_stats = stats['192.168.33.11']
    self.assertIsInstance(lb_stats, proxy_stats.ProxiesStatsSnapshot)
    self.assertEqual(len(lb_stats.proxies_stats), 5)
    self.assertEqual(lb_stats.utc_timestamp, 1494248097.0)
