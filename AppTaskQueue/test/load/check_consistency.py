import argparse
import logging
import os
import sys
import time

import requests

import attr

from prepare_queues import RETRY_LIMIT


@attr.s(cmp=False, hash=False, slots=True)
class TaskHistory(object):
  """
  Represents information about all actions related
  to a particular task according to validation log.
  """
  created_ms = attr.ib()
  scenario = attr.ib()                                  # List of work times
  lease_attempts = attr.ib(default=attr.Factory(list))  # List of tuples (EVENT_TIME, LEASE_EXPIRES)
  deleted_ms = attr.ib(default=None)
  final_retry_count = attr.ib(default=None)


@attr.s(cmp=False, hash=False, slots=True)
class Stats(object):
  """
  Represents main properties of TaskQueue activity
  according to validation log.
  """
  started_ms = attr.ib(default=sys.maxsize)
  total_adds = attr.ib(default=0)
  failed_adds = attr.ib(default=0)
  duplicated_adds = attr.ib(default=0)
  total_leases = attr.ib(default=0)
  early_leases = attr.ib(default=0)
  denied_retries = attr.ib(default=0)
  exhausted_retries = attr.ib(default=0)
  stalled = attr.ib(default=0)
  total_deletions = attr.ib(default=0)
  duplicated_deletions = attr.ib(default=0)
  refs_to_unknown = attr.ib(default=0)
  finished_ms = attr.ib(default=0)
  execution_time_ms = attr.ib(default=0)


