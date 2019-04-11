""" Implements the pull queue viewer interface. """
from __future__ import division

import datetime
import json
import logging
import urllib2

from app_dashboard import AppDashboard
from taskqueue_location import TASKQUEUE_LOCATION


class PQClient(object):
  """ A client that makes pull queue-related requests. """

  # A template for forming URLs for the REST API.
  REST_BASE = 'http://{}/taskqueue/v1beta2/projects/{}/taskqueues'

  def __init__(self, project_id):
    self._project_id = project_id
    self._base_url = self.REST_BASE.format(TASKQUEUE_LOCATION,
                                           self._project_id)

  def list_queues(self):
    """ Fetches a list of pull queues.

    Returns:
      A list of strings specifying queue names.
    """
    response = urllib2.urlopen(self._base_url)
    return json.loads(response.read())

  def list_tasks(self, queue_name):
    """ Fetches a list of tasks in a queue.

    Returns:
      A list of dictionaries representing task details.
    """
    response = urllib2.urlopen('/'.join([self._base_url, queue_name, 'tasks']))
    tasks = json.loads(response.read()).get('items', [])
    return [self._format_task(task) for task in tasks]

  @staticmethod
  def _format_task(result):
    """ Parses task details from a REST API result.

    Returns:
      A dictionary specifying task details.
    """
    def from_micros(timestamp):
      return datetime.datetime.fromtimestamp(float(timestamp) / 1000000)

    return {
      'name': result['id'],
      'eta': from_micros(result['leaseTimestamp']),
      'enqueue_time': from_micros(result['enqueueTimestamp']),
      'retry_count': result['retry_count']
    }


class PQViewerPage(AppDashboard):
  """ A base class for pull queue viewer pages. """
  def ensure_user_has_admin(self, project_id):
    """ Returns an error page if user does not have project permissions.

    Args:
      project_id: A string specifying a project ID.
    """
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0]
                             for version in version_keys})
    else:
      owned_projects = self.helper.get_owned_apps()

    if project_id not in owned_projects:
      self.response.write(
        'You do not have permission to view data for {}.'.format(project_id))
      self.abort(403)


class PQProjectSelector(AppDashboard):
  """ Handles requests for the project selection page. """
  TEMPLATE = 'taskqueue/project_selector.html'

  def get(self):
    """ Presents a list of projects to view queue info for. """
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0] for version in version_keys
                             if version.split('_')[0] != self.PROJECT_ID})
    else:
      owned_projects = self.helper.get_owned_apps()

    context = {
      'owned_projects': owned_projects,
      'page_content': self.TEMPLATE,
    }
    self.render_app_page(page='pq_project_selector', values=context)


class PQQueueSelector(PQViewerPage):
  """ Handles requests for the queue selection page. """
  TEMPLATE = 'taskqueue/queue_selector.html'

  def get(self, project_id):
    """ Presents a list of queues to view tasks for. """
    self.ensure_user_has_admin(project_id)

    client = PQClient(project_id)
    project_queues = client.list_queues()

    context = {
      'page_content': self.TEMPLATE,
      'project_id': project_id,
      'queue_names': project_queues
    }
    self.render_app_page(page='pq_queue_selector', values=context)


class PQTaskSelector(PQViewerPage):
  """ Handles requests for the task selection page. """
  TEMPLATE = 'taskqueue/task_selector.html'

  def get(self, project_id, queue_name):
    """ Presents a list of tasks in a queue. """
    self.ensure_user_has_admin(project_id)

    client = PQClient(project_id)
    tasks = client.list_tasks(queue_name)
    logging.info('tasks: {}'.format(tasks))

    context = {
      'page_content': self.TEMPLATE,
      'project_id': project_id,
      'queue_name': queue_name,
      'tasks': tasks
    }
    self.render_app_page(page='pq_queue_selector', values=context)
