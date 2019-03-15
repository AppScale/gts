""" A daemon that cleans up expired transactions. """
import argparse
import datetime
import json
import logging
import sys
import time
import uuid

from concurrent.futures import ThreadPoolExecutor
from kazoo.client import KazooClient
from kazoo.client import KazooState
from kazoo.exceptions import NoNodeError
from kazoo.exceptions import NotEmptyError
from kazoo.exceptions import ZookeeperError
from kazoo.retry import KazooRetry
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.locks import Event as AsyncEvent
from tornado.queues import Queue as AsyncQueue

from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from ..cassandra_env.cassandra_interface import DatastoreProxy
from ..cassandra_env.large_batch import BatchResolver
from ..dbconstants import MAX_TX_DURATION
from ..index_manager import IndexManager
from ..zkappscale.constants import CONTAINER_PREFIX
from ..zkappscale.constants import COUNTER_NODE_PREFIX
from ..zkappscale.constants import MAX_SEQUENCE_COUNTER
from ..zkappscale.constants import OFFSET_NODE
from ..zkappscale.tornado_kazoo import TornadoKazoo

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore.entity_pb import CompositeIndex

# The maximum number of transactions per project to clean up at the same time.
MAX_CONCURRENCY = 10

logger = logging.getLogger(__name__)


class GroomingCoordinator(object):
  """ Distributes grooming work between registered groomers. """
  def __init__(self, zk_client):
    self.index = 0
    self.total_workers = 1

    self._groomer_id = uuid.uuid4().hex
    self._zk_client = zk_client
    self._node = None
    self._registration_path = '/appscale/datastore/tx_groomer'

    self._zk_client.ensure_path(self._registration_path)

    # Make sure the ephemeral registration node is recreated upon reconnect.
    self._zk_client.add_listener(self._state_listener)
    self._register_groomer()

    # Make sure the assignment is updated whenever a new groomer registers.
    self._zk_client.ChildrenWatch(self._registration_path,
                                  self._update_assignment_watch)

  def _update_assignment(self, workers):
    """ Updates the portion of transactions this groomer needs to clean up.

    Args:
      workers: A list of strings specifying registered groomers.
    """
    workers.sort(key=lambda name: name.rsplit('-')[1])

    self.total_workers = len(workers)
    try:
      self.index = workers.index(self._node)
    except ValueError:
      self._register_groomer()
      workers = self._zk_client.retry(self._zk_client.get_children,
                                      self._registration_path)
      return self._update_assignment(workers)

    logger.info('Currently acting as worker {}/{}'.format(self.index + 1,
                                                          self.total_workers))

  def _update_assignment_watch(self, children):
    """ Watches for new or lost groomers.

    Args:
      children: A list of strings specifying registered groomers.
    """
    IOLoop.instance().add_callback(self._update_assignment, children)

  def _clean_created_nodes(self):
    """ Removes any registrations this service may have created. """
    all_nodes = self._zk_client.retry(self._zk_client.get_children,
                                      self._registration_path)
    to_delete = [node for node in all_nodes
                 if node.startswith(self._groomer_id)]
    for node in to_delete:
      full_path = '/'.join([self._registration_path, node])
      while True:
        try:
          self._zk_client.delete(full_path)
          break
        except NoNodeError:
          break
        except ZookeeperError:
          continue

  def _register_groomer(self):
    """ Creates a ZooKeeper entry that broadcasts this service's presence. """
    logger.info('Registering service with ZooKeeper')
    node_prefix = '/'.join([self._registration_path, self._groomer_id]) + '-'

    # Make sure an older node from this groomer did not remain.
    self._clean_created_nodes()

    # The groomer must be registered before it can continue working.
    while True:
      try:
        full_path = self._zk_client.create(node_prefix, ephemeral=True,
                                           sequence=True)
        self._node = full_path[len(self._registration_path) + 1:]
        break
      except ZookeeperError:
        self._clean_created_nodes()
        continue

  def _state_listener(self, state):
    """ Watches for changes to the ZooKeeper connection state. """
    if state == KazooState.CONNECTED:
      IOLoop.instance().add_callback(self._register_groomer)


