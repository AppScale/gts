import json
import os

from mock import patch, mock
from tornado import testing, gen

from appscale.hermes.stats.producers import taskqueue_stats, proxy_stats

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(CUR_DIR, 'test-data')


class TestTaskqueueStatsSource(testing.AsyncTestCase):

  @patch.object(proxy_stats, 'get_service_instances')
  @patch.object(taskqueue_stats.httpclient.AsyncHTTPClient, 'fetch')
  @testing.gen_test
  def test_taskqueue_stats(self, mock_fetch, mock_get_instances):
    # Read test data from json file
    test_data_path = os.path.join(TEST_DATA_DIR, 'taskqueue-stats.json')
    with open(test_data_path) as json_file:
      tq_stats = json.load(json_file)

    # Tell that we have 2 taskqueue servers
    tq_responses = {
      '10.10.7.86:17447': mock.MagicMock(
        code=200, reason='OK', body=json.dumps(tq_stats['10.10.7.86:17447'])
      ),
      '10.10.7.86:17448': mock.MagicMock(
        code=200, reason='OK', body=json.dumps(tq_stats['10.10.7.86:17448'])
      ),
      '10.10.7.86:17449': mock.MagicMock(
        code=504, reason='Gateway Timeout', body=None
      )
    }
    mock_get_instances.return_value = tq_responses.keys()

    # Mock taskqueue service stats API
    def fetch(request, **kwargs):
      ip_port = request.url.split('://')[1].split('/')[0]
      response = tq_responses[ip_port]
      future_response = gen.Future()
      future_response.set_result(response)
      return future_response

    mock_fetch.side_effect = fetch

    # Environment is mocked, so we can do a test.
    # Call method under test
    stats_source = taskqueue_stats.TaskqueueStatsSource()
    stats_snapshot = yield stats_source.get_current()

    self.assertIsInstance(stats_snapshot.utc_timestamp, int)
    self.assertEqual(stats_snapshot.current_requests, 4)

    # Check summarised cumulative stats
    self.assertEqual(stats_snapshot.cumulative.total, 40)
    self.assertEqual(stats_snapshot.cumulative.failed, 9)
    self.assertEqual(stats_snapshot.cumulative.pb_reqs, 22)
    self.assertEqual(stats_snapshot.cumulative.rest_reqs, 18)

    # Check summarised recent stats
    self.assertEqual(stats_snapshot.recent.total, 33)
    self.assertEqual(stats_snapshot.recent.failed, 8)
    self.assertEqual(stats_snapshot.recent.avg_latency, 83)
    self.assertEqual(stats_snapshot.recent.pb_reqs, 19)
    self.assertEqual(stats_snapshot.recent.rest_reqs, 14)
    self.assertEqual(stats_snapshot.recent.by_pb_method, {
      "BulkAdd": 4, "PauseQueue": 4, "FetchTask": 11
    })
    self.assertEqual(stats_snapshot.recent.by_rest_method, {
      "get_tasks": 2, "post_tasks": 6, "patch_task": 6
    })
    self.assertEqual(stats_snapshot.recent.by_pb_status, {
      "OK": 16, "UNKNOWN_TASK": 2, "UNKNOWN_QUEUE": 1
    })
    self.assertEqual(stats_snapshot.recent.by_rest_status, {
      "200": 9, "404": 3, "500": 2
    })

    # Check instances
    self.assertEqual(len(stats_snapshot.instances), 2)
    tq_17447 = next(instance for instance in stats_snapshot.instances
                    if instance.ip_port == '10.10.7.86:17447')
    tq_17448 = next(instance for instance in stats_snapshot.instances
                    if instance.ip_port == '10.10.7.86:17448')

    # TaskQueue on port 17447
    self.assertEqual(tq_17447.start_timestamp_ms, 1494240000000)
    self.assertEqual(tq_17447.current_requests, 3)
    self.assertEqual(tq_17447.cumulative.total, 15)
    self.assertEqual(tq_17447.cumulative.failed, 5)
    self.assertEqual(tq_17447.cumulative.pb_reqs, 6)
    self.assertEqual(tq_17447.cumulative.rest_reqs, 9)
    self.assertEqual(tq_17447.recent.total, 13)
    self.assertEqual(tq_17447.recent.failed, 5)
    self.assertEqual(tq_17447.recent.avg_latency, 64)
    self.assertEqual(tq_17447.recent.pb_reqs, 6)
    self.assertEqual(tq_17447.recent.rest_reqs, 7)
    self.assertEqual(tq_17447.recent.by_pb_method, {
      "BulkAdd": 4, "PauseQueue": 2
    })
    self.assertEqual(tq_17447.recent.by_rest_method, {
      "get_tasks": 2, "post_tasks": 5
    })
    self.assertEqual(tq_17447.recent.by_pb_status, {
      "OK": 4, "UNKNOWN_TASK": 2
    })
    self.assertEqual(tq_17447.recent.by_rest_status, {
      "200": 4, "404": 3
    })

    # TaskQueue on port 17448
    self.assertEqual(tq_17448.start_timestamp_ms, 1494240000250)
    self.assertEqual(tq_17448.current_requests, 1)
    self.assertEqual(tq_17448.cumulative.total, 25)
    self.assertEqual(tq_17448.cumulative.failed, 4)
    self.assertEqual(tq_17448.cumulative.pb_reqs, 16)
    self.assertEqual(tq_17448.cumulative.rest_reqs, 9)
    self.assertEqual(tq_17448.recent.total, 20)
    self.assertEqual(tq_17448.recent.failed, 3)
    self.assertEqual(tq_17448.recent.avg_latency, 96)
    self.assertEqual(tq_17448.recent.pb_reqs, 13)
    self.assertEqual(tq_17448.recent.rest_reqs, 7)
    self.assertEqual(tq_17448.recent.by_pb_method, {
      "PauseQueue": 2, "FetchTask": 11
    })
    self.assertEqual(tq_17448.recent.by_rest_method, {
      "post_tasks": 1, "patch_task": 6
    })
    self.assertEqual(tq_17448.recent.by_pb_status, {
      "OK": 12, "UNKNOWN_QUEUE": 1
    })
    self.assertEqual(tq_17448.recent.by_rest_status, {
      "200": 5, "500": 2
    })

    self.assertEqual(stats_snapshot.instances_count, 2)

    # Check Failures
    self.assertEqual(len(stats_snapshot.failures), 1)
    self.assertEqual(stats_snapshot.failures[0].ip_port,
                     '10.10.7.86:17449')
    self.assertEqual(stats_snapshot.failures[0].error,
                     '504 Gateway Timeout')
