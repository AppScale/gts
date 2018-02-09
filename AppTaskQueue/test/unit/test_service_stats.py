import sys

from appscale.taskqueue.statistics import service_stats
from mock import mock, patch
from tornado.testing import AsyncHTTPTestCase, gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

from appscale.taskqueue import appscale_taskqueue, rest_api

sys.path.append(APPSCALE_PYTHON_APPSERVER)


class TestServiceStatistics(AsyncHTTPTestCase):

  def get_app(self):
    # We're going to mock functionality which uses taskqueue so can omit it
    return appscale_taskqueue.prepare_taskqueue_application(task_queue=None)

  @classmethod
  def setUpClass(cls):
    # Patch get_status of REST handlers
    handlers = [rest_api.RESTQueue, rest_api.RESTTask,
                rest_api.RESTLease, rest_api.RESTTasks]
    cls.patchers = []
    cls.get_http_status_mock = mock.MagicMock()
    for handler in handlers:
      patcher = patch.object(handler, 'get_status', cls.get_http_status_mock)
      patcher.start()
      cls.patchers.append(patcher)
      # Patch all http methods as they are not an object of test
      for method in ['get', 'post', 'put', 'delete', 'patch']:
        def method_impl(*args, **kwargs):
          return None
        patcher = patch.object(handler, method, method_impl)
        patcher.start()
        cls.patchers.append(patcher)

    # Patch remote_request method of protobuffer handler
    patcher = patch.object(appscale_taskqueue.ProtobufferHandler,
                           'remote_request')
    cls.pb_remote_request_mock = patcher.start()
    cls.patchers.append(patcher)

  @classmethod
  def tearDownClass(cls):
    for patcher in cls.patchers:
      patcher.stop()

  def simulate_protobuffer_request(self, pb_type, method, status):
    self.pb_remote_request_mock.return_value = method, status
    print self.fetch(
      '/queues', method='POST', body="does not matter", headers={
         'protocolbuffertype': pb_type,
         'appdata': 'test-app',
         'Version': 'test-version',
         'Module': 'test-module'
       }
    )

  def simulate_rest_request(self, method, path, status):
    self.get_http_status_mock.return_value = status
    print self.fetch(path, method=method)

  def test_homepage(self):
    self.simulate_protobuffer_request('Request', 'BulkAdd', 'Ok')
    self.simulate_protobuffer_request('Request', 'BulkAdd', 'Ok')
    self.simulate_protobuffer_request('Request', 'BulkAdd', 'Ok')
    self.simulate_protobuffer_request('Request', 'BulkAdd', 'Ok')
    self.simulate_rest_request('GET', '/taskqueue/v1beta2/projects/hello-app/taskqueues/aaa', 200)
    print service_stats.get_cumulative_counters()
    print service_stats.get_recent()
