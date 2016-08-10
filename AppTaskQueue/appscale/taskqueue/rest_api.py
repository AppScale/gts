""" Handlers for implementing v1beta2 of the taskqueue REST API. """
import sys
import tornado.escape

from queue import QueueTypes
from task import Task
from tornado.web import MissingArgumentError
from tornado.web import RequestHandler
from unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
from constants import HTTPCodes

# The prefix for all of the handlers of the pull queue REST API.
REST_PREFIX = '/taskqueue/v1beta2/projects/([a-z0-9-]+)/taskqueues'


class RESTQueue(RequestHandler):
  PATH = '{}/([a-zA-Z0-9-]+)'.format(REST_PREFIX)

  def initialize(self, queue_handler):
    """ Provide access to the queue handler. """
    self.queue_handler = queue_handler

  def get(self, project, queue):
    """ Return info about an existing queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
    """
    queue = self.queue_handler.get_queue(project, queue)
    if queue is None:
      self.set_status(HTTPCodes.NOT_FOUND)
      self.write('Queue not found.')
      return

    if queue.mode != QueueTypes.PULL:
      self.set_status(HTTPCodes.NOT_FOUND)
      self.write('The REST API is not applicable to push queues.')
      return

    self.write(queue.to_json())


class RESTTasks(RequestHandler):
  PATH = '{}/([a-zA-Z0-9-]+)/tasks'.format(REST_PREFIX)

  def initialize(self, queue_handler):
    """ Provide access to the queue handler. """
    self.queue_handler = queue_handler

  def get(self, project, queue):
    """ List all non-deleted tasks in a queue, whether or not they are
    currently leased, up to a maximum of 100.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
    """
    self.set_status(HTTPCodes.NOT_IMPLEMENTED)
    self.write('Not implemented')

  def post(self, project, queue):
    """ Insert a task into an existing queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
    """
    task_info = tornado.escape.json_decode(self.request.body)
    task = Task(task_info)

    queue = self.queue_handler.get_queue(project, queue)
    if queue is None:
      self.set_status(HTTPCodes.NOT_FOUND)
      self.write('Queue not found.')
      return

    queue.add_task(task)
    self.write(task.to_json())


class RESTLease(RequestHandler):
  PATH = '{}/([a-zA-Z0-9-]+)/tasks/lease'.format(REST_PREFIX)

  def initialize(self, queue_handler):
    """ Provide access to the queue handler. """
    self.queue_handler = queue_handler

  def post(self, project, queue):
    """ Acquire a lease on the topmost N unowned tasks in a queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
    """
    try:
      lease_seconds = int(self.get_argument('leaseSecs'))
    except (MissingArgumentError, ValueError):
      self.set_status(HTTPCodes.BAD_REQUEST)
      self.write('An integer is required for the parameter leaseSecs.')
      return

    try:
      tasks = int(self.get_argument('numTasks'))
    except (MissingArgumentError, ValueError):
      self.set_status(HTTPCodes.BAD_REQUEST)
      self.write('An integer is required for the parameter numTasks.')
      return

    try:
      group_by_tag = bool(self.get_argument('groupByTag', False))
    except ValueError:
      self.set_status(HTTPCodes.BAD_REQUEST)
      self.write('groupByTag must be a boolean.')
      return

    tag = self.get_argument('groupByTag', None)

    queue = self.queue_handler.get_queue(project, queue)
    if queue is None:
      self.set_status(HTTPCodes.BAD_REQUEST)
      self.write('Queue not found.')
      return

    queue.lease_tasks(tasks, lease_seconds, group_by_tag, tag)

class RESTTask(RequestHandler):
  PATH = '{}/([a-zA-Z0-9-]+)/tasks/([a-zA-Z0-9_-]+)'.format(REST_PREFIX)

  def initialize(self, queue_handler):
    """ Provide access to the queue handler. """
    self.queue_handler = queue_handler

  def get(self, project, queue, task):
    """ Get the named task in a queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
      task: A string containing a task ID.
    """
    task = Task({'id': task, 'queueName': queue})

    queue = self.queue_handler.get_queue(project, queue)
    if queue is None:
      self.set_status(HTTPCodes.NOT_FOUND)
      self.write('Queue not found.')
      return

    task = queue.get_task(task)
    self.write(task.to_json())

  def post(self, project, queue, task):
    """ Update the duration of a task lease.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
      task: A string containing a task ID.
    """
    self.set_status(HTTPCodes.NOT_IMPLEMENTED)
    self.write('Not implemented')

  def delete(self, project, queue, task):
    """ Delete a task from a queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
      task: A string containing a task ID.
    """
    task = Task({'id': task})

    queue = self.queue_handler.get_queue(project, queue)
    if queue is None:
      self.set_status(HTTPCodes.NOT_FOUND)
      self.write('Queue not found.')
      return

    queue.delete_task(task)

  def patch(self, project, queue, task):
    """ Update tasks that are leased out of a queue.

    Args:
      project: A string containing an application ID.
      queue: A string containing a queue name.
      task: A string containing a task ID.
    """
    self.set_status(HTTPCodes.NOT_IMPLEMENTED)
    self.write('Not implemented')
