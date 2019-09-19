import asyncio
import os
from os import path

import attr
import pytest
from mock import patch, MagicMock

from appscale.hermes.constants import MISSED
from appscale.hermes.producers import proxy_stats

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(CUR_DIR, 'test-data')


def future(value=None):
  future_obj = asyncio.Future()
  future_obj.set_result(value)
  return future_obj


class TestCurrentProxiesStats:
  @staticmethod
  @pytest.mark.asyncio
  async def test_haproxy_stats_mapping():
    with open(path.join(DATA_DIR, 'haproxy-stats-mapping.csv')) as stats_file:
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

    proxy_a = stats_snapshot.proxies_stats[0]

    # Verify Frontend stats
    assert (
      proxy_a.frontend
      == proxy_stats.HAProxyFrontendStats(
        pxname='ProxyA',
        svname='FRONTEND',
        scur=0,
        smax=1,
        slim=2,
        stot=3,
        bin=4,
        bout=5,
        dreq=6,
        dresp=7,
        ereq=8,
        status='OPEN',
        pid=9,
        iid=10,
        type=12,
        rate=13,
        rate_lim=14,
        rate_max=15,
        hrsp_1xx=16,
        hrsp_2xx=17,
        hrsp_3xx=18,
        hrsp_4xx=19,
        hrsp_5xx=20,
        hrsp_other=21,
        req_rate=22,
        req_rate_max=23,
        req_tot=24,
        comp_in=25,
        comp_out=26,
        comp_byp=27,
        comp_rsp=28,
      )
    )

    # Verify Backend stats
    assert (
      proxy_a.backend
      == proxy_stats.HAProxyBackendStats(
        pxname='ProxyA',
        svname='BACKEND',
        qcur=200,
        qmax=201,
        scur=202,
        smax=203,
        slim=204,
        stot=205,
        bin=206,
        bout=207,
        dreq=208,
        dresp=209,
        econ=210,
        eresp=211,
        wretr=212,
        wredis=213,
        status='UP',
        weight=214,
        act=215,
        bck=216,
        chkdown=217,
        lastchg=218,
        downtime=219,
        pid=220,
        iid=221,
        lbtot=223,
        type=224,
        rate=225,
        rate_max=226,
        hrsp_1xx=227,
        hrsp_2xx=228,
        hrsp_3xx=229,
        hrsp_4xx=230,
        hrsp_5xx=231,
        hrsp_other=232,
        cli_abrt=233,
        srv_abrt=234,
        comp_in=235,
        comp_out=236,
        comp_byp=237,
        comp_rsp=238,
        lastsess=239,
        qtime=240,
        ctime=241,
        rtime=242,
        ttime=243,
      )
    )

    # Verify Server stats
    assert (
      proxy_a.servers[0]
      == proxy_stats.HAProxyServerStats(
        private_ip=None,
        port=None,
        pxname='ProxyA',
        svname='ProxyA-10.10.8.28:17447',
        qcur=100,
        qmax=101,
        scur=102,
        smax=103,
        slim=104,
        stot=105,
        bin=106,
        bout=107,
        dresp=108,
        econ=109,
        eresp=110,
        wretr=111,
        wredis=112,
        status='UP',
        weight=113,
        act=114,
        bck=115,
        chkfail=116,
        chkdown=117,
        lastchg=118,
        downtime=119,
        qlimit=None,
        pid=120,
        iid=121,
        sid=122,
        throttle=None,
        lbtot=123,
        tracked=None,
        type=124,
        rate=125,
        rate_max=126,
        check_status='L4OK',
        check_code=None,
        check_duration=127,
        hrsp_1xx=128,
        hrsp_2xx=129,
        hrsp_3xx=130,
        hrsp_4xx=131,
        hrsp_5xx=132,
        hrsp_other=133,
        hanafail=134,
        cli_abrt=135,
        srv_abrt=136,
        lastsess=137,
        last_chk='138',
        last_agt='139',
        qtime=140,
        ctime=141,
        rtime=142,
        ttime=143,
      )
    )

  @staticmethod
  @pytest.mark.asyncio
  async def test_haproxy_stats_v1_5():
    with open(path.join(DATA_DIR, 'haproxy-stats-v1.5.csv')) as stats_file:
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
    with open(path.join(DATA_DIR, 'haproxy-stats-v1.4.csv')) as stats_file:
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
    assert mock_logging_warn.call_args[0][0].startswith(
      'Old version of HAProxy is used (v1.5+ is expected)'
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
    with open(path.join(DATA_DIR, 'haproxy-stats-v1.5.csv')) as stats_file:
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
