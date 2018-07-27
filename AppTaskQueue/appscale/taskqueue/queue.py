import datetime
import json
import re
import sys
import uuid

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.cassandra_env.retry_policies import (
  BASIC_RETRIES,
  NO_RETRIES
)
from appscale.datastore.dbconstants import TRANSIENT_CASSANDRA_ERRORS
from cassandra import DriverException
from cassandra.query import BatchStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from collections import deque
from threading import Lock
from .constants import AGE_LIMIT_REGEX
from .constants import EmptyQueue
from .constants import InvalidQueueConfiguration
from .constants import RATE_REGEX
from .constants import TaskNotFound
from .task import InvalidTaskInfo
from .task import Task
from .utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue.taskqueue import MAX_QUEUE_NAME_LENGTH

# This format is used when returning the long name of a queue as
# part of a leased task. This is to mimic a GCP oddity/bug.
LONG_QUEUE_FORM = 'projects/{app}/taskqueues/{queue}'

# A regex rule for validating queue names.
FULL_QUEUE_NAME_PATTERN = r'^(projects/[a-zA-Z0-9-]+/taskqueues/)?' \
                     r'[a-zA-Z0-9-]{1,%s}$' % MAX_QUEUE_NAME_LENGTH

# A compiled regex rule for validating queue names.
FULL_QUEUE_NAME_RE = re.compile(FULL_QUEUE_NAME_PATTERN)

# All possible fields to include in a queue's JSON representation.
QUEUE_FIELDS = (
  'kind', 'id', 'maxLeases',
  {'stats': ('totalTasks', 'oldestTask', 'leasedLastMinute', 'leasedLastHour')}
)

# Validation rules for queue parameters.
QUEUE_ATTRIBUTE_RULES = {
  'rate': lambda rate: RATE_REGEX.match(rate),
  'task_retry_limit': lambda limit: limit >= 0,
  'task_age_limit': lambda limit: (limit is None or
                                   AGE_LIMIT_REGEX.match(limit)),
  'min_backoff_seconds': lambda seconds: seconds >= 0,
  'max_backoff_seconds': lambda seconds: seconds >= 0,
  'max_doublings': lambda doublings: doublings >= 0
}


def current_time_ms():
  """ Gets the current time with millisecond precision. This allows the server
  to return exactly what Cassandra will store.

  Returns:
    A datetime object with the current time.
  """
  now = datetime.datetime.utcnow()
  new_microsecond = int(now.microsecond / 1000) * 1000
  return now.replace(microsecond=new_microsecond)


def next_key(key):
  """ Calculates the next partition value of a key. Note: Cassandra BOP orders
  'b' before 'aa'.

  Args:
    key: A string containing a Cassandra key.
  Returns:
    A string containing the next partition value.
  """
  mutable_key = list(key)
  mutable_key[-1] = chr(ord(key[-1]) + 1)
  return ''.join(mutable_key)


class InvalidLeaseRequest(Exception):
  pass


class TransientError(Exception):
  """ Indicates that the queue was unable to complete an operation. """
  pass


class Queue(object):
  """ Represents a queue created by an App Engine application. """

  # Attributes that may not be defined.
  OPTIONAL_ATTRS = ['rate', 'task_age_limit', 'min_backoff_seconds',
                    'max_backoff_seconds', 'max_doublings']

  # The default number of task retries for a queue.
  DEFAULT_RETRY_LIMIT = 0

  def __init__(self, queue_info, app):
    """ Create a Queue object.

    Args:
      queue_info: A dictionary containing queue info.
      app: A string containing the application ID.
    """
    self.app = app

    if 'name' not in queue_info:
      raise InvalidQueueConfiguration(
        'Queue requires a name: {}'.format(queue_info))
    self.name = queue_info['name']

    self.task_retry_limit = self.DEFAULT_RETRY_LIMIT
    if 'retry_parameters' in queue_info:
      retry_params = queue_info['retry_parameters']
      if 'task_retry_limit' in retry_params:
        self.task_retry_limit = retry_params['task_retry_limit']

    self.validate_config()
    self.prepared_statements = {}

  def validate_config(self):
    """ Ensures all of the Queue's attributes are valid.

    Raises:
      InvalidQueueConfiguration if there is an invalid attribute.
    """
    for attribute, rule in QUEUE_ATTRIBUTE_RULES.iteritems():
      try:
        value = getattr(self, attribute)
      except AttributeError:
        continue

      if not rule(value):
        message = 'Invalid queue configuration for {queue}.{param}: {value}'\
          .format(queue=self.name, param=attribute, value=value)
        raise InvalidQueueConfiguration(message)

  def __eq__(self, other):
    """ Checks if this Queue is equivalent to another.

    Returns:
      A boolean indicating whether or not the two Queues are equal.
    """
    if not isinstance(other, self.__class__):
      return False

    if self.app != other.app or self.name != other.name:
      return False

    for attribute in self.OPTIONAL_ATTRS:
      if hasattr(self, attribute):
        if not hasattr(other, attribute):
          return False
        if getattr(self, attribute) != getattr(other, attribute):
          return False
      else:
        if hasattr(other, attribute):
          return False

    return True

  def __ne__(self, other):
    """ Checks if this Queue is different than another.

    Returns:
      A boolean indicating whether or not the two Queues are different.
    """
    return not self.__eq__(other)

