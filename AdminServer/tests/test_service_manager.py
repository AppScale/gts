import io
from collections import namedtuple

from mock import MagicMock, patch
from tornado.gen import Future
from tornado.httpclient import AsyncHTTPClient
from tornado.testing import AsyncTestCase, gen_test

from appscale.admin.service_manager import (
  DatastoreServer, gen, options, psutil, ServerStates, ServiceManager,
  ServiceTypes)

FakeHTTPResponse = namedtuple('Response', ['code'])

# Skip sleep calls.
sleep_response = Future()
sleep_response.set_result(None)
gen.sleep = MagicMock(return_value=sleep_response)


class FakeProcess(object):
  pass


class TestDatastoreServer(AsyncTestCase):
  @gen_test
  def test_start(self):
    client = AsyncHTTPClient()
    response = Future()
    response.set_result(FakeHTTPResponse(200))
    client.fetch = MagicMock(return_value=response)

    fake_process = FakeProcess()
    fake_process.is_running = MagicMock(return_value=True)

    server = DatastoreServer(4000, client, False)

    # Test that a Datastore server process is started.
    with patch.object(psutil, 'Popen', return_value=fake_process) as mock_popen:
      yield server.start()

    cmd = ['cgexec', '-g', 'memory:appscale-datastore',
           'appscale-datastore', '--type', 'cassandra', '--port', '4000']
    self.assertEqual(mock_popen.call_count, 1)
    self.assertEqual(mock_popen.call_args[0][0], cmd)

  def test_from_pid(self):
    client = AsyncHTTPClient()
    fake_process = FakeProcess()
    cmd = ['appscale-datastore', '--type', 'cassandra', '--port', '4000']
    fake_process.cmdline = MagicMock(return_value=cmd)

    # Test that the server attributes are parsed correctly.
    with patch.object(psutil, 'Process', return_value=fake_process):
      server = DatastoreServer.from_pid(10000, client)

    self.assertEqual(server.port, 4000)
    self.assertEqual(server.state, ServerStates.RUNNING)
    self.assertEqual(server.type, ServiceTypes.DATASTORE)


class TestServiceManager(AsyncTestCase):
  @gen_test
  def test_get_state(self):
    cgroup_file = io.StringIO(u'10000\n10001')

    # Test that server objects are created with the correct PIDs.
    with patch('appscale.admin.service_manager.open', return_value=cgroup_file):
      with patch.object(DatastoreServer, 'from_pid') as mock_from_pid:
        ServiceManager.get_state()

    self.assertEqual(mock_from_pid.call_count, 2)
    for index, expected_pid in enumerate((10000, 10001)):
      self.assertEqual(mock_from_pid.call_args_list[index][0][0], expected_pid)

  @gen_test
  def test_schedule_service(self):
    zk_client = None
    options.define('private_ip', '192.168.33.10')
    manager = ServiceManager(zk_client)

    # Test that servers are started when scheduled.
    manager._schedule_service(ServiceTypes.DATASTORE,
                              {'count': 2, 'verbose': False})
    self.assertEqual(len(manager.state), 2)
