""" Keeps track of queue configuration details for producer connections. """

import json
import uuid
from datetime import timedelta

from kazoo.exceptions import ZookeeperError
from tornado.ioloop import IOLoop, PeriodicCallback

from .queue import (
  PushQueue, PostgresPullQueue, ensure_queue_registered,
  ensure_queues_table_created, ensure_project_schema_created,
  ensure_tasks_table_created
)
from .utils import logger, create_celery_for_app


class ProjectQueueManager(dict):
  """ Keeps track of queue configuration details for a single project. """

  FLUSH_DELETED_INTERVAL = 1 * 60 * 60  # 1h

  def __init__(self, zk_client, project_id):
    """ Creates a new ProjectQueueManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
    """
    super(ProjectQueueManager, self).__init__()
    self.zk_client = zk_client
    self.project_id = project_id
    self._configure_periodical_flush()

    self.queues_node = '/appscale/projects/{}/queues'.format(project_id)
    self.pullqueues_initialization_lock = zk_client.Lock(
      self.queues_node + '/pullqueues_initialization_lock'
    )
    self.pullqueues_initialized_version_node = (
      self.queues_node + '/pullqueues_initialized_version'
    )
    self.pullqueues_cleanup_lease_node = (
      self.queues_node + '/pullqueues_cleanup_lease'
    )
    self.watch = zk_client.DataWatch(self.queues_node,
                                     self._update_queues_watch)
    self.celery = None
    self.rates = None
    self._stopped = False
    self._holder_id = str(uuid.uuid4())

  def update_queues(self, queue_config, znode_stats):
    """ Caches new configuration details and cleans up old state.

    Args:
      queue_config: A JSON string specifying queue configuration.
      znode_stats: An instance of ZnodeStats.
    """
    logger.info('Updating queues for {}'.format(self.project_id))
    if not queue_config:
      new_queue_config = {'default': {'rate': '5/s'}}
      config_last_modified = 0
    else:
      new_queue_config = json.loads(queue_config.decode('utf-8'))['queue']
      config_last_modified = znode_stats.last_modified

    # Clean up obsolete queues.
    to_stop = [queue for queue in self if queue not in new_queue_config]
    for queue_name in to_stop:
      del self[queue_name]

    self._update_push_queues(
      ((queue_name, queue) for queue_name, queue in new_queue_config.items()
       if queue.get('mode', 'push') == 'push')
    )

    self._update_pull_queues(
      ((queue_name, queue) for queue_name, queue in new_queue_config.items()
       if queue.get('mode', 'push') != 'push'),
      config_last_modified
    )

  def _update_push_queues(self, new_push_queue_configs):
    """ Caches new push queue configuration details.

    Args:
      new_push_queue_configs: A sequence of (queue_name, queue_info) tuples.
    """
    for queue_name, queue in new_push_queue_configs:
      queue['name'] = queue_name
      self[queue_name] = PushQueue(queue, self.project_id)

    # Establish a new Celery connection based on the new queues,
    # and close the old one.
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

  def _update_pull_queues(self, new_pull_queue_configs, config_last_modified):
    """ Caches new pull queue configuration details.

    Args:
      new_pull_queue_configs: A sequence of (queue_name, queue_info) tuples.
      config_last_modified: A number representing configs version.
    """
    new_version = config_last_modified
    if self._get_pullqueue_initialized_version() < new_version:
      # Only one TaskQueue server proceeds with Postgres tables initialization.
      with self.pullqueues_initialization_lock:
        # Double check after acquiring lock.
        if self._get_pullqueue_initialized_version() < new_version:
          # Ensure project schema and queues registry table are created.
          ensure_project_schema_created(self.project_id)
          ensure_queues_table_created(self.project_id)
          # Ensure all queues are registered and tasks tables are created.
          for queue_name, queue in new_pull_queue_configs:
            queue['name'] = queue_name
            queue_id = ensure_queue_registered(self.project_id, queue_name)
            ensure_tasks_table_created(self.project_id, queue_id)
            # Instantiate PostgresPullQueue with registration queue ID.
            self[queue_name] = PostgresPullQueue(queue, self.project_id, queue_id)

          # Report new initialized version of Postgres tables.
          self._set_pullqueue_initialized_version(new_version)
          return

    # Postgres tables are already created, just instantiate PostgresPullQueue.
    for queue_name, queue in new_pull_queue_configs:
      queue['name'] = queue_name
      queue_id = ensure_queue_registered(self.project_id, queue_name)
      self[queue_name] = PostgresPullQueue(queue, self.project_id, queue_id)

  def _get_pullqueue_initialized_version(self):
    """ Retrieves zookeeper node holding version of PullQueues configs
    which is currently provisioned in Postgres.
    """
    initialized_version = b'-1'
    version_node = self.pullqueues_initialized_version_node
    if self.zk_client.exists(version_node):
      initialized_version = self.zk_client.get(version_node)[0]
    return float(initialized_version)

  def _set_pullqueue_initialized_version(self, version):
    """ Sets zookeeper node holding version of PullQueues configs
    which is currently provisioned in Postgres.

    Args:
      version: A number representing last modification time
               of queue configs node in zookeeper.
    """
    version_node = self.pullqueues_initialized_version_node
    if self.zk_client.exists(version_node):
      self.zk_client.set(version_node, str(version).encode())
    else:
      self.zk_client.create(version_node, str(version).encode())

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

  def _update_queues_watch(self, queue_config, znode_stats):
    """ Handles updates to a queue configuration node.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      queue_config: A JSON string specifying queue configuration.
      znode_stats: An instance of ZnodeStats.
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

    main_io_loop.add_callback(self.update_queues, queue_config, znode_stats)

  def _configure_periodical_flush(self):
    """ Creates and starts periodical callback to clear old deleted tasks.
    """
    def flush_deleted():
      """ Attempts to lease a right to cleanup old deleted tasks.
      If it could lease the right it removes old deleted tasks for project
      pull queues.
      """
      # Avoid too frequent cleanup by using zookeeper lease recipe.
      duration = timedelta(seconds=self.FLUSH_DELETED_INTERVAL * 0.8)
      holder_id = self._holder_id
      lease = self.zk_client.NonBlockingLease(
        self.pullqueues_cleanup_lease_node, duration, holder_id
      )
      if lease:
        postgres_pull_queues = (q for q in self.values()
                                if isinstance(q, PostgresPullQueue))
        for queue in postgres_pull_queues:
          queue.flush_deleted()

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