class PushQueue(Queue):
  # The default rate for push queues.
  DEFAULT_RATE = '5/s'

  # The queue default time limit for retrying a failed push task.
  DEFAULT_AGE_LIMIT = None

  # The default minimum number of seconds to wait before retrying push tasks.
  DEFAULT_MIN_BACKOFF = .1

  # The default maximum number of seconds to wait before retrying push tasks.
  DEFAULT_MAX_BACKOFF = 3600.0

  # The default max number of times to double the interval between retries.
  DEFAULT_MAX_DOUBLINGS = 16

  def __init__(self, queue_info, app):
    """ Create a PushQueue object.

    Args:
      queue_info: A dictionary containing queue info.
      app: A string containing the application ID.
    """
    self.rate = self.DEFAULT_RATE
    if 'rate' in queue_info:
      self.rate = queue_info['rate']
    self.target = queue_info.get('target')
    self.task_age_limit = self.DEFAULT_AGE_LIMIT
    self.min_backoff_seconds = self.DEFAULT_MIN_BACKOFF
    self.max_backoff_seconds = self.DEFAULT_MAX_BACKOFF
    self.max_doublings = self.DEFAULT_MAX_DOUBLINGS
    if 'retry_parameters' in queue_info:
      retry_params = queue_info['retry_parameters']
      if 'task_age_limit' in retry_params:
        self.task_age_limit = retry_params['task_age_limit']
      if 'min_backoff_seconds' in retry_params:
        self.min_backoff_seconds = retry_params['min_backoff_seconds']
      if 'max_backoff_seconds' in retry_params:
        self.max_backoff_seconds = retry_params['max_backoff_seconds']
      if 'max_doublings' in retry_params:
        self.max_doublings = retry_params['max_doublings']

    self.celery = None

    super(PushQueue, self).__init__(queue_info, app)

  def __repr__(self):
    """ Generates a string representation of the queue.
    Returns:
      A string representing the PushQueue.
    """
    attributes = {'app': self.app,
                  'task_retry_limit': self.task_retry_limit}
    for attribute in self.OPTIONAL_ATTRS:
      if hasattr(self, attribute):
        attributes[attribute] = getattr(self, attribute)

    attr_str = ', '.join('{}={}'.format(attr, val)
                         for attr, val in attributes.iteritems())

    return '<PushQueue {}: {}>'.format(self.name, attr_str)