class ProjectGroomer(object):
  """ Cleans up expired transactions for a project. """
  def __init__(self, project_id, coordinator, zk_client, db_access,
               thread_pool, index_manager):
    """ Creates a new ProjectGroomer.

    Args:
      project_id: A string specifying a project ID.
      coordinator: A GroomingCoordinator.
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
      thread_pool: A ThreadPoolExecutor.
      index_manager: An IndexManager object.
    """
    self.project_id = project_id

    self._coordinator = coordinator
    self._zk_client = zk_client
    self._tornado_zk = TornadoKazoo(self._zk_client)
    self._db_access = db_access
    self._thread_pool = thread_pool
    self._index_manager = index_manager
    self._project_node = '/appscale/apps/{}'.format(self.project_id)
    self._containers = []
    self._inactive_containers = set()
    self._batch_resolver = BatchResolver(self.project_id, self._db_access)

    self._zk_client.ensure_path(self._project_node)
    self._zk_client.ChildrenWatch(self._project_node, self._update_containers)

    self._txid_manual_offset = 0
    self._offset_node = '/'.join([self._project_node, OFFSET_NODE])
    self._zk_client.DataWatch(self._offset_node, self._update_offset)

    self._stop_event = AsyncEvent()
    self._stopped_event = AsyncEvent()

    # Keeps track of cleanup results for each round of grooming.
    self._txids_cleaned = 0
    self._oldest_valid_tx_time = None

    self._worker_queue = AsyncQueue(maxsize=MAX_CONCURRENCY)
    for _ in range(MAX_CONCURRENCY):
      IOLoop.current().spawn_callback(self._worker)

    IOLoop.current().spawn_callback(self.start)

  @gen.coroutine
  def start(self):
    """ Starts the grooming process until the stop event is set. """
    logger.info('Grooming {}'.format(self.project_id))
    while True:
      if self._stop_event.is_set():
        break

      try:
        yield self._groom_project()
      except Exception:
        # Prevent the grooming loop from stopping if an error is encountered.
        logger.exception(
          'Unexpected error while grooming {}'.format(self.project_id))
        yield gen.sleep(MAX_TX_DURATION)

    self._stopped_event.set()

  @gen.coroutine
  def stop(self):
    """ Stops the grooming process. """
    logger.info('Stopping grooming process for {}'.format(self.project_id))
    self._stop_event.set()
    yield self._stopped_event.wait()

  @gen.coroutine
  def _worker(self):
    """ Processes items in the worker queue. """
    while True:
      tx_path, composite_indexes = yield self._worker_queue.get()
      try:
        tx_time = yield self._resolve_txid(tx_path, composite_indexes)
        if tx_time is None:
          self._txids_cleaned += 1

        if tx_time is not None and tx_time < self._oldest_valid_tx_time:
          self._oldest_valid_tx_time = tx_time
      except Exception:
        logger.exception('Unexpected error while resolving {}'.format(tx_path))
      finally:
        self._worker_queue.task_done()

  def _update_offset(self, new_offset, _):
    """ Watches for updates to the manual offset node.

    Args:
      new_offset: A string specifying the new manual offset.
    """
    self._txid_manual_offset = int(new_offset or 0)

  def _update_containers(self, nodes):
    """ Updates the list of active txid containers.

    Args:
      nodes: A list of strings specifying ZooKeeper nodes.
    """
    counters = [int(node[len(CONTAINER_PREFIX):] or 1)
                for node in nodes if node.startswith(CONTAINER_PREFIX)
                and node not in self._inactive_containers]
    counters.sort()

    containers = [CONTAINER_PREFIX + str(counter) for counter in counters]
    if containers and containers[0] == '{}1'.format(CONTAINER_PREFIX):
      containers[0] = CONTAINER_PREFIX

    self._containers = containers

  @gen.coroutine
  def _groom_project(self):
    """ Runs the grooming process. """
    index = self._coordinator.index
    worker_count = self._coordinator.total_workers

    oldest_valid_tx_time = yield self._fetch_and_clean(index, worker_count)

    # Wait until there's a reasonable chance that some transactions have
    # timed out.
    next_timeout_eta = oldest_valid_tx_time + MAX_TX_DURATION

    # The oldest ignored transaction should still be valid, but ensure that
    # the timeout is not negative.
    next_timeout = max(0, next_timeout_eta - time.time())
    time_to_wait = datetime.timedelta(
      seconds=next_timeout + (MAX_TX_DURATION / 2))

    # Allow the wait to be cut short when a project is removed.
    try:
      yield self._stop_event.wait(timeout=time_to_wait)
    except gen.TimeoutError:
      return

  @gen.coroutine
  def _remove_locks(self, txid, tx_path):
    """ Removes entity locks involved with the transaction.

    Args:
      txid: An integer specifying the transaction ID.
      tx_path: A string specifying the location of the transaction node.
    """
    groups_path = '/'.join([tx_path, 'groups'])
    try:
      groups_data = yield self._tornado_zk.get(groups_path)
    except NoNodeError:
      # If the group list does not exist, the locks have not been acquired.
      return

    group_paths = json.loads(groups_data[0])
    for group_path in group_paths:
      try:
        contenders = yield self._tornado_zk.get_children(group_path)
      except NoNodeError:
        # The lock may have been cleaned up or not acquired in the first place.
        continue

      for contender in contenders:
        contender_path = '/'.join([group_path, contender])
        contender_data = yield self._tornado_zk.get(contender_path)
        contender_txid = int(contender_data[0])
        if contender_txid != txid:
          continue

        yield self._tornado_zk.delete(contender_path)
        break

  @gen.coroutine
  def _remove_path(self, tx_path):
    """ Removes a ZooKeeper node.

    Args:
      tx_path: A string specifying the path to delete.
    """
    try:
      yield self._tornado_zk.delete(tx_path)
    except NoNodeError:
      pass
    except NotEmptyError:
      yield self._thread_pool.submit(self._zk_client.delete, tx_path,
                                     recursive=True)

  @gen.coroutine
  def _resolve_txid(self, tx_path, composite_indexes):
    """ Cleans up a transaction if it has expired.

    Args:
      tx_path: A string specifying the location of the ZooKeeper node.
      composite_indexes: A list of CompositeIndex objects.
    Returns:
      The transaction start time if still valid, None if invalid because this
      method will also delete it.
    """
    try:
      tx_data = yield self._tornado_zk.get(tx_path)
    except NoNodeError:
      return

    tx_time = float(tx_data[0])

    _, container, tx_node = tx_path.rsplit('/', 2)
    tx_node_id = int(tx_node.lstrip(COUNTER_NODE_PREFIX))
    container_count = int(container[len(CONTAINER_PREFIX):] or 1)
    if tx_node_id < 0:
      yield self._remove_path(tx_path)
      return

    container_size = MAX_SEQUENCE_COUNTER + 1
    automatic_offset = (container_count - 1) * container_size
    txid = self._txid_manual_offset + automatic_offset + tx_node_id

    if txid < 1:
      yield self._remove_path(tx_path)
      return

    # If the transaction is still valid, return the time it was created.
    if tx_time + MAX_TX_DURATION >= time.time():
      raise gen.Return(tx_time)

    yield self._batch_resolver.resolve(txid, composite_indexes)
    yield self._remove_locks(txid, tx_path)
    yield self._remove_path(tx_path)
    yield self._batch_resolver.cleanup(txid)

  @gen.coroutine
  def _fetch_and_clean(self, worker_index, worker_count):
    """ Cleans up expired transactions.

    Args:
      worker_index: An integer specifying this worker's index.
      worker_count: An integer specifying the number of total workers.
    Returns:
      A float specifying the time of the oldest valid transaction as a unix
      timestamp.
    """
    self._txids_cleaned = 0
    self._oldest_valid_tx_time = time.time()

    children = []
    for index, container in enumerate(self._containers):
      container_path = '/'.join([self._project_node, container])
      new_children = yield self._tornado_zk.get_children(container_path)

      if not new_children and index < len(self._containers) - 1:
        self._inactive_containers.add(container)

      children.extend(['/'.join([container_path, node])
                       for node in new_children])

    logger.debug(
      'Found {} transaction IDs for {}'.format(len(children), self.project_id))

    if not children:
      raise gen.Return(self._oldest_valid_tx_time)

    # Refresh these each time so that the indexes are fresh.
    project_index_manager = self._index_manager.projects[self.project_id]
    composite_indexes = project_index_manager.indexes_pb

    for tx_path in children:
      tx_node_id = int(tx_path.split('/')[-1].lstrip(COUNTER_NODE_PREFIX))
      # Only resolve transactions that this worker has been assigned.
      if tx_node_id % worker_count != worker_index:
        continue

      yield self._worker_queue.put((tx_path, composite_indexes))

    yield self._worker_queue.join()

    if self._txids_cleaned > 0:
      logger.info('Cleaned up {} expired txids for {}'.format(
        self._txids_cleaned, self.project_id))

    raise gen.Return(self._oldest_valid_tx_time)


