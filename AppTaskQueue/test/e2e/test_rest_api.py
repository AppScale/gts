import base64

import pytest

from conftest import async_test


class TestGetQueue(object):

  @async_test
  async def test_get_existing_pull_queue(self, taskqueue):
    response = await taskqueue.rest('GET', path_suffix='/pull-queue-a')
    assert response.json == {
      'kind': 'taskqueues#taskqueue',
      'id': 'pull-queue-a',
      'maxLeases': 0
    }

  @async_test
  async def test_get_missing_queue(self, taskqueue):
    response = await taskqueue.rest('GET', path_suffix='/missing',
                                    raise_for_status=False)
    assert response.status == 404


@async_test
async def test_add_all_list_lease_delete_all(taskqueue):
  # Initialize queues
  queue = 'pull-queue-a'
  tasks = [
    {
      'id': f'task-{n}',
      'payloadBase64': base64.urlsafe_b64encode(b'data-%d' % n).decode('utf-8')
    }
    for n in range(10)
  ]
  all_ids = set(task['id'] for task in tasks)
  start_time = await taskqueue.remote_time_usec()

  # Add tasks
  for task in tasks:
    await taskqueue.rest('POST', path_suffix=f'/{queue}/tasks', json=task)
  # Verify what tasks are in queue
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue}/tasks')
  assert set(task['id'] for task in listed.json['items']) == all_ids
  assert all(
    int(task['leaseTimestamp']) == pytest.approx(start_time, 50_000)
    for task in listed.json['items']
  )

  # Lease tasks
  leased = await taskqueue.rest(
    'POST', path_suffix=f'/{queue}/tasks/lease', params={
      'leaseSecs': 300,
      'numTasks': 10
    }
  )
  # Verify what is leased
  assert set(task['id'] for task in leased.json['items']) == all_ids
  assert all(
    int(task['leaseTimestamp']) == pytest.approx(start_time + 300_000_000, 50_000)
    for task in leased.json['items']
  )

  # Verify what tasks are in queue
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue}/tasks')
  assert set(task['id'] for task in listed.json['items']) == all_ids
  assert all(
    int(task['leaseTimestamp']) == pytest.approx(start_time + 300_000_000, 50_000)
    for task in listed.json['items']
  )

  # Delete tasks
  for task in tasks:
    await taskqueue.rest('DELETE', path_suffix=f'/{queue}/tasks/{task["id"]}')
  # Verify that queue is empty
  listed = await taskqueue.rest('GET', path_suffix=f'/{queue}/tasks')
  assert listed.json == {'kind': 'taskqueues#tasks'}  # items should be missing