class PullQueue(Queue):
  # The maximum number of tasks that can be leased at a time.
  MAX_LEASE_AMOUNT = 1000

  # Tasks can be leased for up to a week.
  MAX_LEASE_TIME = 60 * 60 * 24 * 7

  # The maximum number of index entries to cache.
  MAX_CACHE_SIZE = 500

  # The number of seconds to keep the index cache.
  MAX_CACHE_DURATION = 30

  # The seconds to wait after fetching 0 index results before retrying.
  EMPTY_RESULTS_COOLDOWN = 5

  def __init__(self, queue_info, app, db_access=None):
    """ Create a PullQueue object.

    Args:
      queue_info: A dictionary containing queue info.
      app: A string containing the application ID.
      db_access: A DatastoreProxy object.
    """
    self.db_access = db_access
    self.index_cache = {'global': {}, 'by_tag': {}}
    self.index_cache_lock = Lock()
    super(PullQueue, self).__init__(queue_info, app)

  def add_task(self, task, retries=5):
    """ Adds a task to the queue.

    Args:
      task: A Task object.
      retries: The number of times to retry adding the task.
    Raises:
      InvalidTaskInfo if the task ID already exists in the queue.
    """
    if not hasattr(task, 'payloadBase64'):
      raise InvalidTaskInfo('{} is missing a payload.'.format(task))

    enqueue_time = datetime.datetime.utcnow()
    try:
      lease_expires = task.leaseTimestamp
    except AttributeError:
      lease_expires = datetime.datetime.utcfromtimestamp(0)

    parameters = {
      'app': self.app,
      'queue': self.name,
      'id': task.id,
      'payload': task.payloadBase64,
      'enqueued': enqueue_time,
      'retry_count': 0,
      'lease_expires': lease_expires,
      'op_id': uuid.uuid4()
    }

    try:
      parameters['tag'] = task.tag
    except AttributeError:
      parameters['tag'] = None

    self._insert_task(parameters, retries)

    task.queueName = self.name
    task.enqueueTimestamp = enqueue_time
    task.leaseTimestamp = lease_expires

    # Create index entries so the task can be queried by ETA and (tag, ETA).
    # This can't be done in a batch because the payload from the previous
    # insert can be up to 1MB, and Cassandra does not approve of large batches.
    try:
      tag = task.tag
    except AttributeError:
      # The API does not differentiate between empty and unspecified tags.
      tag = ''

    insert_eta_index = SimpleStatement("""
      INSERT INTO pull_queue_tasks_index (app, queue, eta, id, tag)
      VALUES (%(app)s, %(queue)s, %(eta)s, %(id)s, %(tag)s)
    """, retry_policy=BASIC_RETRIES)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'eta': task.get_eta(),
      'id': task.id,
      'tag': tag
    }
    self.db_access.session.execute(insert_eta_index, parameters)

    insert_tag_index = SimpleStatement("""
      INSERT INTO pull_queue_tags_index (app, queue, tag, eta, id)
      VALUES (%(app)s, %(queue)s, %(tag)s, %(eta)s, %(id)s)
    """, retry_policy=BASIC_RETRIES)
    self.db_access.session.execute(insert_tag_index, parameters)

    logger.debug('Added task: {}'.format(task))

  def get_task(self, task, omit_payload=False):
    """ Gets a task from the queue.

    Args:
      task: A Task object.
      omit_payload: A boolean indicating that the payload should not be
        fetched.
    Returns:
      A task object or None.
    """
    payload = 'payload,'
    if omit_payload:
      payload = ''
    select_task = """
      SELECT {payload} enqueued, lease_expires, retry_count, tag
      FROM pull_queue_tasks
      WHERE app = %(app)s AND queue = %(queue)s AND id = %(id)s
    """.format(payload=payload)
    statement = SimpleStatement(select_task,
                                consistency_level=ConsistencyLevel.SERIAL)
    parameters = {'app': self.app, 'queue': self.name, 'id': task.id}
    try:
      response = self.db_access.session.execute(statement, parameters)[0]
    except IndexError:
      return None

    task_info = {
      'id': task.id,
      'queueName': self.name,
      'enqueueTimestamp': response.enqueued,
      'leaseTimestamp': response.lease_expires,
      'retry_count': response.retry_count,
    }

    if response.tag is not None:
      task_info['tag'] = response.tag

    if not omit_payload:
      task_info['payloadBase64'] = response.payload

    return Task(task_info)

  def delete_task(self, task):
    """ Deletes a task from the queue.

    Args:
      task: A Task object.
    """
    # Retrieve the ETA info so that the index can also be deleted.
    task = self.get_task(task, omit_payload=True)
    if task is not None:
      self._delete_task_and_index(task)

    logger.debug('Deleted task: {}'.format(task))

  def update_lease(self, task, new_lease_seconds, retries=5):
    """ Updates the duration of a task lease.

    Args:
      task: A Task object.
      new_lease_seconds: An integer specifying when to set the new ETA. It
        represents the number of seconds from now.
      retries: The number of times to try the update.
    Returns:
      A Task object.
    """
    new_eta = current_time_ms() + datetime.timedelta(seconds=new_lease_seconds)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'id': task.id,
      'old_eta': task.get_eta(),
      'new_eta': new_eta,
      'current_time': datetime.datetime.utcnow(),
      'op_id': uuid.uuid4()
    }
    self._update_lease(parameters, retries)

    task.leaseTimestamp = new_eta
    return task

  def update_task(self, task, new_lease_seconds, retries=5):
    """ Updates leased tasks.

    Args:
      task: A task object.
      new_lease_seconds: An integer specifying when to set the new ETA. It
        represents the number of seconds from now.
      retries: The number of times to try the update.
    """
    new_eta = current_time_ms() + datetime.timedelta(seconds=new_lease_seconds)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'id': task.id,
      'new_eta': new_eta,
      'current_time': datetime.datetime.utcnow(),
      'op_id': uuid.uuid4()
    }

    try:
      old_eta = task.leaseTimestamp
    except AttributeError:
      old_eta = None
    if old_eta == datetime.datetime.utcfromtimestamp(0):
      old_eta = None

    if old_eta is not None:
      parameters['old_eta'] = old_eta
      self._update_lease(parameters, retries)
    else:
      self._update_lease(parameters, retries, check_lease=False)

    task.leaseTimestamp = new_eta
    return task

  def list_tasks(self, limit=100):
    """ List all non-deleted tasks in the queue.

    Args:
      limit: An integer specifying the maximum number of tasks to list.
    Returns:
      A list of Task objects.
    """
    session = self.db_access.session

    tasks = []
    start_date = datetime.datetime.utcfromtimestamp(0)
    task_id = ''
    while True:
      query_tasks = """
        SELECT eta, id FROM pull_queue_tasks_index
        WHERE token(app, queue, eta, id) > token(%(app)s, %(queue)s, %(eta)s, %(id)s)
        AND token(app, queue, eta, id) < token(%(app)s, %(next_queue)s, 0, '')
        LIMIT {limit}
      """.format(limit=limit)
      parameters = {'app': self.app, 'queue': self.name, 'eta': start_date,
                    'id': task_id, 'next_queue': next_key(self.name)}
      results = [result for result in session.execute(query_tasks, parameters)]

      if not results:
        break

      satisfied_request = False
      for result in results:
        task = self.get_task(Task({'id': result.id}), omit_payload=True)
        if task is None:
          self._delete_index(result.eta, result.id, result.tag)
          continue

        tasks.append(task)
        if len(tasks) >= limit:
          satisfied_request = True
          break
      if satisfied_request:
        break

      # Update the cursor.
      start_date = results[-1].eta
      task_id = results[-1].id

    return tasks

  def lease_tasks(self, num_tasks, lease_seconds, group_by_tag=False,
                  tag=None):
    """ Acquires a lease on tasks from the queue.

    Args:
      num_tasks: An integer specifying the number of tasks to lease.
      lease_seconds: An integer specifying how long to lease the tasks.
      group_by_tag: A boolean indicating that only tasks of one tag should
        be leased.
      tag: A string containing the tag for the task.
    Returns:
      A list of Task objects.
    """
    if num_tasks > self.MAX_LEASE_AMOUNT:
      raise InvalidLeaseRequest(
        'Only {} tasks can be leased at a time'.format(self.MAX_LEASE_AMOUNT))

    if lease_seconds > self.MAX_LEASE_TIME:
      raise InvalidLeaseRequest('Tasks can only be leased for up to {} seconds'
                                .format(self.MAX_LEASE_TIME))

    start_time = datetime.datetime.utcnow()
    logger.debug('Leasing {} tasks for {} sec. group_by_tag={}, tag={}'.
                 format(num_tasks, lease_seconds, group_by_tag, tag))
    # If not specified, the tag is assumed to be that of the oldest task.
    if group_by_tag and tag is None:
      try:
        tag = self._get_earliest_tag()
      except EmptyQueue:
        return []

    # Fetch available tasks and try to lease them until the requested number
    # has been leased or until the index has been exhausted.
    leased = []
    leased_ids = set()
    indices_seen = set()
    new_eta = None
    while True:
      tasks_needed = num_tasks - len(leased)
      if tasks_needed < 1:
        break

      try:
        index_results = self._query_available_tasks(
          tasks_needed, group_by_tag, tag)
      except TRANSIENT_CASSANDRA_ERRORS:
        raise TransientError('Unable to query available tasks')

      # The following prevents any task from being leased multiple times in the
      # same request. If the lease time is very small, it's possible for the
      # lease to expire while results are still being fetched.
      index_results = [result for result in index_results
                       if result.id not in leased_ids]

      # If there are no more available tasks, return whatever has been leased.
      if not index_results:
        break

      # Determine new_eta when the first index_results are received
      if new_eta is None:
        new_eta = current_time_ms() + datetime.timedelta(seconds=lease_seconds)

      lease_results = self._lease_batch(index_results, new_eta)
      for index_num, index_result in enumerate(index_results):
        task = lease_results[index_num]
        if task is None:
          # If this lease request has previously encountered this index, it's
          # likely that either the index is invalid or that the task has
          # exceeded its retry_count.
          if index_result.id in indices_seen:
            self._resolve_task(index_result)
          indices_seen.add(index_result.id)
          continue

        leased.append(task)
        leased_ids.add(task.id)

    time_elapsed = datetime.datetime.utcnow() - start_time
    logger.debug('Leased {} tasks [time elapsed: {}]'.format(len(leased), str(time_elapsed)))
    logger.debug('IDs leased: {}'.format([task.id for task in leased]))
    return leased

  def total_tasks(self):
    """ Get the total number of tasks in the queue.

    Returns:
      An integer specifying the number of tasks in the queue.
    """
    select_count = """
      SELECT COUNT(*) FROM pull_queue_tasks
      WHERE token(app, queue, id) >= token(%(app)s, %(queue)s, '')
      AND token(app, queue, id) < token(%(app)s, %(next_queue)s, '')
    """
    parameters = {'app': self.app, 'queue': self.name,
                  'next_queue': next_key(self.name)}
    return self.db_access.session.execute(select_count, parameters)[0].count

  def oldest_eta(self):
    """ Get the ETA of the oldest task

    Returns:
      A datetime object specifying the oldest ETA or None if there are no
      tasks.
    """
    session = self.db_access.session
    select_oldest = """
      SELECT eta FROM pull_queue_tasks_index
      WHERE token(app, queue, eta, id) >= token(%(app)s, %(queue)s, 0, '')
      AND token(app, queue, eta, id) < token(%(app)s, %(next_queue)s, 0, '')
      LIMIT 1
    """
    parameters = {'app': self.app, 'queue': self.name,
                  'next_queue': next_key(self.name)}
    try:
      return session.execute(select_oldest, parameters)[0].eta
    except IndexError:
      return None

  def purge(self):
    """ Remove all tasks from queue.

    Cassandra cannot perform a range scan during a delete, so this function
    selects all the tasks before deleting them one at a time.
    """
    select_tasks = """
      SELECT id, enqueued, lease_expires, tag FROM pull_queue_tasks
      WHERE token(app, queue, id) >= token(%(app)s, %(queue)s, '')
      AND token(app, queue, id) < token(%(app)s, %(next_queue)s, '')
    """
    parameters = {'app': self.app, 'queue': self.name,
                  'next_queue': next_key(self.name)}
    results = self.db_access.session.execute(select_tasks, parameters)

    for result in results:
      task_info = {'id': result.id,
                   'enqueueTimestamp': result.enqueued,
                   'leaseTimestamp': result.lease_expires,
                   'tag': result.tag}
      self._delete_task_and_index(Task(task_info))

  def to_json(self, include_stats=False, fields=None):
    """ Generate a JSON representation of the queue.

    Args:
      include_stats: A boolean indicating whether or not to include stats.
      fields: A tuple of fields to include in the output.
    Returns:
      A string in JSON format representing the queue.
    """
    if fields is None:
      fields = QUEUE_FIELDS

    queue = {}
    if 'kind' in fields:
      queue['kind'] = 'taskqueues#taskqueue'

    if 'id' in fields:
      queue['id'] = self.name

    if 'maxLeases' in fields:
      queue['maxLeases'] = self.task_retry_limit

    stat_fields = ()
    for field in fields:
      if isinstance(field, dict) and 'stats' in field:
        stat_fields = field['stats']

    if stat_fields and include_stats:
      queue['stats'] = self._get_stats(fields=stat_fields)

    return json.dumps(queue)

  def _task_mutated_by_id(self, task_id, op_id):
    """ Checks if the task entry was last mutated with the given ID.

    Args:
      task_id: A string specifying the task ID.
      op_id: A uuid identifying a process that tried to mutate the task.
    Returns:
      A boolean indicating that the task was last mutated with the ID.
    """
    select_statement = SimpleStatement("""
      SELECT op_id FROM pull_queue_tasks
      WHERE app = %(app)s AND queue = %(queue)s AND id = %(id)s
    """, consistency_level=ConsistencyLevel.SERIAL)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'id': task_id,
      'op_id': op_id
    }
    try:
      result = self.db_access.session.execute(select_statement, parameters)[0]
    except IndexError:
      raise TaskNotFound('Task does not exist: {}'.format(task_id))

    return result.op_id == op_id

  def _insert_task(self, parameters, retries):
    """ Insert task entry into pull_queue_tasks.

    Args:
      parameters: A dictionary specifying the task parameters.
      retries: The number of times to try the insert.
    Raises:
      InvalidTaskInfo if the task ID already exists in the queue.
    """
    insert_statement = SimpleStatement("""
      INSERT INTO pull_queue_tasks (
        app, queue, id, payload,
        enqueued, lease_expires, retry_count, tag, op_id
      )
      VALUES (
        %(app)s, %(queue)s, %(id)s, %(payload)s,
        %(enqueued)s, %(lease_expires)s, %(retry_count)s, %(tag)s, %(op_id)s
      )
      IF NOT EXISTS
    """, retry_policy=NO_RETRIES)
    try:
      result = self.db_access.session.execute(insert_statement, parameters)
    except TRANSIENT_CASSANDRA_ERRORS as error:
      retries_left = retries - 1
      if retries_left <= 0:
        raise
      logger.warning(
        'Encountered error while inserting task: {}. Retrying.'.format(error))
      return self._insert_task(parameters, retries_left)

    if result.was_applied:
      return

    try:
      success = self._task_mutated_by_id(parameters['id'], parameters['op_id'])
    except TaskNotFound:
      raise TransientError('Unable to insert task')

    if not success:
      raise InvalidTaskInfo(
        'Task name already taken: {}'.format(parameters['id']))

  def _update_lease(self, parameters, retries, check_lease=True):
    """ Update lease expiration on a task entry.

    Args:
      parameters: A dictionary specifying the new parameters.
      retries: The number of times to try the update.
      check_lease: A boolean specifying that the old lease_expires field must
        match the one provided.
    Raises:
      InvalidLeaseRequest if the lease has already expired.
    """
    update_task = """
      UPDATE pull_queue_tasks
      SET lease_expires = %(new_eta)s, op_id = %(op_id)s
      WHERE app = %(app)s AND queue = %(queue)s AND id = %(id)s
      IF lease_expires > %(current_time)s
    """

    # When reporting errors, GCP does not differentiate between a lease
    # expiration and the client providing the wrong old_eta.
    if check_lease:
      update_task += 'AND lease_expires = %(old_eta)s'

    update_statement = SimpleStatement(update_task, retry_policy=NO_RETRIES)
    try:
      result = self.db_access.session.execute(update_statement, parameters)
    except TRANSIENT_CASSANDRA_ERRORS as error:
      retries_left = retries - 1
      if retries_left <= 0:
        raise
      logger.warning(
        'Encountered error while updating lease: {}. Retrying.'.format(error))
      return self._update_lease(parameters, retries_left,
                                check_lease=check_lease)

    if result.was_applied:
      return

    if not self._task_mutated_by_id(parameters['id'], parameters['op_id']):
      raise InvalidLeaseRequest('The task lease has expired.')

  def _query_index(self, num_tasks, group_by_tag, tag):
    """ Query the index table for available tasks.

    Args:
      num_tasks: An integer specifying the number of tasks to lease.
      group_by_tag: A boolean indicating that only tasks of one tag should
        be leased.
      tag: A string containing the tag for the task.

    Returns:
      A list of results from the index table.
    """
    if group_by_tag:
      query_tasks = """
        SELECT tag, eta, id FROM pull_queue_tags_index
        WHERE token(app, queue, tag, eta, id) >= token(%(app)s, %(queue)s, %(tag)s, 0, '')
        AND token(app, queue, tag, eta, id) <= token(%(app)s, %(queue)s, %(tag)s, dateof(now()), '')
        LIMIT {limit}
      """.format(limit=num_tasks)
      parameters = {'app': self.app, 'queue': self.name, 'tag': tag}
      results = self.db_access.session.execute(query_tasks, parameters)
    else:
      query_tasks = """
        SELECT eta, id, tag FROM pull_queue_tasks_index
        WHERE token(app, queue, eta, id) >= token(%(app)s, %(queue)s, 0, '')
        AND token(app, queue, eta, id) <= token(%(app)s, %(queue)s, dateof(now()), '')
        LIMIT {limit}
      """.format(limit=num_tasks)
      parameters = {'app': self.app, 'queue': self.name}
      results = self.db_access.session.execute(query_tasks, parameters)
    return results

  def _query_available_tasks(self, num_tasks, group_by_tag, tag):
    """ Query the cache or index table for available tasks.

    Args:
      num_tasks: An integer specifying the number of tasks to lease.
      group_by_tag: A boolean indicating that only tasks of one tag should
        be leased.
      tag: A string containing the tag for the task.

    Returns:
      A list of index results.
    """
    # If the request is larger than the max cache size, don't use the cache.
    if num_tasks > self.MAX_CACHE_SIZE:
      return self._query_index(num_tasks, group_by_tag, tag)

    with self.index_cache_lock:
      if group_by_tag:
        if tag not in self.index_cache['by_tag']:
          self.index_cache['by_tag'][tag] = {}
        tag_cache = self.index_cache['by_tag'][tag]
      else:
        tag_cache = self.index_cache['global']

      # If results have never been fetched, populate the cache.
      if not tag_cache:
        results = self._query_index(self.MAX_CACHE_SIZE, group_by_tag, tag)
        tag_cache['queue'] = deque(results)
        tag_cache['last_fetch'] = datetime.datetime.now()
        tag_cache['last_results'] = len(tag_cache['queue'])

      # If 0 results were fetched recently, don't try fetching again.
      recently = datetime.datetime.now() - datetime.timedelta(
        seconds=self.EMPTY_RESULTS_COOLDOWN)
      if (not tag_cache['queue'] and tag_cache['last_results'] == 0 and
          tag_cache['last_fetch'] > recently):
        return []

      # If the cache is outdated or insufficient, update it.
      outdated = datetime.datetime.now() - datetime.timedelta(
        seconds=self.MAX_CACHE_DURATION)
      if (num_tasks > len(tag_cache['queue']) or
          tag_cache['last_fetch'] < outdated):
        results = self._query_index(self.MAX_CACHE_SIZE, group_by_tag, tag)
        tag_cache['queue'] = deque(results)
        tag_cache['last_fetch'] = datetime.datetime.now()
        tag_cache['last_results'] = len(tag_cache['queue'])

      results = []
      for _ in range(num_tasks):
        try:
          results.append(tag_cache['queue'].popleft())
        except IndexError:
          # The queue is empty.
          break

      return results

  def _get_earliest_tag(self):
    """ Get the tag with the earliest ETA.

    Returns:
      A string containing a tag.
    Raises:
      EmptyQueue if there are no tasks.
    """
    get_earliest_tag = """
      SELECT tag FROM pull_queue_tasks_index
      WHERE token(app, queue, eta, id) > token(%(app)s, %(queue)s, 0, '')
      LIMIT 1
    """
    parameters = {'app': self.app, 'queue': self.name}
    try:
      tag = self.db_access.session.execute(get_earliest_tag, parameters)[0].tag
    except IndexError:
      raise EmptyQueue('No entries in queue index')
    return tag

  def _increment_count_async(self, task):
    """ Update retry count for a task.

    Args:
      task: A Task object.
    """
    session = self.db_access.session

    statement = """
      UPDATE pull_queue_tasks
      SET retry_count=?
      WHERE app=? AND queue=? AND id=?
      IF retry_count=?
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    update_count = self.prepared_statements[statement]

    old_count = task.retry_count
    new_count = task.retry_count + 1
    params = [new_count, self.app, self.name, task.id, old_count]
    bound_update = update_count.bind(params)
    bound_update.retry_policy = NO_RETRIES
    self.db_access.session.execute_async(bound_update)

  def _lease_batch(self, indexes, new_eta):
    """ Acquires a lease on tasks in the queue.

    Args:
      indexes: An iterable containing results from the index table.
      new_eta: A datetime object containing the new lease expiration.

    Returns:
      A list of task objects or None if unable to acquire a lease.
    """
    leased = [None for _ in indexes]
    session = self.db_access.session
    op_id = uuid.uuid4()

    lease_statement = """
      UPDATE pull_queue_tasks
      SET lease_expires = ?, op_id = ?
      WHERE app = ? AND queue = ? AND id = ?
      IF lease_expires < ?
    """
    if self.task_retry_limit != 0:
      lease_statement += 'AND retry_count < {}'.format(self.task_retry_limit)
    lease_task = session.prepare(lease_statement)
    lease_task.retry_policy = NO_RETRIES
    current_time = datetime.datetime.utcnow()

    update_futures = []
    for index in indexes:
      params = (new_eta, op_id, self.app, self.name, index.id, current_time)
      update_futures.append(session.execute_async(lease_task, params))

    # Check which lease operations succeeded.
    statement = """
      SELECT payload, enqueued, retry_count, tag, op_id
      FROM pull_queue_tasks
      WHERE app=? AND queue=? AND id=?
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    select = self.prepared_statements[statement]

    futures = {}
    for result_num, update_future in enumerate(update_futures):
      try:
        result = update_future.result()
        success = True
      except DriverException:
        result = None
        success = False

      if success and not result.was_applied:
        # The lease operation failed, so keep this index as None.
        continue

      index = indexes[result_num]
      bound_select = select.bind([self.app, self.name, index.id])
      bound_select.consistency_level = ConsistencyLevel.SERIAL
      future = session.execute_async(bound_select)
      futures[result_num] = (future, not success)

    index_update_futures = []
    for result_num, (future, lease_timed_out) in futures.iteritems():
      index = indexes[result_num]
      try:
        read_result = future.result()[0]
      except (TRANSIENT_CASSANDRA_ERRORS, IndexError):
        raise TransientError('Unable to read task {}'.format(index.id))

      # If the operation IDs do not match, the lease was not successful.
      if lease_timed_out and read_result.op_id != op_id:
        continue

      task_info = {
        'queueName': self.name,
        'id': index.id,
        'payloadBase64': read_result.payload,
        'enqueueTimestamp': read_result.enqueued,
        'leaseTimestamp': new_eta,
        'retry_count': read_result.retry_count
      }
      if read_result.tag:
        task_info['tag'] = read_result.tag
      task = Task(task_info)
      leased[result_num] = task

      self._increment_count_async(task)
      index_update_futures.append(self._update_index_async(index, task))
      self._update_stats()

    # Make sure all of the index updates complete successfully.
    for index_update in index_update_futures:
      index_update.result()

    return leased

  def _update_index_async(self, old_index, task):
    """ Updates the index table after leasing a task.

    Args:
      old_index: The row to remove from the index table.
      task: A Task object to create a new index entry for.
    Returns:
      A cassandra-driver future.
    """
    session = self.db_access.session

    old_eta = old_index.eta
    update_index = BatchStatement(retry_policy=BASIC_RETRIES)

    statement = """
      DELETE FROM pull_queue_tasks_index
      WHERE app=?
      AND queue=?
      AND eta=?
      AND id=?
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    delete_old_eta_index = self.prepared_statements[statement]

    parameters = [self.app, self.name, old_eta, task.id]
    update_index.add(delete_old_eta_index, parameters)

    statement = """
      DELETE FROM pull_queue_tags_index
      WHERE app=?
      AND queue=?
      AND tag=?
      AND eta=?
      AND id=?
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    delete_old_tag_index = self.prepared_statements[statement]

    parameters = [self.app, self.name, old_index.tag, old_eta, task.id]
    update_index.add(delete_old_tag_index, parameters)

    try:
      tag = task.tag
    except AttributeError:
      tag = ''

    statement = """
      INSERT INTO pull_queue_tasks_index (app, queue, eta, id, tag)
      VALUES (?, ?, ?, ?, ?)
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    create_new_eta_index = self.prepared_statements[statement]

    parameters = [self.app, self.name, task.leaseTimestamp, task.id, tag]
    update_index.add(create_new_eta_index, parameters)

    statement = """
      INSERT INTO pull_queue_tags_index (app, queue, tag, eta, id)
      VALUES (?, ?, ?, ?, ?)
    """
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    create_new_tag_index = self.prepared_statements[statement]

    parameters = [self.app, self.name, tag, task.leaseTimestamp, task.id]
    update_index.add(create_new_tag_index, parameters)

    return self.db_access.session.execute_async(update_index)

  def _delete_index(self, eta, task_id, tag):
    """ Deletes an index entry for a task.

    Args:
      eta: A datetime object.
      task_id: A string containing the task ID.
      tag: A string containing the task tag.
    """
    delete_eta_index = """
      DELETE FROM pull_queue_tasks_index
      WHERE app = %(app)s
      AND queue = %(queue)s
      AND eta = %(eta)s
      AND id = %(id)s
    """
    parameters = {'app': self.app, 'queue': self.name, 'eta': eta,
                  'id': task_id}
    self.db_access.session.execute(delete_eta_index, parameters)

    delete_tag_index = """
      DELETE FROM pull_queue_tags_index
      WHERE app = %(app)s
      AND queue = %(queue)s
      AND tag = %(tag)s
      AND eta = %(eta)s
      AND id = %(id)s
    """
    parameters = {'app': self.app, 'queue': self.name, 'tag': tag, 'eta': eta,
                  'id': task_id}
    self.db_access.session.execute(delete_tag_index, parameters)

  def _delete_task_and_index(self, task, retries=5):
    """ Deletes a task and its index.

    Args:
      task: A Task object.
    """
    delete_task = SimpleStatement("""
      DELETE FROM pull_queue_tasks
      WHERE app = %(app)s AND queue = %(queue)s AND id = %(id)s
      IF EXISTS
    """, retry_policy=NO_RETRIES)
    parameters = {'app': self.app, 'queue': self.name, 'id': task.id}
    try:
      self.db_access.session.execute(delete_task, parameters=parameters)
    except TRANSIENT_CASSANDRA_ERRORS as error:
      retries_left = retries - 1
      if retries_left <= 0:
        raise
      logger.warning(
        'Encountered error while deleting task: {}. Retrying.'.format(error))
      return self._delete_task_and_index(task, retries=retries_left)

    delete_task_eta_index = SimpleStatement("""
      DELETE FROM pull_queue_tasks_index
      WHERE app = %(app)s
      AND queue = %(queue)s
      AND eta = %(eta)s
      AND id = %(id)s
    """)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'eta': task.get_eta(),
      'id': task.id
    }
    self.db_access.session.execute(delete_task_eta_index, parameters=parameters)

    try:
      tag = task.tag
    except AttributeError:
      tag = ''

    delete_task_tag_index = SimpleStatement("""
      DELETE FROM pull_queue_tags_index
      WHERE app = %(app)s
      AND queue = %(queue)s
      AND tag = %(tag)s
      AND eta = %(eta)s
      AND id = %(id)s
    """)
    parameters = {
      'app': self.app,
      'queue': self.name,
      'tag': tag,
      'eta': task.get_eta(),
      'id': task.id
    }
    self.db_access.session.execute(delete_task_tag_index, parameters=parameters)

  def _resolve_task(self, index):
    """ Cleans up expired tasks and indices.

    Args:
      index: An index result.
    """
    task = self.get_task(Task({'id': index.id}), omit_payload=True)
    if task is None:
      self._delete_index(index.eta, index.id, index.tag)
      return

    if self.task_retry_limit != 0 and task.expired(self.task_retry_limit):
      self._delete_task_and_index(task)
      return

    # If the index does not match the task, update it.
    if task.leaseTimestamp != index.eta:
      self._update_index_async(index, task).result()

  def _update_stats(self):
    """ Write queue metadata for keeping track of statistics. """
    session = self.db_access.session
    # Stats are only kept for one hour.
    ttl = 60 * 60
    statement = """
      INSERT INTO pull_queue_leases (app, queue, leased)
      VALUES (?, ?, ?)
      USING TTL {ttl}
    """.format(ttl=ttl)
    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = session.prepare(statement)
    record_lease = self.prepared_statements[statement]

    parameters = [self.app, self.name, datetime.datetime.utcnow()]
    self.db_access.session.execute_async(record_lease, parameters)

  def _get_stats(self, fields):
    """ Fetch queue statistics.

    Args:
      fields: A tuple of fields to include in the results.
    Returns:
      A dictionary containing queue statistics.
    """
    session = self.db_access.session
    stats = {}

    if 'totalTasks' in fields:
      stats['totalTasks'] = self.total_tasks()

    if 'oldestTask' in fields:
      epoch = datetime.datetime.utcfromtimestamp(0)
      oldest_eta = self.oldest_eta() or epoch
      stats['oldestTask'] = int((oldest_eta - epoch).total_seconds())

    if 'leasedLastMinute' in fields:
      select_count = """
        SELECT COUNT(*) from pull_queue_leases
        WHERE token(app, queue, leased) > token(%(app)s, %(queue)s, %(ts)s)
        AND token(app, queue, leased) <=
            token(%(app)s, %(queue)s, dateof(now()))
      """
      start_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
      parameters = {'app': self.app, 'queue': self.name, 'ts': start_time}
      leased_last_minute = session.execute(select_count, parameters)[0].count
      stats['leasedLastMinute'] = leased_last_minute

    if 'leasedLastHour' in fields:
      select_count = """
        SELECT COUNT(*) from pull_queue_leases
        WHERE token(app, queue, leased) > token(%(app)s, %(queue)s, %(ts)s)
        AND token(app, queue, leased) <=
            token(%(app)s, %(queue)s, dateof(now()))
      """
      start_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=60)
      parameters = {'app': self.app, 'queue': self.name, 'ts': start_time}
      leased_last_hour = session.execute(select_count, parameters)[0].count
      stats['leasedLastHour'] = leased_last_hour

    return stats

  def __repr__(self):
    """ Generates a string representation of the queue.

    Returns:
      A string representing the PullQueue.
    """
    return '<PullQueue {}: app={}, task_retry_limit={}>'.format(
      self.name, self.app, self.task_retry_limit)
