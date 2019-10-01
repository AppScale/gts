import datetime

import base64
import json
import sys

import psycopg2

from appscale.common import retrying
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

from .pg_connection_wrapper import pg_wrapper
from .constants import AGE_LIMIT_REGEX
from .constants import InvalidQueueConfiguration
from .constants import RATE_REGEX
from .task import InvalidTaskInfo
from .task import Task
from .utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)


# This format is used when returning the long name of a queue as
# part of a leased task. This is to mimic a GCP oddity/bug.
LONG_QUEUE_FORM = 'projects/{app}/taskqueues/{queue}'

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


class InvalidLeaseRequest(Exception):
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
    for attribute, rule in QUEUE_ATTRIBUTE_RULES.items():
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
                         for attr, val in attributes.items())

    return '<PushQueue {}: {}>'.format(self.name, attr_str)


def is_connection_error(err):
  """ This function is used as retry criteria.

  Args:
    err: an instance of Exception.
  Returns:
    True if error is related to connection, False otherwise.
  """
  return isinstance(err, psycopg2.InterfaceError)


retry_pg_connection = retrying.retry(
  retrying_timeout=10, retry_on_exception=is_connection_error
)


class PostgresPullQueue(Queue):
  """
  Before using Postgres implementation, make sure that
  connection using appscale user can be created:
  /etc/postgresql/9.5/main/pg_hba.conf
  """

  TTL_INTERVAL_AFTER_DELETED = '7 days'

  # The maximum number of tasks that can be leased at a time.
  MAX_LEASE_AMOUNT = 1000

  # Tasks can be leased for up to a week.
  MAX_LEASE_TIME = 60 * 60 * 24 * 7

  # The maximum number of index entries to cache.
  MAX_CACHE_SIZE = 500

  # The number of seconds to keep the index cache.
  MAX_CACHE_DURATION = 30

  def __init__(self, queue_info, app, queue_id):
    """ Create a PostgresPullQueue object.

    Args:
      queue_info: A dictionary containing queue info.
      app: A string containing the application ID.
    """
    super(PostgresPullQueue, self).__init__(queue_info, app)
    self.queue_id = queue_id
    self.schema_name = self.get_schema_name(app)
    self.tasks_table_name = self.get_tasks_table_name(app, queue_id)

  @staticmethod
  def get_schema_name(project_id):
    return 'appscale_{}'.format(project_id)

  @classmethod
  def get_queues_table_name(cls, project_id):
    return '{}.queues'.format(cls.get_schema_name(project_id))

  @classmethod
  def get_tasks_table_name(cls, project_id, queue_id):
    return '{}.tasks_{}'.format(cls.get_schema_name(project_id), queue_id)

  @retry_pg_connection
  def add_task(self, task):
    """ Adds a task to the queue.

    Args:
      task: A Task object.
    Raises:
      InvalidTaskInfo if the task ID already exists in the queue
        or it doesn't have payloadBase64 attribute.
    """
    if not hasattr(task, 'payloadBase64'):
      raise InvalidTaskInfo('{} is missing a payload.'.format(task))

    # TODO: remove decoding when task.payloadBase64
    #       is replaced with task.payload
    params = {
      'task_name': task.id,
      'payload': bytearray(base64.urlsafe_b64decode(task.payloadBase64)),
      'lease_count': 0,
      'tag': getattr(task, 'tag', None)
    }

    try:
      lease_expires = '%(lease_expires_val)s'
      params['lease_expires_val'] = task.leaseTimestamp
    except AttributeError:
      lease_expires = 'current_timestamp'

    pg_connection = pg_wrapper.get_connection()
    try:
      with pg_connection:
        with pg_connection.cursor() as pg_cursor:
          pg_cursor.execute(
            'INSERT INTO "{table}" ( '
            '  task_name, payload, time_enqueued, '
            '  lease_expires, lease_count, tag '
            ')'
            'VALUES ( '
            '  %(task_name)s, %(payload)s, current_timestamp, '
            '  {lease_expires}, %(lease_count)s, %(tag)s '
            ') '
            'RETURNING time_enqueued, lease_expires'
            .format(table=self.tasks_table_name, lease_expires=lease_expires),
            vars=params
          )
          row = pg_cursor.fetchone()
    except psycopg2.IntegrityError:
      name_taken_msg = 'Task name already taken: {}'.format(task.id)
      raise InvalidTaskInfo(name_taken_msg)

    logger.debug('Added task: {}'.format(task))

    task.queueName = self.name
    task.enqueueTimestamp = row[0]  # time_enqueued is generated on PG side
    task.leaseTimestamp = row[1]    # lease_expires is generated on PG side

  @retry_pg_connection
  def get_task(self, task, omit_payload=False):
    """ Gets a task from the queue.

    Args:
      task: A Task object.
      omit_payload: A boolean indicating that the payload should not be
        fetched.
    Returns:
      A task object or None.
    """
    if omit_payload:
      columns = ['task_name', 'time_enqueued',
                 'lease_expires', 'lease_count', 'tag']
    else:
      columns = ['payload', 'task_name', 'time_enqueued',
                 'lease_expires', 'lease_count', 'tag']
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT {columns} FROM "{tasks_table}" '
          'WHERE task_name = %(task_name)s AND time_deleted IS NULL'
          .format(columns=', '.join(columns),
                  tasks_table=self.tasks_table_name),
          vars={
            'task_name': task.id,
          }
        )
        row = pg_cursor.fetchone()

    if not row:
      return None
    return self._task_from_row(columns, row, id=task.id)

  @retry_pg_connection
  def delete_task(self, task):
    """ Marks a task as deleted. It will be permanently removed later
     (after TTL_INTERVAL_AFTER_DELETED).

    Args:
      task: A Task object.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'UPDATE "{tasks_table}" '
          'SET time_deleted = current_timestamp '
          'WHERE "{tasks_table}".task_name = %(task_name)s'
          .format(tasks_table=self.tasks_table_name),
          vars={
            'task_name': task.id,
          }
        )

  @retry_pg_connection
  def update_lease(self, task, new_lease_seconds):
    """ Updates the duration of a task lease.

    Args:
      task: A Task object.
      new_lease_seconds: An integer specifying when to set the new ETA. It
        represents the number of seconds from now.
    Returns:
      A Task object.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'UPDATE "{tasks_table}" '
          'SET lease_expires = '
          '  current_timestamp + interval \'%(lease_seconds)s seconds\' '
          'WHERE task_name = %(task_name)s '
          '  AND lease_expires > current_timestamp '
          '  AND lease_expires = %(old_eta)s '
          '  AND time_deleted IS NULL '
          'RETURNING lease_expires'
          .format(tasks_table=self.tasks_table_name),
          vars={
            'task_name': task.id,
            'old_eta': task.get_eta(),
            'lease_seconds': new_lease_seconds
          }
        )
        if pg_cursor.statusmessage != 'UPDATE 1':
          logger.info('Expected to get status "UPDATE 1", got: "{}"'
                      .format(pg_cursor.statusmessage))
          raise InvalidLeaseRequest('The task lease has expired')

        row = pg_cursor.fetchone()

    task.leaseTimestamp = row[0]
    return task

  @retry_pg_connection
  def update_task(self, task, new_lease_seconds):
    """ Updates leased tasks.

    Args:
      task: A task object.
      new_lease_seconds: An integer specifying when to set the new ETA. It
        represents the number of seconds from now.
    """
    statement = (
      'UPDATE "{tasks_table}" '
      'SET lease_expires = '
      '  current_timestamp + interval \'%(lease_seconds)s seconds\' '
      'WHERE task_name = %(task_name)s '
      '  AND lease_expires > current_timestamp '
      '  {old_eta_verification} '
      '  AND time_deleted IS NULL '
      'RETURNING lease_expires'
    )
    parameters = {
      'task_name': task.id,
      'lease_seconds': new_lease_seconds
    }

    # Make sure we don't override concurrent lease
    try:
      old_eta = task.leaseTimestamp
    except AttributeError:
      old_eta = None

    if old_eta is not None:
      old_eta_verification = 'AND lease_expires = %(old_eta)s'
      parameters['old_eta'] = old_eta
    else:
      old_eta_verification = ''

    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          statement.format(tasks_table=self.tasks_table_name,
                           old_eta_verification=old_eta_verification),
          vars=parameters
        )
        if pg_cursor.statusmessage != 'UPDATE 1':
          logger.info('Expected to get status "UPDATE 1", got: "{}"'
                      .format(pg_cursor.statusmessage))
          raise InvalidLeaseRequest('The task lease has expired')

        row = pg_cursor.fetchone()

    task.leaseTimestamp = row[0]
    return task

  @retry_pg_connection
  def list_tasks(self, limit=100):
    """ List all non-deleted tasks in the queue.

    Args:
      limit: An integer specifying the maximum number of tasks to list.
    Returns:
      A list of Task objects.
    """
    columns = ['task_name', 'time_enqueued',
               'lease_expires', 'lease_count', 'tag']
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT {columns} FROM "{tasks_table}" '
          'WHERE time_deleted IS NULL '
          'ORDER BY lease_expires'
          .format(columns=', '.join(columns),
                  tasks_table=self.tasks_table_name)
        )
        rows = pg_cursor.fetchmany(size=limit)
        tasks = [self._task_from_row(columns, row) for row in rows]

    return tasks

  @retry_pg_connection
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
      raise InvalidLeaseRequest('Only {} tasks can be leased at a time'
                                .format(self.MAX_LEASE_AMOUNT))

    if lease_seconds > self.MAX_LEASE_TIME:
      raise InvalidLeaseRequest('Tasks can only be leased for up to {} seconds'
                                .format(self.MAX_LEASE_TIME))

    start_time = datetime.datetime.utcnow()
    logger.debug('Leasing {} tasks for {} sec. group_by_tag={}, tag={}'.
                 format(num_tasks, lease_seconds, group_by_tag, tag))
    # If not specified, the tag is assumed to be that of the oldest task.
    if group_by_tag and tag is None:
      tag = self._get_earliest_tag()
      if tag is None:
        return []

    # Determine tag condition for the query
    tag_condition = ''
    if group_by_tag:
      tag_condition = ' AND tag = %(tag)s'

    # Determine max retries condition for the query
    max_retries_condition = ''
    if self.task_retry_limit:
      max_retries_condition = ' AND lease_count < %(max_retries)s'

    columns = ['task_name', 'payload', 'time_enqueued',
               'lease_expires', 'lease_count', 'tag']
    full_column_names = [
      '"{table}".{col}'.format(table=self.tasks_table_name, col=column)
      for column in columns
    ]
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'UPDATE "{tasks_table}" '
          'SET lease_expires = '
          '      current_timestamp + interval \'%(lease_seconds)s seconds\', '
          '    lease_count = lease_count + 1 '
          'FROM ( '
          '  SELECT task_name FROM "{tasks_table}" '
          '  WHERE time_deleted IS NULL '        # Tell PG to use partial index
          '        AND lease_expires < current_timestamp '
          '        {retry_limit} '
          '        {tag_filter} '
          '  ORDER BY lease_expires '
          '  FOR UPDATE SKIP LOCKED '
          '  LIMIT {num_tasks} '
          ') as tasks_to_update '
          'WHERE "{tasks_table}".task_name = tasks_to_update.task_name '
          'RETURNING {columns}'
          .format(columns=', '.join(full_column_names),
                  retry_limit=max_retries_condition, tag_filter=tag_condition,
                  num_tasks=num_tasks, tasks_table=self.tasks_table_name),
          vars={
            'lease_seconds': lease_seconds,
            'max_retries': self.task_retry_limit,
            'tag': tag
          }
        )
        rows = pg_cursor.fetchall()
        leased = [self._task_from_row(columns, row) for row in rows]

    time_elapsed = datetime.datetime.utcnow() - start_time
    logger.debug('Leased {} tasks [time elapsed: {}]'
                 .format(len(leased), str(time_elapsed)))
    return leased

  @retry_pg_connection
  def purge(self):
    """ Remove all tasks from queue.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'TRUNCATE TABLE "{tasks_table}"'
          .format(tasks_table=self.tasks_table_name)
        )

  def to_json(self, include_stats=False, fields=None):
    """ Generate a JSON representation of the queue.
    It doesn't provide leasedLastMinute and leasedLastHour fields.

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
      queue['stats'] = self._get_stats(stat_fields)

    return json.dumps(queue)

  @retry_pg_connection
  def total_tasks(self):
    """ Get the total number of tasks in the queue.

    Returns:
      An integer specifying the number of tasks in the queue.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT count(*) FROM "{tasks_table}" WHERE time_deleted IS NULL'
          .format(tasks_table=self.tasks_table_name)
        )
        tasks_count = pg_cursor.fetchone()[0]
    return tasks_count

  @retry_pg_connection
  def oldest_eta(self):
    """ Get the ETA of the oldest task

    Returns:
      A datetime object specifying the oldest ETA or None if there are no
      tasks.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT min(lease_expires) FROM "{tasks_table}" '
          'WHERE time_deleted IS NULL'
          .format(tasks_table=self.tasks_table_name)
        )
        oldest_eta = pg_cursor.fetchone()[0]
    return oldest_eta

  @retry_pg_connection
  def flush_deleted(self):
    """ Removes all tasks which were deleted more than week ago.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'DELETE FROM "{tasks_table}" '
          'WHERE time_deleted < current_timestamp - interval \'{ttl}\''
          .format(tasks_table=self.tasks_table_name,
                  ttl=self.TTL_INTERVAL_AFTER_DELETED)
        )
        logger.info('Flushed deleted tasks from {} with status: {}'
                    .format(self.tasks_table_name, pg_cursor.statusmessage))

  COLUMN_ATTR_MAPPING = {
    'task_name': 'id',
    'payload': 'payload',  # it's converted to payloadBase64 in _task_from_row
    'time_enqueued': 'enqueueTimestamp',
    'lease_expires': 'leaseTimestamp',
    'lease_count': 'retry_count',
    'tag': 'tag'
  }

  def _task_from_row(self, columns, row, **other_attrs):
    """ Helper function for building Task object from DB row.

    Args:
      columns: a list of DB column names.
      row: a tuple of values.
      other_attrs: other attributes to be set in Task object.
    Returns:
      an instance of Task.
    """
    task_info = {
      self.COLUMN_ATTR_MAPPING[column]: value
      for column, value in zip(columns, row)
    }
    task_info.update(other_attrs)
    task_info['queueName'] = self.name

    # TODO: remove it when task.payloadBase64 is replaced with task.payload
    if 'payload' in columns:
      payload = task_info.pop('payload')
      task_info['payloadBase64'] = \
        base64.urlsafe_b64encode(payload).decode('utf-8')

    return Task(task_info)

  @retry_pg_connection
  def _get_earliest_tag(self):
    """ Get the tag with the earliest ETA.

    Returns:
      A string containing a tag or None.
    """
    pg_connection = pg_wrapper.get_connection()
    with pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT tag FROM "{tasks_table}" '
          'WHERE time_deleted IS NULL '
          'ORDER BY lease_expires'
          .format(tasks_table=self.tasks_table_name)
        )
        row = pg_cursor.fetchone()
        tag = row[0] if row else None
        return tag

  def _get_stats(self, fields):
    """ Fetch queue statistics.
    It doesn't provide leasedLastMinute and leasedLastHour fields.

    Args:
      fields: A tuple of fields to include in the results.
    Returns:
      A dictionary containing queue statistics.
    """
    stats = {}

    if 'totalTasks' in fields:
      stats['totalTasks'] = self.total_tasks()

    if 'oldestTask' in fields:
      epoch = datetime.datetime.utcfromtimestamp(0)
      oldest_eta = self.oldest_eta() or epoch
      stats['oldestTask'] = int((oldest_eta - epoch).total_seconds())

    if 'leasedLastMinute' in fields:
      logger.warning('leasedLastMinute can\'t be provided')
      stats['leasedLastMinute'] = None

    if 'leasedLastHour' in fields:
      logger.warning('leasedLastHour can\'t be provided')
      stats['leasedLastHour'] = None

    return stats

  def __repr__(self):
    """ Generates a string representation of the queue.

    Returns:
      A string representing the PullQueue.
    """
    return '<PostgresPullQueue {}: app={}, task_retry_limit={}>'.format(
      self.name, self.app, self.task_retry_limit)


@retry_pg_connection
def ensure_project_schema_created(project_id):
  pg_connection = pg_wrapper.get_connection()
  schema_name = PostgresPullQueue.get_schema_name(project_id)
  with pg_connection:
    with pg_connection.cursor() as pg_cursor:
      logger.info('Ensuring "{schema_name}" schema is created'
                  .format(schema_name=schema_name))
      pg_cursor.execute(
        'CREATE SCHEMA IF NOT EXISTS "{schema_name}";'
        .format(schema_name=schema_name)
      )


@retry_pg_connection
def ensure_queues_table_created(project_id):
  pg_connection = pg_wrapper.get_connection()
  queues_table_name = PostgresPullQueue.get_queues_table_name(project_id)
  with pg_connection:
    with pg_connection.cursor() as pg_cursor:
      logger.info('Ensuring "{}" table is created'.format(queues_table_name))
      pg_cursor.execute(
        'CREATE TABLE IF NOT EXISTS "{queues_table}" ('
        '  id SERIAL,'
        '  queue_name varchar(100) NOT NULL UNIQUE'
        ');'
        .format(queues_table=queues_table_name)
      )


@retry_pg_connection
def ensure_queue_registered(project_id, queue_name):
  pg_connection = pg_wrapper.get_connection()
  queues_table_name = PostgresPullQueue.get_queues_table_name(project_id)
  with pg_connection:
    with pg_connection.cursor() as pg_cursor:
      pg_cursor.execute(
        'SELECT id FROM "{queues_table}" WHERE queue_name = %(queue_name)s;'
        .format(queues_table=queues_table_name),
        vars={'queue_name': queue_name}
      )
      row = pg_cursor.fetchone()
      if row:
        return row[0]

      logger.info('Registering queue "{}" in "{}" table'
                  .format(queue_name, queues_table_name))
      pg_cursor.execute(
        'INSERT INTO "{queues_table}" (queue_name) '
        'VALUES (%(queue_name)s) ON CONFLICT DO NOTHING;'
        'SELECT id FROM "{queues_table}" WHERE queue_name = %(queue_name)s;'
        .format(queues_table=queues_table_name),
        vars={'queue_name': queue_name}
      )
      row = pg_cursor.fetchone()
      logger.info('Queue "{}" was registered with ID "{}"'
                  .format(queue_name, row[0]))
      return row[0]


@retry_pg_connection
def ensure_tasks_table_created(project_id, queue_id):
  pg_connection = pg_wrapper.get_connection()
  tasks_table_name = PostgresPullQueue.get_tasks_table_name(
    project_id, queue_id
  )
  with pg_connection:
    with pg_connection.cursor() as pg_cursor:
      logger.info('Ensuring "{}" table is created'.format(tasks_table_name))
      pg_cursor.execute(
        'CREATE TABLE IF NOT EXISTS "{table_name}" ('
        '  task_name varchar(500) NOT NULL,'
        '  time_deleted timestamp DEFAULT NULL,'
        '  time_enqueued timestamp NOT NULL,'
        '  lease_count integer NOT NULL,'
        '  lease_expires timestamp NOT NULL,'
        '  payload bytea,'
        '  tag varchar(500),'
        '  PRIMARY KEY (task_name)'
        ');'
        'CREATE INDEX IF NOT EXISTS "{table_name}_eta_retry_tag_index" '
        '  ON "{table_name}" USING BTREE (lease_expires, lease_count, tag) '
        '  WHERE time_deleted IS NULL;'
        'CREATE INDEX IF NOT EXISTS "{table_name}_retry_eta_tag_index" '
        '  ON "{table_name}" (lease_count, lease_expires, tag) '
        '  WHERE time_deleted IS NULL;'
        .format(table_name=tasks_table_name)
      )
