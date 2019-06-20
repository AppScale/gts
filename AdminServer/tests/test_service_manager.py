from mock import MagicMock, mock_open, patch, call
from tornado.gen import Future
from tornado.testing import AsyncTestCase, gen_test

from appscale.admin.service_manager import (
  gen, psutil, ServerStates, ServiceManager,
  ServiceTypes, datastore_service, search_service,
  ServerManager)


def fake_response(**kwargs):
  future = Future()
  future.set_result(MagicMock(**kwargs))
  return future


# Skip sleep calls.
patchers = []
def setUpModule():
  patcher = patch.object(gen, 'sleep')
  patchers.append(patcher)
  sleep_response = Future()
  sleep_response.set_result(None)
  sleep_mock = patcher.start()
  sleep_mock.return_value = sleep_response


def tearDownModule():
  for patcher in patchers:
    patcher.stop()


class TestDatastoreService(AsyncTestCase):
  @patch('appscale.admin.service_manager.AsyncHTTPClient')
  @patch.object(psutil, 'Popen')
  @patch('appscale.admin.service_manager.open', mock_open(), create=True)
  @gen_test
  def test_start(self, popen_mock, http_client_mock):
    datastore_server = ServerManager(datastore_service, 4000,
                                     {'count': 4, 'verbose': True})

    # Test that a Datastore server process is started.
    popen_mock.return_value = MagicMock(
      is_running=MagicMock(return_value=True), pid=10000
    )
    fake_fetch = MagicMock(return_value=fake_response(code=200))
    http_client_mock.return_value = MagicMock(fetch=fake_fetch)
    yield datastore_server.start()

    cmd = ['appscale-datastore',
           '--type', 'cassandra', '--port', '4000', '--verbose']
    self.assertEqual(popen_mock.call_count, 1)
    self.assertEqual(popen_mock.call_args[0][0], cmd)

  @patch.object(psutil, 'Process')
  def test_from_pid(self, process_mock):
    # Test that the server attributes are parsed correctly.
    cmd = ['python', 'appscale-datastore',
           '--type', 'cassandra', '--port', '4000']
    process_mock.return_value = MagicMock(cmdline=MagicMock(return_value=cmd))
    server = ServerManager.from_pid(10000, datastore_service)

    self.assertEqual(server.port, 4000)
    self.assertEqual(server.state, ServerStates.RUNNING)
    self.assertEqual(server.type, ServiceTypes.DATASTORE)


class TestSearchService(AsyncTestCase):
  @patch('appscale.admin.service_manager.options')
  @patch('appscale.admin.service_manager.AsyncHTTPClient')
  @patch.object(psutil, 'Popen')
  @patch('appscale.admin.service_manager.open', mock_open(), create=True)
  @gen_test
  def test_start(self, popen_mock, http_client_mock, options_mock):
    search_server = ServerManager(search_service, 30000,
                                  {'count': 2, 'verbose': False})

    # Test that a Datastore server process is started.
    popen_mock.return_value = MagicMock(
      is_running=MagicMock(return_value=True), pid=15000
    )
    health = ('{"solr_live_nodes": ["10.0.2.15:8983"], '
              '"zookeeper_state": "CONNECTED"}')
    response = fake_response(code=200, body=health)
    fake_fetch = MagicMock(return_value=response)
    http_client_mock.return_value = MagicMock(fetch=fake_fetch)
    options_mock.zk_locations = ['10.0.2.13']
    options_mock.private_ip = '10.0.2.14'
    yield search_server.start()

    cmd = [
      '/opt/appscale_venvs/search2/bin/appscale-search2',
      '--zk-locations', '10.0.2.13', '--host', '10.0.2.14', '--port', '30000'
    ]
    self.assertEqual(popen_mock.call_count, 1)
    self.assertEqual(popen_mock.call_args[0][0], cmd)

  @patch.object(psutil, 'Process')
  def test_from_pid(self, process_mock):
    # Test that the server attributes are parsed correctly.
    cmd = [
      'python3', '/opt/appscale_venvs/search2/bin/appscale-search2',
      '--zk-locations', '10.0.2.13', '--host', '10.0.2.14', '--port', '30000'
    ]
    process_mock.return_value = MagicMock(cmdline=MagicMock(return_value=cmd))
    server = ServerManager.from_pid(15000, search_service)

    self.assertEqual(server.port, 30000)
    self.assertEqual(server.state, ServerStates.RUNNING)
    self.assertEqual(server.type, ServiceTypes.SEARCH)


class TestServiceManager(AsyncTestCase):
  @patch.object(ServerManager, 'from_pid')
  @patch('appscale.admin.service_manager.pids_in_slice')
  def test_get_state(self, pids_in_slice_mock, from_pid_mock):
    # Test that server objects are created with the correct PIDs.
    slices = {
      'appscale-datastore': [10000, 10001],
      'appscale-search': [15000, 15001]
    }
    pids_in_slice_mock.side_effect = lambda service_type: slices[service_type]
    ServiceManager.get_state()

    self.assertEqual(from_pid_mock.call_count, 4)
    calls = from_pid_mock.call_args_list
    self.assertEqual(calls[0], call(10000, datastore_service))
    self.assertEqual(calls[1], call(10001, datastore_service))
    self.assertEqual(calls[2], call(15000, search_service))
    self.assertEqual(calls[3], call(15001, search_service))

  @patch('appscale.admin.service_manager.options')
  def test_schedule_service(self, options_mock):
    options_mock.private_ip = '192.168.33.10'
    zk_client = None

    manager = ServiceManager(zk_client)

    # Test that servers are started when scheduled.
    manager._schedule_service(ServiceTypes.DATASTORE,
                              {'count': 2, 'verbose': False})
    self.assertEqual(len(manager.state), 2)
    manager._schedule_service(ServiceTypes.SEARCH,
                              {'count': 3, 'verbose': True})
    self.assertEqual(len(manager.state), 5)
