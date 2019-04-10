import asyncio
import os
from os import path

import attr
import pytest
from mock import patch, MagicMock

from appscale.hermes.constants import MISSED
from appscale.hermes.producers import proxy_stats

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test-data')


def future(value=None):
  future_obj = asyncio.Future()
  future_obj.set_result(value)
  return future_obj


class TestCurrentProxiesStats:

  @staticmethod
  @pytest.mark.asyncio
  async def test_haproxy_stats_v1_5():
    with open(path.join(TEST_DATA_DIR, 'haproxy-stats-v1.5.csv')) as stats_file:
      stats_bytes = stats_file.read().encode()
    # Mocking haproxy stats socket with csv content
    fake_reader = MagicMock(read=MagicMock(
      side_effect=[
        future(stats_bytes),  # First call
        future(b'')           # Second call
      ]
    ))
    fake_writer = MagicMock(write=MagicMock(return_value=None))
    socket_patcher = patch(
      'asyncio.open_unix_connection',
      return_value=future((fake_reader, fake_writer))
    )

    with socket_patcher:
      # Running method under test
      stats_snapshot = await proxy_stats.ProxiesStatsSource.get_current()

    # Verifying outcomes
    assert isinstance(stats_snapshot.utc_timestamp, float)
    proxies_stats = stats_snapshot.proxies_stats
    assert len(proxies_stats) == 5
    proxies_stats_dict = {
      px_stats.name: px_stats for px_stats in proxies_stats
    }
    assert set(proxies_stats_dict) == {
      'TaskQueue', 'UserAppServer', 'appscale-datastore_server',
      'as_blob_server', 'gae_appscaledashboard'
    }

    # There are 5 proxies, let's choose one for deeper verification
    dashboard = proxies_stats_dict['gae_appscaledashboard']
    assert dashboard.name == 'gae_appscaledashboard'
    assert dashboard.unified_service_name == 'application'
    assert dashboard.application_id == 'appscaledashboard'

    # Frontend stats shouldn't have Nones
    frontend = dashboard.frontend
    for field in list(attr.fields_dict(proxy_stats.HAProxyFrontendStats).keys()):
      assert getattr(frontend, field) is not None

    # Backend stats shouldn't have Nones
    backend = dashboard.backend
    for field in list(attr.fields_dict(proxy_stats.HAProxyBackendStats).keys()):
      assert getattr(backend, field) is not None

    # Backend stats can have Nones only in some fields
    servers = dashboard.servers
    assert isinstance(servers, list)
    assert len(servers) == 3
    for server in servers:
      for field in list(attr.fields_dict(proxy_stats.HAProxyServerStats).keys()):
        if field in {'qlimit', 'throttle', 'tracked', 'check_code',
                     'last_chk', 'last_agt'}:
          continue
        assert getattr(server, field) is not None

    # We don't have listeners on stats
    assert dashboard.listeners == []

  @staticmethod
  @pytest.mark.asyncio
  async def test_haproxy_stats_v1_4():
    with open(path.join(TEST_DATA_DIR, 'haproxy-stats-v1.4.csv')) as stats_file:
      stats_bytes = stats_file.read().encode()
    # Mocking haproxy stats socket with csv content
    fake_reader = MagicMock(read=MagicMock(
      side_effect=[
        future(stats_bytes),  # First call
        future(b'')           # Second call
      ]
    ))
    fake_writer = MagicMock(write=MagicMock(return_value=None))
    socket_patcher = patch(
      'asyncio.open_unix_connection',
      return_value=future((fake_reader, fake_writer))
    )

    # Mock logger warning method
    warning_patcher = patch(
      'appscale.hermes.producers.proxy_stats.logger.warning'
    )

    with socket_patcher:
      with warning_patcher as mock_logging_warn:
        # Running method under test
        proxy_stats.ProxiesStatsSource.first_run = True
        stats_snapshot = await proxy_stats.ProxiesStatsSource.get_current()

    # Verifying outcomes
    assert isinstance(stats_snapshot.utc_timestamp, float)
    proxies_stats = stats_snapshot.proxies_stats
    assert (
      'Old version of HAProxy is probably used (v1.5+ is expected)' in
      mock_logging_warn.call_args[0][0]
    )
    assert len(proxies_stats) == 5
    proxies_stats_dict = {
      px_stats.name: px_stats for px_stats in proxies_stats
    }
    assert set(proxies_stats_dict) == {
      'TaskQueue', 'UserAppServer', 'appscale-datastore_server',
      'as_blob_server', 'gae_appscaledashboard'
    }

    # There are 5 proxies, let's choose one for deeper verification
    dashboard = proxies_stats_dict['gae_appscaledashboard']
    assert dashboard.name == 'gae_appscaledashboard'
    assert dashboard.unified_service_name == 'application'
    assert dashboard.application_id == 'appscaledashboard'

    # Frontend stats shouldn't have Nones
    frontend = dashboard.frontend
    for field in list(attr.fields_dict(proxy_stats.HAProxyFrontendStats).keys()):
      assert getattr(frontend, field) is not None
    # New columns should be highlighted
    for new_in_v1_5 in ('comp_byp', 'comp_rsp', 'comp_out', 'comp_in'):
      assert getattr(frontend, new_in_v1_5) is MISSED

    # Backend stats shouldn't have Nones
    backend = dashboard.backend
    for field in list(attr.fields_dict(proxy_stats.HAProxyBackendStats).keys()):
      assert getattr(backend, field) is not None
    # New columns should be highlighted
    for new_in_v1_5 in ('comp_byp', 'lastsess', 'comp_rsp', 'comp_out',
                        'comp_in', 'ttime', 'rtime', 'ctime', 'qtime'):
      assert getattr(backend, new_in_v1_5) is MISSED

    # Backend stats can have Nones only in some fields
    servers = dashboard.servers
    assert isinstance(servers, list)
    assert len(servers) == 3
    for server in servers:
      for field in list(attr.fields_dict(proxy_stats.HAProxyServerStats).keys()):
        if field in {'qlimit', 'throttle', 'tracked', 'check_code',
                     'last_chk', 'last_agt'}:
          continue
        assert getattr(server, field) is not None
      # New columns should be highlighted
      for new_in_v1_5 in ('lastsess', 'last_chk', 'ttime', 'last_agt',
                          'rtime', 'ctime', 'qtime'):
        assert getattr(server, new_in_v1_5) is MISSED

    # We don't have listeners on stats
    assert dashboard.listeners == []


