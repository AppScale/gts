""" Keeps track of queue configuration details for push workers. """

import logging
import json
import os
from datetime import timedelta

from kazoo.exceptions import ZookeeperError
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.options import options

from appscale.common.async_retrying import (
  retry_children_watch_coroutine, retry_coroutine, retry_data_watch_coroutine
)
from appscale.common.constants import (CONFIG_DIR, LOG_DIR, MonitStates,
                                       VAR_DIR)
from appscale.common.monit_app_configuration import create_config_file
from appscale.common.monit_app_configuration import MONIT_CONFIG_DIR

from .utils import ensure_path

# The number of tasks the Celery worker can handle at a time.
CELERY_CONCURRENCY = 1000

# The directory where Celery configuration files are stored.
CELERY_CONFIG_DIR = os.path.join(CONFIG_DIR, 'celery', 'configuration')

# The safe memory in MB per Celery worker.
CELERY_SAFE_MEMORY = 1000

# The directory where Celery persists state.
CELERY_STATE_DIR = os.path.join('/', 'opt', 'appscale', 'celery')

# The directory where separate TaskQueue venv stores Celery
CELERY_TQ_DIR = os.path.join('/', 'opt', 'appscale_venvs',
                             'appscale_taskqueue', 'bin', 'celery')

# The working directory for Celery workers.
CELERY_WORKER_DIR = os.path.join(CONFIG_DIR, 'celery', 'workers')

# The directory that workers use for logging.
CELERY_WORKER_LOG_DIR = os.path.join(LOG_DIR, 'celery_workers')

# The time limit of a running task in seconds. Extra time over the soft limit
# allows it to catch up to interrupts.
HARD_TIME_LIMIT = 610

# The soft time limit of a running task.
TASK_SOFT_TIME_LIMIT = 600

# The worker script for Celery to use.
WORKER_MODULE = 'appscale.taskqueue.push_worker'

logger = logging.getLogger(__name__)


