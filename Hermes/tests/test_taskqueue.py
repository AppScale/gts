import asyncio
import json
import os

import aiohttp
import pytest
from mock import patch, MagicMock

from appscale.hermes.producers import taskqueue_stats

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


@pytest.mark.asyncio
async def test_taskqueue_stats():
  # Read test data from json file
  test_data_path = os.path.join(TEST_DATA_DIR, 'taskqueue-stats.json')
  with open(test_data_path) as json_file:
    tq_stats = json.load(json_file)

  def fake_get(url, *args, **kwargs):
    ip_port = url.split('://')[1].split('/')[0]
    if ip_port == '10.10.7.86:17447':
      json_method = MagicMock(return_value=future(tq_stats['10.10.7.86:17447']))
      response = MagicMock(json=json_method)
      return AsyncContextMock(aenter=response)
    if ip_port == '10.10.7.86:17448':
      json_method = MagicMock(return_value=future(tq_stats['10.10.7.86:17448']))
      response = MagicMock(json=json_method)
      return AsyncContextMock(aenter=response)
    if ip_port == '10.10.7.86:17449':
      error = aiohttp.ClientError('HTTP 504: Gateway Timeout')
      response = MagicMock(raise_for_status=MagicMock(side_effect=error))
      return AsyncContextMock(aenter=response)
    if ip_port == '10.10.7.86:17450':
      raise aiohttp.ClientError('Connection refused')

  get_patcher = patch(
    'aiohttp.ClientSession.get',
    side_effect=fake_get
  )
  # Tell that we have 4 taskqueue servers
  get_instances_patcher = patch(
    'appscale.hermes.producers.proxy_stats.get_service_instances',
    return_value=future([
      '10.10.7.86:17447',
      '10.10.7.86:17448',
      '10.10.7.86:17449',
      '10.10.7.86:17450'
    ])
  )
  with get_patcher:
    with get_instances_patcher:
      # Environment is mocked, so we can do a test.
      # Call method under test
      stats_source = taskqueue_stats.TaskqueueStatsSource()
      stats_snapshot = await stats_source.get_current()

  assert isinstance(stats_snapshot.utc_timestamp, int)
  assert stats_snapshot.current_requests == 4

  # Check summarised cumulative stats
  assert stats_snapshot.cumulative.total == 40
  assert stats_snapshot.cumulative.failed == 9
  assert stats_snapshot.cumulative.pb_reqs == 22
  assert stats_snapshot.cumulative.rest_reqs == 18

  # Check summarised recent stats
  assert stats_snapshot.recent.total == 33
  assert stats_snapshot.recent.failed == 8
  assert stats_snapshot.recent.avg_latency == 83
  assert stats_snapshot.recent.pb_reqs == 19
  assert stats_snapshot.recent.rest_reqs == 14
  assert (
    stats_snapshot.recent.by_pb_method ==
    {"BulkAdd": 4, "PauseQueue": 4, "FetchTask": 11}
  )
  assert (
    stats_snapshot.recent.by_rest_method ==
    {"get_tasks": 2, "post_tasks": 6, "patch_task": 6}
  )
  assert (
    stats_snapshot.recent.by_pb_status ==
    {"OK": 16, "UNKNOWN_TASK": 2, "UNKNOWN_QUEUE": 1}
  )
  assert (
    stats_snapshot.recent.by_rest_status ==
    {"200": 9, "404": 3, "500": 2}
  )

  # Check instances
  assert len(stats_snapshot.instances) == 2
  tq_17447 = next(instance for instance in stats_snapshot.instances
                  if instance.ip_port == '10.10.7.86:17447')
  tq_17448 = next(instance for instance in stats_snapshot.instances
                  if instance.ip_port == '10.10.7.86:17448')

  # TaskQueue on port 17447
  assert tq_17447.start_timestamp_ms == 1494240000000
  assert tq_17447.current_requests == 3
  assert tq_17447.cumulative.total == 15
  assert tq_17447.cumulative.failed == 5
  assert tq_17447.cumulative.pb_reqs == 6
  assert tq_17447.cumulative.rest_reqs == 9
  assert tq_17447.recent.total == 13
  assert tq_17447.recent.failed == 5
  assert tq_17447.recent.avg_latency == 64
  assert tq_17447.recent.pb_reqs == 6
  assert tq_17447.recent.rest_reqs == 7
  assert (
    tq_17447.recent.by_pb_method ==
    {"BulkAdd": 4, "PauseQueue": 2}
  )
  assert (
    tq_17447.recent.by_rest_method ==
    {"get_tasks": 2, "post_tasks": 5}
  )
  assert (
    tq_17447.recent.by_pb_status ==
    {"OK": 4, "UNKNOWN_TASK": 2}
  )
  assert (
    tq_17447.recent.by_rest_status ==
    {"200": 4, "404": 3}
  )

  # TaskQueue on port 17448
  assert tq_17448.start_timestamp_ms == 1494240000250
  assert tq_17448.current_requests == 1
  assert tq_17448.cumulative.total == 25
  assert tq_17448.cumulative.failed == 4
  assert tq_17448.cumulative.pb_reqs == 16
  assert tq_17448.cumulative.rest_reqs == 9
  assert tq_17448.recent.total == 20
  assert tq_17448.recent.failed == 3
  assert tq_17448.recent.avg_latency == 96
  assert tq_17448.recent.pb_reqs == 13
  assert tq_17448.recent.rest_reqs == 7
  assert (
    tq_17448.recent.by_pb_method ==
    {"PauseQueue": 2, "FetchTask": 11}
  )
  assert (
    tq_17448.recent.by_rest_method ==
    {"post_tasks": 1, "patch_task": 6}
  )
  assert (
    tq_17448.recent.by_pb_status ==
    {"OK": 12, "UNKNOWN_QUEUE": 1}
  )
  assert (
    tq_17448.recent.by_rest_status ==
    {"200": 5, "500": 2}
  )

  assert stats_snapshot.instances_count == 2

  # Check Failures
  assert len(stats_snapshot.failures) == 2
  tq_17449 = next(instance for instance in stats_snapshot.failures
                  if instance.ip_port == '10.10.7.86:17449')
  tq_17450 = next(instance for instance in stats_snapshot.failures
                  if instance.ip_port == '10.10.7.86:17450')
  assert tq_17449.error == 'HTTP 504: Gateway Timeout'
  assert tq_17450.error == 'Connection refused'
