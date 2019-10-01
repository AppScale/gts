""" Keeps track of queue configuration details for producer connections. """

import json

from kazoo.exceptions import ZookeeperError
from tornado.ioloop import IOLoop, PeriodicCallback

from appscale.taskqueue.pg_connection_wrapper import PostgresConnectionWrapper
from appscale.taskqueue.queue import PostgresPullQueue
from appscale.taskqueue.utils import create_celery_for_app
from .queue import PullQueue
from .queue import PushQueue
from .utils import logger


class ProjectQueueManager(dict):
  """ Keeps track of queue configuration details for a single project. """

  FLUSH_DELETED_INTERVAL = 3 * 60 * 60  # 3h
  MAX_POSTGRES_BACKED_PROJECTS = 20

  def __init__(self, zk_client, project_id):
    """ Creates a new ProjectQueueManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
    """
    super(ProjectQueueManager, self).__init__()
    self.zk_client = zk_client
    self.project_id = project_id

    project_dsn_node = '/appscale/projects/{}/postgres_dsn'.format(project_id)
    global_dsn_node = '/appscale/tasks/postgres_dsn'
    if self.zk_client.exists(project_dsn_node):
      pg_dsn = self.zk_client.get(project_dsn_node)
      logger.info('Using project-specific PostgreSQL as a backend for '
                  'Pull Queues of project "{}" '.format(project_id))
    elif self.zk_client.exists(global_dsn_node):
      pg_dsn = self.zk_client.get(global_dsn_node)
      logger.info('Using deployment-wide PostgreSQL as a backend for '
                  'Pull Queues"'.format(project_id))
    else:
      pg_dsn = None
      logger.info('Using Cassandra as a backend for Pull Queues of "{}"'
                  .format(project_id))

    if pg_dsn:
      # TODO: PostgresConnectionWrapper may need an update when
      #       TaskQueue becomes concurrent
      self.pg_connection_wrapper = PostgresConnectionWrapper(
        dsn=pg_dsn[0].decode('utf-8')
      )
      self._configure_periodical_flush()
    else:
      self.pg_connection_wrapper = None

    self.queues_node = '/appscale/projects/{}/queues'.format(project_id)
    self.watch = zk_client.DataWatch(self.queues_node,
                                     self._update_queues_watch)
    self.celery = None
    self.rates = None
    self._stopped = False

  def update_queues(self, queue_config):
    """ Caches new configuration details and cleans up old state.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    logger.info('Updating queues for {}'.format(self.project_id))
    if not queue_config:
      new_queue_config = {'default': {'rate': '5/s'}}
    else:
      new_queue_config = json.loads(queue_config.decode('utf-8'))['queue']

    # Clean up obsolete queues.
    to_stop = [queue for queue in self if queue not in new_queue_config]
    for queue_name in to_stop:
      del self[queue_name]

    # Add new queues.
    for queue_name in new_queue_config:
      if queue_name in self:
        continue

      queue_info = new_queue_config[queue_name]
      queue_info['name'] = queue_name
      if 'mode' not in queue_info or queue_info['mode'] == 'push':
        self[queue_name] = PushQueue(queue_info, self.project_id)
      elif self.pg_connection_wrapper:
        self[queue_name] = PostgresPullQueue(queue_info, self.project_id,
                                             self.pg_connection_wrapper)
      else:
        self[queue_name] = PullQueue(queue_info, self.project_id)

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

  def ensure_watch(self):
    """ Restart the watch if it has been cancelled. """
    if self._stopped:
      self._stopped = False
      self.watch = self.zk_client.DataWatch(self.queues_node,
                                            self._update_queues_watch)

  def stop(self):
    """ Close the Celery and Postgres connections if they still exist. """
    if self.celery is not None:
      self.celery.close()
    if self.pg_connection_wrapper is not None:
      self.pg_connection_wrapper.close()

  def _update_queues_watch(self, queue_config, _):
    """ Handles updates to a queue configuration node.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    main_io_loop = IOLoop.instance()

    # Prevent further watches if they are no longer needed.
    if queue_config is None:
      try:
        project_exists = self.zk_client.exists(
          '/appscale/projects/{}'.format(self.project_id)) is not None
      except ZookeeperError:
        # If the project has been deleted, an extra "exists" watch will remain.
        project_exists = True

      if not project_exists:
        self._stopped = True
        return False

    main_io_loop.add_callback(self.update_queues, queue_config)

  def _configure_periodical_flush(self):
    """ Creates and starts periodical callback to clear old deleted tasks.
    """
    def flush_deleted():
      """ Calls flush_deleted method for all PostgresPullQueues.
      """
      postgres_pull_queues = (q for q in self.values()
                              if isinstance(q, PostgresPullQueue))
      for q in postgres_pull_queues:
        q.flush_deleted()

    PeriodicCallback(flush_deleted, self.FLUSH_DELETED_INTERVAL * 1000).start()


class GlobalQueueManager(dict):
  """ Keeps track of queue configuration details for all projects. """
  def __init__(self, zk_client):
    """ Creates a new GlobalQueueManager.

    Args:
      zk_client: A KazooClient.
    """
    super(GlobalQueueManager, self).__init__()
    self.zk_client = zk_client
    zk_client.ensure_path('/appscale/projects')
    zk_client.ChildrenWatch('/appscale/projects', self._update_projects_watch)

  def update_projects(self, new_project_list):
    """ Establishes watches for all existing projects.

    Args:
      new_project_list: A fresh list of strings specifying existing
        project IDs.
    """
    to_stop = [project for project in self if project not in new_project_list]
    for project_id in to_stop:
      self[project_id].stop()
      del self[project_id]

    for project_id in new_project_list:
      if project_id not in self:
        self[project_id] = ProjectQueueManager(self.zk_client, project_id)

      # Handle changes that happen between watches.
      self[project_id].ensure_watch()

  def _update_projects_watch(self, new_projects):
    """ Handles creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects: A list of strings specifying all existing project IDs.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_projects, new_projects)