class TransactionGroomer(object):
  """ Cleans up expired transactions. """
  def __init__(self, zk_client, db_access, thread_pool, index_manager):
    """ Creates a new TransactionGroomer.

    Args:
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
      thread_pool: A ThreadPoolExecutor.
      index_manager: An IndexManager.
    """
    self.projects = {}

    self._zk_client = zk_client
    self._db_access = db_access
    self._thread_pool = thread_pool
    self._index_manager = index_manager

    self._coordinator = GroomingCoordinator(self._zk_client)

    self._zk_client.ensure_path('/appscale/projects')
    self.projects_watch = zk_client.ChildrenWatch(
      '/appscale/projects', self._update_projects)

  @gen.coroutine
  def _update_projects(self, new_projects):
    """ Handles project additions and deletions.

    Args:
      new_projects: A list of string specifying project IDs.
    """
    # The DatastoreProxy expects bare strings for project IDs.
    new_projects = [str(project) for project in new_projects]
    to_remove = [project for project in self.projects
                 if project not in new_projects]
    for old_project in to_remove:
      yield self.projects[old_project].stop()
      del self.projects[old_project]

    for new_project in new_projects:
      if new_project not in self.projects:
        self.projects[new_project] = ProjectGroomer(
          new_project, self._coordinator, self._zk_client, self._db_access,
          self._thread_pool, self._index_manager)

  def _update_projects_watch(self, new_projects):
    """ Handles project additions or deletions.

    Args:
      new_projects: A list of strings specifying project IDs.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self._update_projects, new_projects)


def main():
  """ Starts the groomer. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  zk_hosts = appscale_info.get_zk_node_ips()
  zk_client = KazooClient(hosts=','.join(zk_hosts),
                          connection_retry=ZK_PERSISTENT_RECONNECTS,
                          command_retry=KazooRetry(max_tries=-1))
  zk_client.start()

  db_access = DatastoreProxy()

  thread_pool = ThreadPoolExecutor(4)

  index_manager = IndexManager(zk_client, None)

  TransactionGroomer(zk_client, db_access, thread_pool, index_manager)
  logger.info('Starting transaction groomer')

  IOLoop.current().start()
