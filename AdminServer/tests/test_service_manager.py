from mock import MagicMock, mock_open, patch
from tornado.gen import Future
from tornado.testing import AsyncTestCase, gen_test

from appscale.admin.service_manager import (
  gen, psutil, ServerStates, ServiceTypes, datastore_service, ServerManager
)


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
