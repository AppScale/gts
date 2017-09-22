""" A daemon that cleans up expired transactions. """
import argparse
import datetime
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

from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from ..cassandra_env.cassandra_interface import DatastoreProxy
from ..cassandra_env.large_batch import BatchResolver
from ..dbconstants import MAX_TX_DURATION
from ..zkappscale.tornado_kazoo import TornadoKazoo
from ..zkappscale.zktransaction import APP_TX_PREFIX

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore.entity_pb import CompositeIndex

logger = logging.getLogger('appscale-transaction-groomer')


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
               thread_pool):
    """ Creates a new ProjectGroomer.

    Args:
      project_id: A string specifying a project ID.
      coordinator: A GroomingCoordinator.
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
      thread_pool: A ThreadPoolExecutor.
    """
    self.project_id = project_id

    self._coordinator = coordinator
    self._zk_client = zk_client
    self._tornado_zk = TornadoKazoo(self._zk_client)
    self._db_access = db_access
    self._thread_pool = thread_pool
    self._txids_path = '/appscale/apps/{}/txids'.format(self.project_id)
    self._batch_resolver = BatchResolver(self.project_id, self._db_access)

    self._stop_event = AsyncEvent()
    self._stopped_event = AsyncEvent()

    self._zk_client.ensure_path(self._txids_path)
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
  def _groom_project(self):
    """ Runs the grooming process. """
    index = self._coordinator.index
    worker_count = self._coordinator.total_workers

    oldest_valid_tx = yield self._fetch_and_clean(index, worker_count)

    # Wait until there's a reasonable chance that some transactions have
    # timed out.
    next_timeout_eta = oldest_valid_tx + MAX_TX_DURATION

    # The oldest ignored transaction should still be valid, but ensure that
    # the timeout is not negative.
    next_timeout = max(0, next_timeout_eta - time.time())
    time_to_wait = datetime.timedelta(
      seconds=next_timeout + (MAX_TX_DURATION / 2))

    # Allow the wait to be cut short when a project is removed.
    try:
      yield self._stop_event.wait(timeout=time_to_wait)
    except gen.TimeoutError:
      raise gen.Return()

  @gen.coroutine
  def _resolve_txid(self, tx_node, composite_indexes):
    """ Cleans up a transaction if it has expired.

    Args:
      tx_node: A string specifying the name of the ZooKeeper node.
      composite_indexes: A list of CompositeIndex objects.
    Returns:
      The transaction start time if still valid, None if invalid.
    """
    full_path = '/'.join([self._txids_path, tx_node])
    tx_data = yield self._tornado_zk.get(full_path)
    tx_time = float(tx_data[0])
    txid = int(tx_node.lstrip(APP_TX_PREFIX))

    # If the transaction is still valid, return the time it was created.
    if tx_time + MAX_TX_DURATION >= time.time():
      raise gen.Return(tx_time)

    yield self._batch_resolver.resolve(txid, composite_indexes)

    try:
      yield self._tornado_zk.delete(full_path)
    except NoNodeError:
      pass
    except NotEmptyError:
      yield self._thread_pool.submit(self._zk_client.delete, full_path,
                                     recursive=True)

    yield self._batch_resolver.cleanup(txid)

  @gen.coroutine
  def _fetch_and_clean(self, worker_index, worker_count):
    """ Cleans up expired transactions.

    Args:
      worker_index: An integer specifying this worker's index.
      worker_count: An integer specifying the number of total workers.
    """
    oldest_valid_tx = time.time()
    future = self._tornado_zk.get_children(self._txids_path)
    children = yield future
    logger.debug(
      'Found {} transaction IDs for {}'.format(len(children), self.project_id))

    if not children:
      raise gen.Return(oldest_valid_tx)

    # Refresh these each time so that the indexes are fresh.
    encoded_indexes = yield self._thread_pool.submit(
      self._db_access.get_indices, self.project_id)
    composite_indexes = [CompositeIndex(index) for index in encoded_indexes]

    futures = []
    for tx_node in children:
      txid = int(tx_node.lstrip(APP_TX_PREFIX))
      # Only resolve transactions that this worker has been assigned.
      if txid % worker_count != worker_index:
        continue

      futures.append(self._resolve_txid(tx_node, composite_indexes))

    txids_cleaned = 0
    for future in futures:
      try:
        tx_time = yield future
      except Exception:
        # If the resolution process failed, try again the next time around.
        logger.exception('Error while resolving transaction')
        continue

      # 'None' indicates that the transaction was expired and cleaned up.
      if tx_time is None:
        txids_cleaned += 1

      if tx_time is not None and tx_time < oldest_valid_tx:
        oldest_valid_tx = tx_time

    if txids_cleaned > 0:
      logger.info('Cleaned up {} expired txids for {}'.format(txids_cleaned,
                                                              self.project_id))
    raise gen.Return(oldest_valid_tx)


class TransactionGroomer(object):
  """ Cleans up expired transactions. """
  def __init__(self, zk_client, db_access, thread_pool):
    """ Creates a new TransactionGroomer.

    Args:
      zk_client: A KazooClient.
      db_access: A DatastoreProxy.
      thread_pool: A ThreadPoolExecutor.
    """
    self.projects = {}

    self._zk_client = zk_client
    self._db_access = db_access
    self._thread_pool = thread_pool

    self._coordinator = GroomingCoordinator(self._zk_client)
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
          self._thread_pool)

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
    logger.setLevel(logging.DEBUG)

  zk_hosts = appscale_info.get_zk_node_ips()
  zk_client = KazooClient(hosts=','.join(zk_hosts),
                          connection_retry=ZK_PERSISTENT_RECONNECTS,
                          command_retry=KazooRetry(max_tries=-1))
  zk_client.start()

  db_access = DatastoreProxy()

  thread_pool = ThreadPoolExecutor(4)

  TransactionGroomer(zk_client, db_access, thread_pool)
  logger.info('Starting transaction groomer')

  IOLoop.current().start()
