import os
from os import path
import unittest

import attr
from mock import patch, MagicMock

from appscale.hermes.constants import MISSED
from appscale.hermes.producers import proxy_stats

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(CUR_DIR, 'test-data')


class TestCurrentProxiesStats(unittest.TestCase):

  def setUp(self):
    self.stats_file = None

  def tearDown(self):
    if self.stats_file:
      self.stats_file.close()

  @patch.object(proxy_stats.socket, 'socket')
  def test_haproxy_stats_mapping(self, mock_socket):
    # Mocking haproxy stats socket with csv file
    # THE FILE CONTAINS MEANINGLESS DATA BUT IT HELP TO TEST COLUMNS MAPPING
    self.stats_file = open(path.join(DATA_DIR, 'haproxy-stats-mapping.csv'))
    fake_socket = MagicMock(recv=self.stats_file.read)
    mock_socket.return_value = fake_socket

    # Running method under test
    stats_snapshot = proxy_stats.ProxiesStatsSource.get_current()
    proxy_a = stats_snapshot.proxies_stats[0]

    # Verify Frontend stats
    self.assertEqual(
      proxy_a.frontend,
      proxy_stats.HAProxyFrontendStats(
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
    self.assertEqual(
      proxy_a.backend,
      proxy_stats.HAProxyBackendStats(
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
    self.assertEqual(
      proxy_a.servers[0],
      proxy_stats.HAProxyServerStats(
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

  @patch.object(proxy_stats.socket, 'socket')
  def test_haproxy_stats_v1_5(self, mock_socket):
    # Mocking haproxy stats socket with csv file
    self.stats_file = open(path.join(DATA_DIR, 'haproxy-stats-v1.5.csv'))
    fake_socket = MagicMock(recv=self.stats_file.read)
    mock_socket.return_value = fake_socket

    # Running method under test
    stats_snapshot = proxy_stats.ProxiesStatsSource.get_current()

    # Verifying outcomes
    self.assertIsInstance(stats_snapshot.utc_timestamp, float)
    proxies_stats = stats_snapshot.proxies_stats
    self.assertEqual(len(proxies_stats), 5)
    proxies_stats_dict = {
      proxy_stats.name: proxy_stats for proxy_stats in proxies_stats
    }
    self.assertEqual(set(proxies_stats_dict), {
      'TaskQueue', 'UserAppServer', 'appscale-datastore_server',
      'as_blob_server', 'gae_appscaledashboard'
    })

    # There are 5 proxies, let's choose one for deeper verification
    dashboard = proxies_stats_dict['gae_appscaledashboard']
    self.assertEqual(dashboard.name, 'gae_appscaledashboard')
    self.assertEqual(dashboard.unified_service_name, 'application')
    self.assertEqual(dashboard.application_id, 'appscaledashboard')

    # Frontend stats shouldn't have Nones
    frontend = dashboard.frontend
    for field in attr.fields_dict(proxy_stats.HAProxyFrontendStats).keys():
      self.assertIsNotNone(getattr(frontend, field))

    # Backend stats shouldn't have Nones
    backend = dashboard.backend
    for field in attr.fields_dict(proxy_stats.HAProxyBackendStats).keys():
      self.assertIsNotNone(getattr(backend, field))

    # Backend stats can have Nones only in some fields
    servers = dashboard.servers
    self.assertIsInstance(servers, list)
    self.assertEqual(len(servers), 3)
    for server in servers:
      for field in attr.fields_dict(proxy_stats.HAProxyServerStats).keys():
        if field in {'qlimit', 'throttle', 'tracked', 'check_code',
                     'last_chk', 'last_agt'}:
          continue
        self.assertIsNotNone(getattr(server, field))

    # We don't have listeners on stats
    self.assertEqual(dashboard.listeners, [])

  @patch.object(proxy_stats.socket, 'socket')
  @patch.object(proxy_stats.logger, 'warning')
  def test_haproxy_stats_v1_4(self, mock_logging_warn, mock_socket):
    # Mocking "echo 'show stat' | socat stdio unix-connect:{}" with csv file
    self.stats_file = open(path.join(DATA_DIR, 'haproxy-stats-v1.4.csv'))
    fake_socket = MagicMock(recv=self.stats_file.read)
    mock_socket.return_value = fake_socket

    # Running method under test
    proxy_stats.ProxiesStatsSource.first_run = True
    stats_snapshot = proxy_stats.ProxiesStatsSource.get_current()

    # Verifying outcomes
    self.assertIsInstance(stats_snapshot.utc_timestamp, float)
    proxies_stats = stats_snapshot.proxies_stats
    self.assertTrue(
      mock_logging_warn.call_args[0][0].startswith(
        "Old version of HAProxy is used (v1.5+ is expected)."
      )
    )
    self.assertEqual(len(proxies_stats), 5)
    proxies_stats_dict = {
      proxy_stats.name: proxy_stats for proxy_stats in proxies_stats
    }
    self.assertEqual(set(proxies_stats_dict), {
      'TaskQueue', 'UserAppServer', 'appscale-datastore_server',
      'as_blob_server', 'gae_appscaledashboard'
    })

    # There are 5 proxies, let's choose one for deeper verification
    dashboard = proxies_stats_dict['gae_appscaledashboard']
    self.assertEqual(dashboard.name, 'gae_appscaledashboard')
    self.assertEqual(dashboard.unified_service_name, 'application')
    self.assertEqual(dashboard.application_id, 'appscaledashboard')

    # Frontend stats shouldn't have Nones
    frontend = dashboard.frontend
    for field in attr.fields_dict(proxy_stats.HAProxyFrontendStats).keys():
      self.assertIsNotNone(getattr(frontend, field))
    # New columns should be highlighted
    for new_in_v1_5 in ('comp_byp', 'comp_rsp', 'comp_out', 'comp_in'):
      self.assertIs(getattr(frontend, new_in_v1_5), MISSED)

    # Backend stats shouldn't have Nones
    backend = dashboard.backend
    for field in attr.fields_dict(proxy_stats.HAProxyBackendStats).keys():
      self.assertIsNotNone(getattr(backend, field))
    # New columns should be highlighted
    for new_in_v1_5 in ('comp_byp', 'lastsess', 'comp_rsp', 'comp_out',
                        'comp_in', 'ttime', 'rtime', 'ctime', 'qtime'):
      self.assertIs(getattr(backend, new_in_v1_5), MISSED)

    # Backend stats can have Nones only in some fields
    servers = dashboard.servers
    self.assertIsInstance(servers, list)
    self.assertEqual(len(servers), 3)
    for server in servers:
      for field in attr.fields_dict(proxy_stats.HAProxyServerStats).keys():
        if field in {'qlimit', 'throttle', 'tracked', 'check_code',
                     'last_chk', 'last_agt'}:
          continue
        self.assertIsNotNone(getattr(server, field))
      # New columns should be highlighted
      for new_in_v1_5 in ('lastsess', 'last_chk', 'ttime', 'last_agt',
                          'rtime', 'ctime', 'qtime'):
        self.assertIs(getattr(server, new_in_v1_5), MISSED)

    # We don't have listeners on stats
    self.assertEqual(dashboard.listeners, [])


class TestGetServiceInstances(unittest.TestCase):
  def setUp(self):
    stats_file = open(path.join(DATA_DIR, 'haproxy-stats-v1.5.csv'))
    fake_socket = MagicMock(recv=stats_file.read)
    self.socket_patcher = patch.object(proxy_stats.socket, 'socket')
    socket_mock = self.socket_patcher.start()
    socket_mock.return_value = fake_socket

  def tearDown(self):
    self.socket_patcher.stop()

  def test_taskqueue_instances(self):
    taskqueue = proxy_stats.get_service_instances('mocked', 'TaskQueue')
    self.assertEqual(taskqueue, [
      '10.10.7.86:17447',
      '10.10.7.86:17448',
      '10.10.7.86:17449',
      '10.10.7.86:17450'
    ])

  def test_datastore_instances(self):
    datastore = proxy_stats.get_service_instances(
      'mocked', 'appscale-datastore_server'
    )
    self.assertEqual(datastore, [
      '10.10.7.86:4000',
      '10.10.7.86:4001',
      '10.10.7.86:4002',
      '10.10.7.86:4003'
    ])

  def test_dashboard_instances(self):
    dashboard = proxy_stats.get_service_instances(
      'mocked', 'gae_appscaledashboard'
    )
    self.assertEqual(dashboard, [
      '10.10.9.111:20000',
      '10.10.9.111:20001',
      '10.10.9.111:20002'
    ])

  def test_unknown_proxy(self):
    unknown = proxy_stats.get_service_instances('mocked', 'gae_not_running')
    self.assertEqual(unknown, [])


if __name__ == '__main__':
  unittest.main()
