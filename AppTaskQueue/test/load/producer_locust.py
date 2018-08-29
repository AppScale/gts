import itertools
import random
import uuid

import locust

from helpers import taskqueue_service_pb2
from base_locust import TEST_PROJECT, TaskQueueLocust
from prepare_queues import PULL_QUEUE

# Number of tasks added by a single BulkAdd request
BULK_SIZES = 5

# Sequence declaring number of failures to simulate
FAIL_SEQUENCE = itertools.cycle([
  0, 0, 0, 0, 0, 2, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0,
  0, 2, 0, 2, 0, 0, 0, 1, 1, 0, 3, 0, 0, 1, 0, 0, 4, 0, 0, 0, 1, 0, 1, 1, 1, 0,
  1, 1, 2, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 2, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0,
  0, 2, 2, 0, 2, 0, 2, 0, 0, 1, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 0, 2, 3,
  0, 0, 2, 1, 0, 1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 3, 0, 0, 0,
  0, 0, 0, 0, 2, 0, 3, 2, 0, 0, 0, 0, 0, 2, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0,
  2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 1, 2, 2, 0, 1, 2, 1,
  3, 1, 2, 1, 1, 0, 1, 2, 1, 1, 0, 2, 0, 0, 2, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 2
])

# Sequence declaring how long should take processing of a task
WORK_TIME = itertools.cycle([
  1739, 56, 745, 26, 216, 13950, 37, 8852, 3, 9, 100, 2993, 9163, 3424, 6065,
  4381, 5270, 2365, 2293, 847, 2567, 9, 5276, 67, 68, 1456, 90, 2668, 9, 64,
  37, 33, 92, 3502, 34, 50, 584, 61, 71, 1854, 523, 427, 65, 19, 1589, 41, 207,
  9077, 10, 831, 58, 33, 4370, 84, 2225, 7, 9405, 76, 4960, 94, 9011, 7974, 65,
  90, 3283, 33, 4229, 45, 93, 13080, 3197, 986, 2498, 5542, 3150, 131, 9098,
  1754, 838, 248
])

PAYLOAD_SIZES = (
  [0]*128 + [20]*64 + [100]*32 + [500]*16
  + [2500]*8 + [10000]*4 + [50000]*2 + [250000]
)
# Sequence of random byte arrays to use as payload
BIG_PAYLOADS = itertools.cycle([
  bytearray(random.getrandbits(8) for _ in range(size))
  for size in PAYLOAD_SIZES
])


class Producer(TaskQueueLocust):
  """
  Virtual TaskQueue user producing tasks
  """

  class ProducerTasks(locust.TaskSet):
    """
    Set of actions (locust tasks) performed by producer
    """

    @locust.task
    def add_tasks(self):
      """ The only action performed by producer.
      Sends BulkAdd request to TaskQueue protobuffer API.
      Every added task is reported to validation log.
      """
      bulk_add = taskqueue_service_pb2.TaskQueueBulkAddRequest()
      tasks = {}
      for _ in range(BULK_SIZES):
        add_task = bulk_add.add_request.add()
        add_task.app_id = bytes(TEST_PROJECT, 'utf8')
        add_task.queue_name = bytes(PULL_QUEUE, 'utf8')
        add_task.mode = taskqueue_service_pb2.TaskQueueMode.PULL
        add_task.task_name = bytes(str(uuid.uuid4()), 'utf8')
        work_times = self.generate_work_times()
        add_task.body = bytes(work_times, 'utf8') + b':' + next(BIG_PAYLOADS)
        add_task.eta_usec = 0
        tasks[add_task.task_name] = work_times

      # Send request to TaskQueue
      with self.client.protobuf('BulkAdd', bulk_add) as response:
        # Report what tasks were added
        for task in response.taskresult:
          if task.result == taskqueue_service_pb2.TaskQueueServiceError.OK:
            self.locust.log_action(
              'ADDED', str(task.chosen_task_name, 'utf8'),
              tasks[task.chosen_task_name]
            )
          else:
            self.locust.log_action(task.result, '?', '?')

    @staticmethod
    def generate_work_times():
      """ Generates a string representing execution scenario for a task.
      The string is space-separated list of numbers.
      Every number corresponds to task processing attempt and tells
      worker how long should take execution of a task.
      """
      simulate_failures = next(FAIL_SEQUENCE)
      work_time_seq = (str(next(WORK_TIME))
                       for _ in range(simulate_failures + 1))
      return ' '.join(work_time_seq)

  task_set = ProducerTasks
  min_wait = 800
  max_wait = 1200
