import logging
import os
import time

import gevent
import locust
import psutil
from locust.exception import StopLocust

from helpers import taskqueue_service_pb2
from base_locust import TaskQueueLocust
from prepare_queues import PULL_QUEUE, RETRY_LIMIT

# Maximum number of tasks to lease by a single request
MAX_TASKS = 30
# Number of seconds to lease tasks for
LEASE_SECONDS = 30

PRODUCER_PID = int(os.environ['PRODUCERS_PID'])


class Worker(TaskQueueLocust):
  """
  Virtual TaskQueue user processing tasks
  """

  # Last time when at least one task was leased
  LAST_LEASE_TIME = time.time()

  class WorkerTasks(locust.TaskSet):
    """
    Set of actions (locust tasks) performed by worker
    """

    @locust.task(20)
    def lease(self):
      """ Locust action performed by worker.
      Sends lease request to TaskQueue protobuffer API.
      Reports leased tasks to validation log. Deletes tasks which
      suppose to be done according to scenario.
      """
      # Lease tasks
      lease_req = taskqueue_service_pb2.TaskQueueQueryAndOwnTasksRequest()
      lease_req.queue_name = bytes(PULL_QUEUE, 'utf8')
      lease_req.lease_seconds = LEASE_SECONDS
      lease_req.max_tasks = MAX_TASKS
      with self.client.protobuf('QueryAndOwnTasks', lease_req) as leased:
        # Report what tasks were leased
        for task in leased.task:
          self.locust.log_action(
            'LEASED', str(task.task_name, 'utf8'), int(task.eta_usec / 1000)
          )

        # Parse payload to see how long should take task execution
        if not leased.task:
          return
        Worker.LAST_LEASE_TIME = time.time()
        tasks_info = [self.get_task_info(task) for task in leased.task]

        # Assuming that virtual tasks can be run in parallel
        work_time_ms = max(work_time for task, work_time, should_fail
                           in tasks_info)
        gevent.sleep(work_time_ms / 1000)

        # Determine tasks that should not be retried
        tasks_to_delete = [task for task, work_time, should_fail
                           in tasks_info if not should_fail]

        # Delete tasks
        delete_req = taskqueue_service_pb2.TaskQueueDeleteRequest()
        delete_req.queue_name = bytes(PULL_QUEUE, 'utf8')
        delete_req.task_name.extend([task.task_name for task in tasks_to_delete])
        with self.client.protobuf('Delete', delete_req):
          # Report what tasks were deleted
          for task in tasks_to_delete:
            self.locust.log_action(
              'DELETED', str(task.task_name, 'utf8'), f'{task.retry_count}'
            )

    @locust.task(5)
    def list(self):
      """ This locust task verifies if producers are terminated
      and, if they are, checks number of tasks left in queue.
      When queue is empty it triggers sys.exit(0)
      """
      try:
        producer_process = psutil.Process(PRODUCER_PID)
        if './producer_locust.py' in producer_process.cmdline():
          return
      except psutil.NoSuchProcess:
        pass

      with self.client.rest('GET', path_suffix=f'/{PULL_QUEUE}/tasks') as resp:
        tasks = resp.json().get('items', [])
        active_tasks = [
          # It would have to be ` < RETRY_LIMIT`, but out TQ works in wrong way
          task for task in tasks if task['retry_count'] <= RETRY_LIMIT + 1
        ]
        if active_tasks:
          return

        if Worker.LAST_LEASE_TIME + LEASE_SECONDS + 150 < time.time():
          logging.info(
            'producer_locust is already terminated and we couldn\'t find '
            'any active tasks (which did not exhausted retries) in queue. '
            f'No tasks were leased during last {LEASE_SECONDS + 150} seconds.'
          )
          raise StopLocust('All work seems to be done')

    @staticmethod
    def get_task_info(task):
      """ Parses task payload containing execution scenario.

      Returns:
        a tuple of (task, work_time, should_fail)
      """
      bytes_work_times, bytes_noise = task.body.split(b':', 1)
      task_work_times = [
        float(str(item, 'utf8')) for item in bytes_work_times.split(b' ')
      ]
      # Payload contains list of work times for each retry
      try:
        work_time = task_work_times[task.retry_count - 1]
      except IndexError:
        # Work times list specified in payload declares wanted number of retries
        # But shit happens.. worker may fail to execute task for reason unknown
        work_time = task_work_times[-1]
      # Tasks means to be failed if another work time is specified in payload
      should_fail = len(task_work_times) > task.retry_count
      return task, work_time, should_fail

  task_set = WorkerTasks
  min_wait = 800
  max_wait = 1200