class ProjectPushWorkerManager(object):
  """ Manages the Celery worker for a single project. """
  def __init__(self, zk_client, monit_operator, project_id):
    """ Creates a new ProjectPushWorkerManager.

    Args:
      zk_client: A KazooClient.
      monit_operator: A MonitOperator.
      project_id: A string specifying a project ID.
    """
    self.zk_client = zk_client
    self.project_id = project_id
    self.monit_operator = monit_operator
    self.queues_node = '/appscale/projects/{}/queues'.format(project_id)
    self.watch = zk_client.DataWatch(self.queues_node, self._update_worker)
    self.monit_watch = 'celery-{}'.format(project_id)
    self._stopped = False

  @gen.coroutine
  def update_worker(self, queue_config):
    """ Updates a worker's configuration and restarts it.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    self._write_worker_configuration(queue_config)
    status = yield self._wait_for_stable_state()

    pid_location = os.path.join(VAR_DIR, 'celery-{}.pid'.format(self.project_id))
    try:
      with open(pid_location) as pidfile:
        old_pid = int(pidfile.read().strip())
    except IOError:
      old_pid = None

    # Start the worker if it doesn't exist. Restart it if it does.
    if status == MonitStates.MISSING:
      command = self.celery_command()
      env_vars = {'APP_ID': self.project_id, 'HOST': options.load_balancers[0],
                  'C_FORCE_ROOT': True}
      create_config_file(self.monit_watch, command, pid_location,
                         env_vars=env_vars, max_memory=CELERY_SAFE_MEMORY)
      logger.info('Starting push worker for {}'.format(self.project_id))
      yield self.monit_operator.reload()
    else:
      logger.info('Restarting push worker for {}'.format(self.project_id))
      yield self.monit_operator.send_command(self.monit_watch, 'restart')

    start_future = self.monit_operator.ensure_running(self.monit_watch)
    yield gen.with_timeout(timedelta(seconds=60), start_future,
                           IOLoop.current())

    try:
      yield self.ensure_pid_changed(old_pid, pid_location)
    except AssertionError:
      # Occasionally, Monit will get interrupted during a restart. Retry the
      # restart if the Celery worker PID is the same.
      logger.warning(
        '{} worker PID did not change. Restarting it.'.format(self.project_id))
      yield self.update_worker(queue_config)

  @staticmethod
  @retry_coroutine(retrying_timeout=10, retry_on_exception=[AssertionError])
  def ensure_pid_changed(old_pid, pid_location):
    try:
      with open(pid_location) as pidfile:
        new_pid = int(pidfile.read().strip())
    except IOError:
      new_pid = None

    if new_pid == old_pid:
      raise AssertionError

  @gen.coroutine
  def stop_worker(self):
    """ Removes the monit configuration for the project's push worker. """
    status = yield self._wait_for_stable_state()
    if status == MonitStates.RUNNING:
      logger.info('Stopping push worker for {}.'.format(self.project_id))
      yield self.monit_operator.send_command(self.monit_watch, 'stop')
      watch_file = '{}/appscale-{}.cfg'.format(MONIT_CONFIG_DIR, self.monit_watch)
      os.remove(watch_file)
    else:
      logger.debug('Not stopping push worker for {} since it is not running.'.format(self.project_id))

  def celery_command(self):
    """ Generates the Celery command for a project's push worker. """
    log_file = os.path.join(CELERY_WORKER_LOG_DIR,
                            '{}.log'.format(self.project_id))
    pidfile = os.path.join(VAR_DIR, 'celery-{}.pid'.format(self.project_id))
    state_db = os.path.join(CELERY_STATE_DIR,
                            'worker___{}.db'.format(self.project_id))

    return ' '.join([
      CELERY_TQ_DIR, 'worker',
      '--app', WORKER_MODULE,
      '--pool=eventlet',
      '--concurrency={}'.format(CELERY_CONCURRENCY),
      '--hostname', self.project_id,
      '--workdir', CELERY_WORKER_DIR,
      '--logfile', log_file,
      '--pidfile', pidfile,
      '--time-limit', str(HARD_TIME_LIMIT),
      '--soft-time-limit', str(TASK_SOFT_TIME_LIMIT),
      '--statedb', state_db,
      '-Ofair'
    ])

  def ensure_watch(self):
    """ Restart the watch if it has been cancelled. """
    if self._stopped:
      self._stopped = False
      self.watch = self.zk_client.DataWatch(self.queues_node,
                                            self._update_worker)

  @gen.coroutine
  def _wait_for_stable_state(self):
    """ Waits until the worker's state is not pending. """
    stable_states = (MonitStates.MISSING, MonitStates.RUNNING,
                     MonitStates.UNMONITORED)
    status_future = self.monit_operator.wait_for_status(
      self.monit_watch, stable_states)
    status = yield gen.with_timeout(timedelta(seconds=60), status_future,
                                    IOLoop.current())
    raise gen.Return(status)

  def _write_worker_configuration(self, queue_config):
    """ Writes a worker's configuration file.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
    if queue_config is None:
      rates = {'default': '5/s'}
    else:
      queues = json.loads(queue_config)['queue']
      rates = {
        queue_name: queue['rate'] for queue_name, queue in queues.items()
        if 'mode' not in queue or queue['mode'] == 'push'}

    config_location = os.path.join(CELERY_CONFIG_DIR,
                                   '{}.json'.format(self.project_id))
    with open(config_location, 'w') as config_file:
      json.dump(rates, config_file)

  def _update_worker(self, queue_config, _):
    """ Handles updates to a queue configuration node.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      queue_config: A JSON string specifying queue configuration.
    """
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

    persistent_update_worker = retry_data_watch_coroutine(
      self.queues_node, self.update_worker
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_worker, queue_config)


class GlobalPushWorkerManager(object):
  """ Manages the Celery workers for all projects. """
  def __init__(self, zk_client, monit_operator):
    """ Creates a new GlobalPushWorkerManager. """
    self.zk_client = zk_client
    self.monit_operator = monit_operator
    self.projects = {}
    ensure_path(CELERY_CONFIG_DIR)
    ensure_path(CELERY_WORKER_DIR)
    ensure_path(CELERY_WORKER_LOG_DIR)
    ensure_path(CELERY_STATE_DIR)
    zk_client.ensure_path('/appscale/projects')
    zk_client.ChildrenWatch('/appscale/projects', self._update_projects)

  @gen.coroutine
  def update_projects(self, new_project_list):
    """ Establishes watches for each project's queue configuration.

    Args:
      new_project_list: A fresh list of strings specifying existing
        project IDs.
    """
    to_stop = [project for project in self.projects
               if project not in new_project_list]
    for project_id in to_stop:
      yield self.projects[project_id].stop_worker()
      del self.projects[project_id]

    for new_project_id in new_project_list:
      if new_project_id not in self.projects:
        self.projects[new_project_id] = ProjectPushWorkerManager(
          self.zk_client, self.monit_operator, new_project_id)

      # Handle changes that happen between watches.
      self.projects[new_project_id].ensure_watch()

  def _update_projects(self, new_projects):
    """ Handles creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects: A list of strings specifying all existing project IDs.
    """
    persistent_update_project = retry_children_watch_coroutine(
      '/appscale/projects', self.update_projects
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_project, new_projects)
