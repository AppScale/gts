from importlib import reload
import json
from unittest import mock
from unittest.mock import patch

from appscale.common.service_stats import stats_manager
from tornado.testing import AsyncHTTPTestCase

from appscale.taskqueue import appscale_taskqueue, rest_api, statistics


class TestServiceStatistics(AsyncHTTPTestCase):

  def get_app(self):
    """ Overwrites method of AsyncHTTPTestCase.
    Returns:
      an instance of tornado application
    """
    # We mock functionality which uses distributed taskqueue so can omit it
    distributed_taskqueue = None
    return appscale_taskqueue.prepare_taskqueue_application(
      task_queue=distributed_taskqueue
    )

  def setUp(self):
    """ Patches handlers of Taskqueue application in order
    to prevent real calls to Cassandra and Datastore because only
    service statistics matters for this test.
    """
    super(TestServiceStatistics, self).setUp()

    # Patch get_status of REST handlers
    handlers = [rest_api.RESTQueue, rest_api.RESTTask,
                rest_api.RESTLease, rest_api.RESTTasks]
    self.patchers = []
    self.get_http_status_mock = mock.MagicMock()
    for handler in handlers:
      patcher = patch.object(handler, 'get_status', self.get_http_status_mock)
      patcher.start()
      self.patchers.append(patcher)
      # Patch all http methods as they are not an object of test
      for method in ['get', 'post', 'put', 'delete', 'patch']:
        def method_impl(*args, **kwargs):
          return None
        patcher = patch.object(handler, method, method_impl)
        patcher.start()
        self.patchers.append(patcher)

    # Patch remote_request method of protobuffer handler
    remote_request_patcher = patch.object(
      appscale_taskqueue.ProtobufferHandler, 'remote_request'
    )
    self.pb_remote_request_mock = remote_request_patcher.start()
    self.patchers.append(remote_request_patcher)

    time_patcher = patch.object(stats_manager.time, 'time')
    self.time_mock = time_patcher.start()
    self.patchers.append(time_patcher)

  def tearDown(self):
    super(TestServiceStatistics, self).tearDown()
    # Stops all patchers.
    for patcher in self.patchers:
      patcher.stop()

    reload(statistics)
    reload(rest_api)
    reload(appscale_taskqueue)

  def test_stats(self):
    self.time_mock.return_value = 1000

    # Specify stub information for protobuffer requests
    pb_headers = {
      'protocolbuffertype': 'Request',
      'appdata': 'test-app',
      'Version': 'test-version',
      'Module': 'test-module'
    }
    pb_body = "does not matter"

    # Do 6 protobuffer requests:
    # Mock remote_request method to return tuple (pb_method, pb_status)
    self.pb_remote_request_mock.return_value = 'BulkAdd', 'OK'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)
    self.pb_remote_request_mock.return_value = 'BulkAdd', 'OK'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)
    self.pb_remote_request_mock.return_value = 'FetchTask', 'OK'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)
    self.pb_remote_request_mock.return_value = 'PauseQueue', 'UNKNOWN_QUEUE'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)
    self.pb_remote_request_mock.return_value = 'PauseQueue', 'OK'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)
    self.pb_remote_request_mock.return_value = 'FetchTask', 'UNKNOWN_TASK'
    self.fetch('/queues', method='POST', body=pb_body, headers=pb_headers)

    # Do 9 REST requests:
    # Mock get_status method of REST handlers to return wanted http status
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/queue1'
    self.fetch(path, method='GET')
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/queue1'
    self.fetch(path, method='GET')
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/queue1/tasks'
    self.fetch(path, method='GET')
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/qeueu1/tasks'
    self.fetch(path, method='POST', allow_nonstandard_methods=True)
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/qeueu1/tasks'
    self.fetch(path, method='POST', allow_nonstandard_methods=True)
    self.get_http_status_mock.return_value = 200
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/qeueu1/tasks/task1'
    self.fetch(path, method='GET')
    self.get_http_status_mock.return_value = 500
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/qeueu1/tasks/task1'
    self.fetch(path, method='DELETE', allow_nonstandard_methods=True)
    self.get_http_status_mock.return_value = 404
    path = '/taskqueue/v1beta2/projects/app1/taskqueues/unknown/tasks/task1'
    self.fetch(path, method='PATCH', allow_nonstandard_methods=True)
    self.get_http_status_mock.return_value = 404
    path = '/taskqueue/v1beta2/projects/unknown/taskqueues/qeueu1/tasks/task1'
    self.fetch(path, method='GET')

    # Fetch statistics
    raw_stats = self.fetch('/service-stats').body
    stats = json.loads(raw_stats.decode('utf-8'))

    # Pop and check time-related fields
    self.assertGreater(stats['cumulative_counters'].pop('from'), 0)
    self.assertGreater(stats['cumulative_counters'].pop('to'), 0)
    self.assertGreater(stats['recent_stats'].pop('from'), 0)
    self.assertGreater(stats['recent_stats'].pop('to'), 0)
    self.assertGreaterEqual(stats['recent_stats'].pop('avg_latency'), 0)

    # Verify other fields
    self.assertEqual(stats, {
      'current_requests': 0,
      'cumulative_counters': {
        'all': 15,
        'failed': 5,
        'pb_reqs': 6,
        'rest_reqs': 9
      },
     'recent_stats': {
       'all': 15,
       'failed': 5,
       'pb_reqs': 6,
       'rest_reqs': 9,
       'by_rest_method': {
         'get_task': 2,
         'get_tasks': 1,
         'delete_task': 1,
         'get_queue': 2,
         'patch_task': 1,
         'post_tasks': 2
       },
       'by_rest_status': {
         '200': 6,
         '404': 2,
         '500': 1
       },
       'by_pb_method': {
         'BulkAdd': 2,
         'PauseQueue': 2,
         'FetchTask': 2
       },
       'by_pb_status': {
         'OK': 4,
         'UNKNOWN_TASK': 1,
         'UNKNOWN_QUEUE': 1
    }}})

  def test_scroll_stats(self):
    self.time_mock.return_value = 1000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')
    self.time_mock.return_value = 2000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')
    self.time_mock.return_value = 3000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')

    # Fetch statistics
    self.time_mock.return_value = 99999  # current time doesn't matter
                                         # for scrolling
    raw_stats = self.fetch('/service-stats?cursor=1500000').body
    stats = json.loads(raw_stats.decode('utf-8'))

    self.assertEqual(stats['cumulative_counters']['all'], 3)
    self.assertEqual(stats['recent_stats']['all'], 2)

  def test_recent_stats(self):
    self.time_mock.return_value = 1000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')
    self.time_mock.return_value = 2000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')
    self.time_mock.return_value = 3000
    self.get_http_status_mock.return_value = 200
    self.fetch('/taskqueue/v1beta2/projects/app1/taskqueues/queue1')

    # Fetch statistics as if it was in the future
    self.time_mock.return_value = 99999  # current time does matter for recent
    raw_stats = self.fetch('/service-stats?last_milliseconds=2000000').body
    stats = json.loads(raw_stats.decode('utf-8'))

    self.assertEqual(stats['cumulative_counters']['all'], 3)
    self.assertEqual(stats['recent_stats']['all'], 0)  # 0 for last 2 seconds

    # Fetch statistics as if it was just after requests
    self.time_mock.return_value = 3500  # current time does matter for recent
    raw_stats = self.fetch('/service-stats?last_milliseconds=2000000').body
    stats = json.loads(raw_stats.decode('utf-8'))

    self.assertEqual(stats['cumulative_counters']['all'], 3)
    self.assertEqual(stats['recent_stats']['all'], 2)   # 2 for last 2 seconds