class TestGetServiceInstances:
  @staticmethod
  @pytest.fixture(autouse=True)
  def haproxy_stats_v1_5():
    with open(path.join(TEST_DATA_DIR, 'haproxy-stats-v1.5.csv')) as stats_file:
      stats_bytes = stats_file.read().encode()
    # Mocking haproxy stats socket with csv content
    fake_reader = MagicMock(read=MagicMock(return_value=future(stats_bytes)))
    fake_writer = MagicMock(write=MagicMock(return_value=None))
    socket_patcher = patch(
      'asyncio.open_unix_connection',
      return_value=future((fake_reader, fake_writer))
    )
    socket_patcher.start()
    yield socket_patcher
    socket_patcher.stop()

  @staticmethod
  @pytest.mark.asyncio
  async def test_taskqueue_instances():
    taskqueue = await proxy_stats.get_service_instances('mocked', 'TaskQueue')
    assert taskqueue == [
      '10.10.7.86:17447',
      '10.10.7.86:17448',
      '10.10.7.86:17449',
      '10.10.7.86:17450'
    ]

  @staticmethod
  @pytest.mark.asyncio
  async def test_datastore_instances():
    datastore = await proxy_stats.get_service_instances(
      'mocked', 'appscale-datastore_server'
    )
    assert datastore == [
      '10.10.7.86:4000',
      '10.10.7.86:4001',
      '10.10.7.86:4002',
      '10.10.7.86:4003'
    ]

  @staticmethod
  @pytest.mark.asyncio
  async def test_dashboard_instances():
    dashboard = await proxy_stats.get_service_instances(
      'mocked', 'gae_appscaledashboard'
    )
    assert dashboard == [
      '10.10.9.111:20000',
      '10.10.9.111:20001',
      '10.10.9.111:20002'
    ]

  @staticmethod
  @pytest.mark.asyncio
  async def test_unknown_proxy():
    unknown = await proxy_stats.get_service_instances(
      'mocked', 'gae_not_running'
    )
    assert unknown == []

