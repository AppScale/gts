import asyncio
import contextlib
import json
import os

import aiohttp
import pytest
from mock import patch, MagicMock

from appscale.hermes import converter, constants
from appscale.hermes.converter import IncludeLists
from appscale.hermes.producers import (
  cluster_stats, node_stats, process_stats, proxy_stats
)

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test-data')


def future(value=None):
  future_obj = asyncio.Future()
  future_obj.set_result(value)
  return future_obj


class AsyncContextMock(MagicMock):
  async def __aenter__(self):
    return self.aenter

  async def __aexit__(self, exc_type, exc_val, exc_tb):
    return None


def get_stats_from_file(json_file_name, stats_class):
  with open(os.path.join(TEST_DATA_DIR, json_file_name)) as json_file:
    raw_dict = json.load(json_file)
    stats_dict = {
      ip: converter.stats_from_dict(stats_class, snapshot)
      for ip, snapshot in raw_dict.items()
    }
    return raw_dict, stats_dict


class TestClusterNodeStatsProducer:

  @staticmethod
  @pytest.mark.asyncio
  async def test_verbose_cluster_nodes_stats():
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_nodes_stats.ips_getter',
      return_value=['192.168.33.10', '192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.node_stats.NodeStatsSource.get_current',
      return_value=stats_test_data['192.168.33.10']
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      stack.enter_context(local_stats_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test
      stats, failures = await cluster_stats.cluster_nodes_stats.get_current()

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/node',
      headers={'Appscale-Secret': 'secret'},
      json={}, timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    assert isinstance(local_stats, node_stats.NodeStatsSnapshot)
    assert local_stats.utc_timestamp == 1494248091.0
    assert isinstance(slave_stats, node_stats.NodeStatsSnapshot)
    assert slave_stats.utc_timestamp == 1494248082.0

  @staticmethod
  @pytest.mark.asyncio
  async def test_remote_failure():
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_nodes_stats.ips_getter',
      return_value=['192.168.33.10', '192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.node_stats.NodeStatsSource.get_current',
      return_value=stats_test_data['192.168.33.10']
    )
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      side_effect=aiohttp.ClientError('HTTP 504: Gateway Timeout')
    )

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      stack.enter_context(local_stats_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test
      stats, failures = await cluster_stats.cluster_nodes_stats.get_current()

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/node',
      headers={'Appscale-Secret': 'secret'},
      json={}, timeout=constants.REMOTE_REQUEST_TIMEOUT
    )

    local_stats = stats['192.168.33.10']
    assert '192.168.33.11' not in stats
    assert isinstance(local_stats, node_stats.NodeStatsSnapshot)
    assert local_stats.utc_timestamp == 1494248091.0
    assert failures == {'192.168.33.11': 'HTTP 504: Gateway Timeout'}

  @staticmethod
  @pytest.mark.asyncio
  async def test_local_failure():
    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_nodes_stats.ips_getter',
      return_value=['192.168.33.10']
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.node_stats.NodeStatsSource.get_current',
      side_effect=ValueError("Something strange \u2234")
    )

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(local_stats_patcher)
      # Call method under test
      stats, failures = await cluster_stats.cluster_nodes_stats.get_current()

    # ASSERTING EXPECTATIONS
    assert stats == {}
    assert failures == {'192.168.33.10': "Something strange \u2234"}

  @staticmethod
  @pytest.mark.asyncio
  async def test_filtered_cluster_nodes_stats():
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'node-stats.json', node_stats.NodeStatsSnapshot
    )

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_nodes_stats.ips_getter',
      return_value=['192.168.33.10', '192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.node_stats.NodeStatsSource.get_current',
      return_value=stats_test_data['192.168.33.10']
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )

    # Prepare raw dict with include lists
    raw_include_lists = {
      'node': ['cpu', 'memory'],
      'node.cpu': ['percent', 'count'],
      'node.memory': ['available']
    }

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      stack.enter_context(local_stats_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test to get stats with filtered set of fields
      include_lists = IncludeLists(raw_include_lists)
      stats, failures = await cluster_stats.cluster_nodes_stats.get_current(
        max_age=10, include_lists=include_lists
      )

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/node',
      headers={'Appscale-Secret': 'secret'},
      json={
        'max_age': 10,
        'include_lists': raw_include_lists,
      },
      timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    assert isinstance(local_stats, node_stats.NodeStatsSnapshot)
    assert local_stats.utc_timestamp == 1494248091.0
    assert isinstance(slave_stats, node_stats.NodeStatsSnapshot)
    assert slave_stats.utc_timestamp == 1494248082.0


class TestClusterProcessesStatsProducer:

  @staticmethod
  @pytest.mark.asyncio
  async def test_verbose_cluster_processes_stats():
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_processes_stats.ips_getter',
      return_value=['192.168.33.10', '192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.process_stats.ProcessesStatsSource.get_current',
      return_value=stats_test_data['192.168.33.10']
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      stack.enter_context(local_stats_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test
      stats, failures = await cluster_stats.cluster_processes_stats.get_current()

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/processes',
      headers={'Appscale-Secret': 'secret'},
      json={}, timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    assert isinstance(local_stats, process_stats.ProcessesStatsSnapshot)
    assert len(local_stats.processes_stats) == 24
    assert local_stats.utc_timestamp == 1494248000.0
    assert isinstance(slave_stats, process_stats.ProcessesStatsSnapshot)
    assert len(slave_stats.processes_stats) == 10
    assert slave_stats.utc_timestamp == 1494248091.0

  @staticmethod
  @pytest.mark.asyncio
  async def test_filtered_cluster_processes_stats():
    # Read test data from json file
    raw_test_data, stats_test_data = get_stats_from_file(
      'processes-stats.json', process_stats.ProcessesStatsSnapshot
    )

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_processes_stats.ips_getter',
      return_value=['192.168.33.10', '192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    local_stats_patcher = patch(
      'appscale.hermes.producers.process_stats.ProcessesStatsSource.get_current',
      return_value=stats_test_data['192.168.33.10']
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )

    # Prepare raw dict with include lists
    raw_include_lists = {
      'process': ['monit_name', 'unified_service_name', 'application_id',
                  'port', 'cpu', 'memory', 'children_stats_sum'],
      'process.cpu': ['user', 'system', 'percent'],
      'process.memory': ['resident', 'virtual', 'unique'],
      'process.children_stats_sum': ['cpu', 'memory'],
    }

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      stack.enter_context(local_stats_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test to get stats with filtered set of fields
      include_lists = IncludeLists(raw_include_lists)
      stats, failures = await cluster_stats.cluster_processes_stats.get_current(
        max_age=15, include_lists=include_lists
      )

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/processes',
      headers={'Appscale-Secret': 'secret'},
      json={
        'max_age': 15,
        'include_lists': raw_include_lists,
      },
      timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    local_stats = stats['192.168.33.10']
    slave_stats = stats['192.168.33.11']
    assert isinstance(local_stats, process_stats.ProcessesStatsSnapshot)
    assert len(local_stats.processes_stats) == 24
    assert local_stats.utc_timestamp == 1494248000.0
    assert isinstance(slave_stats, process_stats.ProcessesStatsSnapshot)
    assert len(slave_stats.processes_stats) == 10
    assert slave_stats.utc_timestamp == 1494248091.0


class TestClusterProxiesStatsProducer:

  @staticmethod
  @pytest.mark.asyncio
  async def test_verbose_cluster_proxies_stats():
    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_proxies_stats.ips_getter',
      return_value=['192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test
      stats, failures = await cluster_stats.cluster_proxies_stats.get_current()

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/proxies',
      headers={'Appscale-Secret': 'secret'},
      json={}, timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    lb_stats = stats['192.168.33.11']
    assert isinstance(lb_stats, proxy_stats.ProxiesStatsSnapshot)
    assert len(lb_stats.proxies_stats) == 5
    assert lb_stats.utc_timestamp == 1494248097.0

  @staticmethod
  @pytest.mark.asyncio
  async def test_filtered_cluster_proxies_stats():
    # Read test data from json file
    raw_test_data = get_stats_from_file(
      'proxies-stats.json', proxy_stats.ProxiesStatsSnapshot
    )[0]

    private_ip_patcher = patch(
      'appscale.common.appscale_info.get_private_ip',
      return_value='192.168.33.10'
    )
    ips_getter_patcher = patch(
      'appscale.hermes.producers.cluster_stats.cluster_proxies_stats.ips_getter',
      return_value=['192.168.33.11']
    )
    secret_patcher = patch(
      'appscale.common.appscale_info.get_secret',
      return_value='secret'
    )
    json_method = MagicMock(return_value=future(raw_test_data['192.168.33.11']))
    response = MagicMock(json=json_method, status=200)
    get_remote_patcher = patch(
      'aiohttp.ClientSession.get',
      return_value=AsyncContextMock(aenter=response)
    )
    # Prepare raw dict with include lists
    raw_include_lists = {
      'proxy': ['name', 'unified_service_name', 'application_id',
                'frontend', 'backend'],
      'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
      'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
    }

    # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
    with contextlib.ExitStack() as stack:
      # Start patchers
      stack.enter_context(private_ip_patcher)
      stack.enter_context(ips_getter_patcher)
      stack.enter_context(secret_patcher)
      session_get_mock = stack.enter_context(get_remote_patcher)
      # Call method under test to get stats with filtered set of fields
      include_lists = IncludeLists(raw_include_lists)
      stats, failures = await cluster_stats.cluster_proxies_stats.get_current(
        max_age=18, include_lists=include_lists
      )

    # ASSERTING EXPECTATIONS
    session_get_mock.assert_called_once_with(
      'http://192.168.33.11:4378/stats/local/proxies',
      headers={'Appscale-Secret': 'secret'},
      json={
        'max_age': 18,
        'include_lists': raw_include_lists,
      },
      timeout=constants.REMOTE_REQUEST_TIMEOUT
    )
    assert failures == {}

    lb_stats = stats['192.168.33.11']
    assert isinstance(lb_stats, proxy_stats.ProxiesStatsSnapshot)
    assert len(lb_stats.proxies_stats) == 5
    assert lb_stats.utc_timestamp == 1494248097.0