class Validator(object):
  """
  Class performing validation of TaskQueue activity log.
  """

  # tasks and stats attributes are frequently accessed (millions of times)
  # during logs validation, so it worth to make it slots
  __slots__ = ('stats', 'tasks', 'time_diff_ms',
               'producer_files', 'worker_files')

  def __init__(self, logs_dir, tq_location=None):
    self.stats = Stats()
    self.tasks = {}
    self.producer_files = []
    self.worker_files = []

    if tq_location:
      # Compute approximate difference between local time and TQ server time
      try:
        response = requests.get(f'http://{tq_location}/service-stats')
        response.raise_for_status()
        current_remote_time_ms = response.json()['cumulative_counters']['to']
      except requests.HTTPError as err:
        logging.debug(f'Failed to get remote time ({err}). '
                      f'Assuming it is equal to local.')
        current_remote_time_ms = time.time() * 1_000
      self.time_diff_ms = int(time.time() * 1000 - current_remote_time_ms)
    else:
      self.time_diff_ms = 0

    self.find_relevant_logs(logs_dir)
    self.parse_producer_files()
    self.parse_worker_files()
    self.verify_lease_history()
    self.stats.execution_time_ms = self.stats.finished_ms - self.stats.started_ms

  def find_relevant_logs(self, logs_dir):
    """ Walks though all files in logs_dir
    and picks activity log files.
    """
    for root, dirs, files in os.walk(logs_dir):
      for filename in files:
        if filename.startswith('Producers-'):
          self.producer_files.append(os.path.join(root, filename))
        if filename.startswith('Workers-'):
          self.worker_files.append(os.path.join(root, filename))

  def parse_producer_files(self):
    """ Parses producers activity log.
    Fills TaskHistory instances and Stats object.
    """
    for producer_file in self.producer_files:
      with open(producer_file) as log:
        for line in log:
          self.stats.total_adds += 1
          timestamp_str, status, task_name, work_times = line.split(' ', 3)
          event_timestamp = int(timestamp_str)
          self.stats.started_ms = min(self.stats.started_ms, event_timestamp)
          self.stats.finished_ms = max(self.stats.finished_ms, event_timestamp)
          if status != 'ADDED':
            logging.debug(f'Failure in producer log: {line}')
            self.stats.failed_adds += 1
            continue
          if task_name in self.tasks:
            logging.debug(f'Duplicated task: {task_name}')
            self.stats.duplicated_adds += 1
            continue
          task = TaskHistory(created_ms=event_timestamp,
                             scenario=[int(t) for t in work_times.split()])
          self.tasks[task_name] = task

  def parse_worker_files(self):
    """ Parses workers activity log.
    Fills TaskHistory instances and Stats object.
    """
    for worker_file in self.worker_files:
      with open(worker_file) as log:
        for line in log:
          timestamp_str, op, task_name, op_info = line.split(' ', 3)
          event_timestamp = int(timestamp_str)
          self.stats.started_ms = min(self.stats.started_ms, event_timestamp)
          self.stats.finished_ms = max(self.stats.finished_ms, event_timestamp)
          task = self.tasks.get(task_name)
          if not task:
            logging.debug(f'Referring to unknown task: {line}')
            self.stats.refs_to_unknown += 1
            continue
          if op == 'LEASED':
            self.stats.total_leases += 1
            lease_expires = int(op_info)
            lease_attempt = (event_timestamp, self.local_time_ms(lease_expires))
            task.lease_attempts.append(lease_attempt)
            continue
          if op == 'DELETED':
            self.stats.total_deletions += 1
            if task.deleted_ms:
              logging.debug(f'Duplicated deletion: {task_name}')
              self.stats.duplicated_deletions += 1
              continue
            retry_count = int(op_info)
            task.deleted_ms = event_timestamp
            task.final_retry_count = retry_count
            continue

  def verify_lease_history(self):
    """ Verifies lease history of every known task.
    Reports any issues to Stats object.
    """
    for task_name, task in self.tasks.items():
      prev_lease_expires = 0
      for lease_request_time, new_lease_expires in task.lease_attempts:
        # Allow 1 second overlay as remote time is manually adjusted to local
        if lease_request_time + 1000 < prev_lease_expires:
          logging.debug(f'Task {task_name} was leased '
                        f'before previous lease was expired')
          self.stats.early_leases += 1
        prev_lease_expires = new_lease_expires

      if len(task.lease_attempts) > RETRY_LIMIT + 1:
        logging.debug(f'Task {task_name} was leased '
                      f'though it ran out of retries')
        self.stats.denied_retries += 1

      if task.deleted_ms is None:
        if len(task.lease_attempts) != RETRY_LIMIT + 1:
          logging.debug(f'Task {task_name} left stalled '
                        f'before exhausting retries limit')
          self.stats.stalled += 1
        else:
          self.stats.exhausted_retries += 1

  def local_time_ms(self, remote_time_ms):
    """ Adjusts remote time to a local time.

    Returns:
      an integer representing remote time shifted to a local time.
    """
    return remote_time_ms + self.time_diff_ms

  def validate_consistency_and_exit(self, ignore_exceeded_retry_limit):
    """ Verifies collected information. Reports warnings for
    any inconsistency and exits with proper exit code.
    """
    finished_tasks = self.stats.total_deletions + self.stats.exhausted_retries
    is_consistent = all((
      self.stats.duplicated_adds == 0,
      self.stats.early_leases == 0,
      self.stats.denied_retries == 0 or ignore_exceeded_retry_limit,
      self.stats.stalled == 0,
      self.stats.duplicated_deletions == 0,
      self.stats.refs_to_unknown == 0,
      self.stats.total_adds == finished_tasks
    ))
    if not is_consistent:
      msg = 'TaskQueue activity log is not consistent:'
      if self.stats.duplicated_adds:
        msg += (f'\n - {self.stats.duplicated_adds} tasks were added '
                f'more than once during the test')
      if self.stats.early_leases:
        msg += (f'\n - {self.stats.early_leases} tasks were leased '
                f'before previous lease was expired')
      if self.stats.denied_retries and not ignore_exceeded_retry_limit:
        msg += (f'\n - {self.stats.denied_retries} tasks were leased '
                f'after exhausting retries')
      if self.stats.stalled:
        msg += f'\n - {self.stats.stalled} tasks left stalled'
      if self.stats.duplicated_deletions:
        msg += (f'\n - {self.stats.duplicated_deletions} tasks were deleted '
                f'more than once during the test')
      if self.stats.refs_to_unknown:
        msg += (f'\n - {self.stats.refs_to_unknown} unknown tasks were '
                f'either leased or deleted')
      if self.stats.total_adds != finished_tasks:
        msg += (f'\n - Number of added tasks ({self.stats.total_adds}) is '
                f'not equal to sum of deleted ({self.stats.total_deletions}) '
                f'and exhausted ({self.stats.exhausted_retries})')
      logging.error(msg)
      sys.exit(1)
    else:
      logging.info(f'TaskQueue activity log looks consistent')
      sys.exit(0)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--validation-log",
                      help="Directory containing validation log.")
  parser.add_argument("--taskqueue-location", default=None,
                      help="Taskqueue location (for syncing with remote time)")
  parser.add_argument("--ignore-exceeded-retry-limit", action="store_true",
                      help="Ignore tasks with exceeded retry limit.")
  parser.add_argument("--verbose", action="store_true",
                      help="Increase output verbosity.")
  args = parser.parse_args()

  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                      format='%(levelname)s %(message)s')

  validator = Validator(args.validation_log, args.taskqueue_location)
  stats = validator.stats
  logging.info(
    f'TaskQueue activity stats:\n'
    f' - {stats.total_adds} tasks added\n'
    f' - {stats.total_leases} times tasks were leased\n'
    f' - {stats.exhausted_retries} tasks exhausted retries\n'
    f' - {stats.total_deletions} tasks were completed successfully\n'
    f' - Test execution time is {int(stats.execution_time_ms/1000)}s'
  )
  validator.validate_consistency_and_exit(args.ignore_exceeded_retry_limit)
