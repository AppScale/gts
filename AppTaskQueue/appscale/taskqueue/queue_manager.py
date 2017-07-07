""" Keeps track of queue configuration details for producer connections. """

import json

from tornado.ioloop import IOLoop

from appscale.taskqueue.utils import create_celery_for_app
from .queue import PullQueue
from .queue import PushQueue
from .utils import logger


class ProjectQueueManager(dict):
  """ Keeps track of queue configuration details for a single project. """
  def __init__(self, zk_client, db_access, project_id):
    """ Creates a new ProjectQueueManager.

    Args:
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
      project_id: A string specifying a project ID.
    """
    super(ProjectQueueManager, self).__init__()
    self.project_id = project_id
    self.db_access = db_access
    queues_node = '/appscale/projects/{}/queues'.format(project_id)
    self.watch = zk_client.DataWatch(queues_node, self._update_queues_watch)
    self.celery = None
    self.rates = None

  def update_queues(self, queue_config):
    """ Caches new configuration details and cleans up old state.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    logger.info('Updating queues for {}'.format(self.project_id))
    if not queue_config:
      new_queues = {'default': {'rate': '5/s'}}
    else:
      new_queues = json.loads(queue_config)['queue']

    # Clean up obsolete queues.
    to_stop = [queue for queue in self if queue not in new_queues]
    for queue_name in to_stop:
      del self[queue_name]

    # Add new queues.
    for queue_name in new_queues:
      if queue_name in self:
        continue

      queue_info = new_queues[queue_name]
      queue_info['name'] = queue_name
      if 'mode' not in queue_info or queue_info['mode'] == 'push':
        self[queue_name] = PushQueue(queue_info, self.project_id)
      else:
        self[queue_name] = PullQueue(queue_info, self.project_id,
                                     self.db_access)

    # Establish a new Celery connection based on the new queues, and close the
    # old one.
    push_queues = [queue for queue in self.values()
                   if isinstance(queue, PushQueue)]
    old_rates = self.rates
    self.rates = {queue.name: queue.rate for queue in push_queues}
    if self.rates != old_rates:
      old_celery = self.celery
      self.celery = create_celery_for_app(self.project_id, self.rates)
      if old_celery is not None:
        old_celery.close()

    for queue in push_queues:
      queue.celery = self.celery

  def stop(self):
    """ Removes all cached queue configuration and closes connection. """
    self.watch._stopped = True
    if self.celery is not None:
      self.celery.close()

  def _update_queues_watch(self, queue_config, _):
    """ Handles updates to a queue configuration node.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_queues, queue_config)


class GlobalQueueManager(dict):
  """ Keeps track of queue configuration details for all projects. """
  def __init__(self, zk_client, db_access):
    """ Creates a new GlobalQueueManager.

    Args:
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
    """
    super(GlobalQueueManager, self).__init__()
    self.zk_client = zk_client
    self.db_access = db_access
    zk_client.ensure_path('/appscale/projects')
    zk_client.ChildrenWatch('/appscale/projects', self._update_projects_watch)

  def update_projects(self, new_projects):
    """ Establishes watches for all existing projects.

    Args:
      new_projects: A list of strings specifying project IDs.
    """
    to_stop = [project for project in self if project not in new_projects]
    for project_id in to_stop:
      self[project_id].stop()
      del self[project_id]

    for project_id in new_projects:
      if project_id not in self:
        self[project_id] = ProjectQueueManager(self.zk_client, self.db_access,
                                               project_id)

  def _update_projects_watch(self, new_projects):
    """ Handles creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects: A list of strings specifying all existing project IDs.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_projects, new_projects)
