import asyncio
import time

import pytest

from conftest import async_test, TEST_PROJECT
from helpers import taskqueue_service_pb2
from helpers.api_helper import timed


@async_test
async def test_add_lease_prolong_delete(taskqueue):
  # Initialize tasks
  queue_str = 'pull-queue-b'
  queue_bytes = bytes(queue_str, 'utf8')
  tasks = []
  for n in range(10):
    add_task = taskqueue_service_pb2.TaskQueueAddRequest()
    add_task.app_id = bytes(TEST_PROJECT, 'utf8')
    add_task.queue_name = queue_bytes
    add_task.mode = taskqueue_service_pb2.TaskQueueMode.PULL
    add_task.task_name = b'task-%d' % n
    add_task.body = b'some-payload-%d' % n
    add_task.eta_usec = 0
    tasks.append(add_task)
  bulk_add = taskqueue_service_pb2.TaskQueueBulkAddRequest()
  bulk_add.add_request.extend(tasks[:5])

  # Add tasks using single and bulk add
  await taskqueue.protobuf('BulkAdd', bulk_add)
  asyncio_tasks = []
  for task in tasks[5:]:
    asyncio_tasks.append(taskqueue.protobuf('Add', task))
  await asyncio.wait(asyncio_tasks)
  remote_time = await taskqueue.remote_time_usec()

  # Lease 10 tasks for 5 second
  lease_req = taskqueue_service_pb2.TaskQueueQueryAndOwnTasksRequest()
  lease_req.queue_name = queue_bytes
  lease_req.lease_seconds = 5
  lease_req.max_tasks = 10
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  # Make sure eta_usec is ~5s greater than current remote_time
  assert all(
    task.eta_usec == pytest.approx(remote_time + 5_000_000, abs=300_000 + delay)
    for task in leased.task
  )

  # Make a pause greater than absolute precision of approx comparison
  time.sleep(0.6)
  remote_time = await taskqueue.remote_time_usec()

  # Prolong lease for 6 seconds
  prolong_requests = []
  for task in leased.task:
    req = taskqueue_service_pb2.TaskQueueModifyTaskLeaseRequest()
    req.queue_name = queue_bytes
    req.task_name = task.task_name
    req.eta_usec = task.eta_usec
    req.lease_seconds = 6
    prolong_requests.append(taskqueue.protobuf('ModifyTaskLease', req))
  # Wait for multiple responses
  (done_tasks, _), delay = await timed(asyncio.wait)(prolong_requests)
  responses = [asyncio_task.result() for asyncio_task in done_tasks]
  actual = [resp.updated_eta_usec for resp in responses]
  expected = [pytest.approx(remote_time + 6_000_000, abs=300_000 + delay)] * 10
  # Make sure updated_eta_usec is 6s greater than start_time
  assert actual == expected

  # Verify listed tasks
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue_str}/tasks')
  actual = [int(task['leaseTimestamp']) for task in listed.json['items']]
  expected = [pytest.approx(remote_time + 6_000_000, abs=300_000 + delay)] * 10
  # Make sure leaseTimestamp is what we expect
  assert actual == expected
  assert (  # Make sure all tasks are in place
    set(task['id'] for task in listed.json['items'])
    == set(str(task.task_name, 'utf8') for task in tasks)
  )

  # Delete tasks
  req = taskqueue_service_pb2.TaskQueueDeleteRequest()
  req.queue_name = queue_bytes
  req.task_name.extend([task.task_name for task in leased.task])
  await taskqueue.protobuf('Delete', req)
  # Verify that queue is empty
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue_str}/tasks')
  assert listed.json == {'kind': 'taskqueues#tasks'}  # items should be missing


@async_test
async def test_add_lease_retry_retry_delete_pg(taskqueue):
  # Initialize tasks
  queue_str = 'pull-queue-5-retry'
  queue_bytes = bytes(queue_str, 'utf8')
  add_tasks = []
  for n in range(4):
    add_task = taskqueue_service_pb2.TaskQueueAddRequest()
    add_task.app_id = bytes(TEST_PROJECT, 'utf8')
    add_task.queue_name = queue_bytes
    add_task.mode = taskqueue_service_pb2.TaskQueueMode.PULL
    add_task.task_name = b'task-%d' % n
    add_task.body = b'some-payload-%d' % n
    add_task.eta_usec = 0
    add_tasks.append(add_task)
  bulk_add = taskqueue_service_pb2.TaskQueueBulkAddRequest()
  bulk_add.add_request.extend(add_tasks)
  start_time = await taskqueue.remote_time_usec()
  total_delay = 0

  # Add tasks using bulk add
  _, delay = await taskqueue.timed_protobuf('BulkAdd', bulk_add)
  total_delay += delay

  # Lease 4 tasks for 2 seconds
  lease_req = taskqueue_service_pb2.TaskQueueQueryAndOwnTasksRequest()
  lease_req.queue_name = queue_bytes
  lease_req.lease_seconds = 2
  lease_req.max_tasks = 4
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == [1, 1, 1, 1]
  # Try to lease 4 tasks for 2 seconds
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == []

  # Give 3 seconds for lease to expire
  time.sleep(3)

  # Lease 2 tasks for 2 seconds (retry)
  lease_req.max_tasks = 2
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == [2, 2]

  # Lease 2 tasks for 2 seconds (retry)
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == [2, 2]

  # Try to lease 2 tasks for 2 seconds
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == []

  # Give 3 seconds for lease to expire
  time.sleep(3)

  # Try to lease 3 tasks for 2 seconds
  lease_req.max_tasks = 3
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == [3, 3, 3]

  # Give 3 seconds for lease to expire
  time.sleep(3)

  # Try to lease 3 tasks for 2 seconds
  leased, delay = await taskqueue.timed_protobuf('QueryAndOwnTasks', lease_req)
  total_delay += delay
  assert [task.retry_count for task in leased.task] == [3, 4, 4]

  # Verify listed tasks
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue_str}/tasks')
  sorting_key = lambda item: (item['retry_count'], int(item['leaseTimestamp']))
  tasks = sorted(listed.json['items'], key=sorting_key)
  actual = [(task['retry_count'], int(task['leaseTimestamp'])) for task in tasks]
  expected = [
    (3, pytest.approx(start_time + 8_000_000, abs=300_000 + total_delay)),
    (3, pytest.approx(start_time + 11_000_000, abs=300_000 + total_delay)),
    (4, pytest.approx(start_time + 11_000_000, abs=300_000 + total_delay)),
    (4, pytest.approx(start_time + 11_000_000, abs=300_000 + total_delay)),
  ]
  assert actual == expected

  # Delete tasks
  req = taskqueue_service_pb2.TaskQueueDeleteRequest()
  req.queue_name = queue_bytes
  req.task_name.extend([task.task_name for task in add_tasks])
  await taskqueue.protobuf('Delete', req)
  # Verify that queue is empty
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue_str}/tasks')
  assert listed.json == {'kind': 'taskqueues#tasks'}  # items should be missing
