import base64
import uuid

from kazoo.exceptions import (
  CancelledError,
  KazooException,
  LockTimeout,
  NoNodeError,
  NotEmptyError
)
from kazoo.retry import (
  ForceRetryError,
  KazooRetry,
  RetryFailedError
)
from tornado import gen, ioloop
from tornado.locks import Lock as TornadoLock

# The ZooKeeper node that contains lock entries for an entity group.
LOCK_PATH_TEMPLATE = u'/appscale/apps/{project}/locks/{namespace}/{group}'

# The number of seconds to wait for a lock before raising a timeout error.
LOCK_TIMEOUT = 10


def zk_group_path(key):
  """ Retrieve the ZooKeeper lock path for a given entity key.

  Args:
    key: An entity Reference object.
  Returns:
    A string containing the location of a ZooKeeper path.
  """
  project = key.app().decode('utf-8')
  if key.name_space():
    namespace = key.name_space().decode('utf-8')
  else:
    namespace = u':default'

  first_element = key.path().element(0)
  kind = first_element.type().decode('utf-8')

  # Differentiate between types of identifiers.
  if first_element.has_id():
    group = u'{}:{}'.format(kind, first_element.id())
  else:
    # Kazoo does not accept certain characters (eg. newlines) that Cloud
    # Datastore allows.
    encoded_id = base64.b64encode(first_element.name())
    group = u'{}::{}'.format(kind, encoded_id.decode('utf-8').rstrip('='))

  return LOCK_PATH_TEMPLATE.format(project=project, namespace=namespace,
                                   group=group)


class EntityLock(object):
  """ A ZooKeeper-based entity lock that allows test-and-set operations.

  This is based on kazoo's lock recipe, and has been modified to lock multiple
  entity groups. This lock is not re-entrant. Repeated calls after already
  acquired will block.
  """
  _NODE_NAME = '__lock__'

  # Tornado lock which allows tornado to switch to different coroutine
  # if current one is waiting for entity group lock
  _tornado_lock = TornadoLock()

  def __init__(self, client, keys, txid=None):
    """ Create an entity lock.

    Args:
      client: A kazoo client.
      keys: A list of entity Reference objects.
      txid: An integer specifying the transaction ID.
    """
    self.client = client
    self.paths = [zk_group_path(key) for key in keys]

    # The txid is written to the contender nodes for deadlock resolution.
    self.data = str(txid or '')

    self.wake_event = client.handler.event_object()

    # Give the contender nodes a uniquely identifiable prefix in case its
    # existence is in question.
    self.prefix = uuid.uuid4().hex + self._NODE_NAME

    self.create_paths = [path + '/' + self.prefix for path in self.paths]

    self.create_tried = False
    self.is_acquired = False
    self.cancelled = False
    self._retry = KazooRetry(max_tries=None,
                             sleep_func=client.handler.sleep_func)
    self._lock = client.handler.lock_object()

  def _ensure_path(self):
    """ Make sure the ZooKeeper lock paths have been created. """
    for path in self.paths:
      self.client.ensure_path(path)

  def cancel(self):
    """ Cancel a pending lock acquire. """
    self.cancelled = True
    self.wake_event.set()

  @gen.coroutine
  def acquire(self):
    now = ioloop.IOLoop.current().time()
    yield EntityLock._tornado_lock.acquire(now + LOCK_TIMEOUT)
    try:
      locked = self.unsafe_acquire()
      raise gen.Return(locked)
    finally:
      if not self.is_acquired:
        EntityLock._tornado_lock.release()

  def unsafe_acquire(self):
    """ Acquire the lock. By default blocks and waits forever.

    Returns:
      A boolean indicating whether or not the lock was acquired.
    """

    def _acquire_lock():
      """ Acquire a kazoo thread lock. """
      got_it = self._lock.acquire(False)
      if not got_it:
        raise ForceRetryError()
      return True

    retry = self._retry.copy()
    retry.deadline = LOCK_TIMEOUT

    # Prevent other threads from acquiring the lock at the same time.
    locked = self._lock.acquire(False)
    if not locked:
      try:
        retry(_acquire_lock)
      except RetryFailedError:
        return False

    already_acquired = self.is_acquired
    try:
      gotten = False
      try:
        gotten = retry(self._inner_acquire)
      except RetryFailedError:
        if not already_acquired:
          self._best_effort_cleanup()
      except KazooException:
        if not already_acquired:
          self._best_effort_cleanup()
          self.cancelled = False
        raise
      if gotten:
        self.is_acquired = gotten
      if not gotten and not already_acquired:
        self._delete_nodes(self.nodes)
      return gotten
    finally:
      self._lock.release()

  def _watch_session(self, state):
    """ A callback function for handling connection state changes.

    Args:
      state: The new connection state.
    """
    self.wake_event.set()
    return True

  def _resolve_deadlocks(self, children_list):
    """ Check if there are any concurrent cross-group locks.

    Args:
      children_list: A list of current transactions for each group.
    """
    current_txid = int(self.data)
    for index, children in enumerate(children_list):
      our_index = children.index(self.nodes[index])

      # Skip groups where this lock already has the earliest contender.
      if our_index == 0:
        continue

      # Get transaction IDs for earlier contenders.
      for child in children[:our_index - 1]:
        try:
          data, _ = self.client.get(
            self.paths[index] + '/' + child)
        except NoNodeError:
          continue

        # If data is not set, it doesn't belong to a cross-group
        # transaction.
        if not data:
          continue

        child_txid = int(data)
        # As an arbitrary rule, require later transactions to
        # resolve deadlocks.
        if current_txid > child_txid:
          # TODO: Implement a more graceful deadlock detection.
          self.client.retry(self._delete_nodes, self.nodes)
          raise ForceRetryError()

  def _inner_acquire(self):
    """ Create contender node(s) and wait until the lock is acquired. """

    # Make sure the group lock node exists.
    self._ensure_path()

    nodes = [None for _ in self.paths]
    if self.create_tried:
      nodes = self._find_nodes()
    else:
      self.create_tried = True

    for index, node in enumerate(nodes):
      if node is not None:
        continue

      # The entity group lock root may have been deleted, so try a few times.
      try_num = 0
      while True:
        try:
          node = self.client.create(
            self.create_paths[index], self.data, sequence=True)
          break
        except NoNodeError:
          self.client.ensure_path(self.paths[index])
          if try_num > 3:
            raise ForceRetryError()
        try_num += 1

      # Strip off path to node.
      node = node[len(self.paths[index]) + 1:]
      nodes[index] = node

    self.nodes = nodes

    while True:
      self.wake_event.clear()

      # Bail out with an exception if cancellation has been requested.
      if self.cancelled:
        raise CancelledError()

      children_list = self._get_sorted_children()

      predecessors = []
      for index, children in enumerate(children_list):
        try:
          our_index = children.index(nodes[index])
        except ValueError:
          raise ForceRetryError()

        # If the lock for this group hasn't been acquired, get the predecessor.
        if our_index != 0:
          predecessors.append(
            self.paths[index] + "/" + children[our_index - 1])

      if not predecessors:
        return True

      if len(nodes) > 1:
        self._resolve_deadlocks(children_list)

      # Wait for predecessor to be removed.
      # TODO: Listen for all at the same time.
      for index, predecessor in enumerate(predecessors):
        self.client.add_listener(self._watch_session)
        try:
          if self.client.exists(predecessor, self._watch_predecessor):
            self.wake_event.wait(LOCK_TIMEOUT)
            if not self.wake_event.isSet():
              error = 'Failed to acquire lock on {} after {} '\
                'seconds'.format(self.paths, LOCK_TIMEOUT * (index + 1))
              raise LockTimeout(error)
        finally:
          self.client.remove_listener(self._watch_session)

  def _watch_predecessor(self, event):
    """ A callback function for handling contender deletions.

    Args:
      event: A ZooKeeper event.
    """
    self.wake_event.set()

  def _get_sorted_children(self):
    """ Retrieve a list of sorted contenders for each group.

    Returns:
      A list of contenders for each group.
    """
    children = []
    for path in self.paths:
      try:
        children.append(self.client.get_children(path))
      except NoNodeError:
        children.append([])

    # Ignore lock path prefix when sorting contenders.
    lockname = self._NODE_NAME
    for child_list in children:
      child_list.sort(key=lambda c: c[c.find(lockname) + len(lockname):])
    return children

  def _find_nodes(self):
    """ Retrieve a list of paths this lock has created.

    Returns:
      A list of ZooKeeper paths.
    """
    nodes = []
    for path in self.paths:
      try:
        children = self.client.get_children(path)
      except NoNodeError:
        children = []

      node = None
      for child in children:
        if child.startswith(self.prefix):
          node = child
      nodes.append(node)
    return nodes

  def _delete_nodes(self, nodes):
    """ Remove ZooKeeper nodes.

    Args:
      nodes: A list of nodes to delete.
    """
    for index, node in enumerate(nodes):
      if node is None:
        continue
      self.client.delete(self.paths[index] + "/" + node)

  def _best_effort_cleanup(self):
    """ Attempt to delete nodes that this lock has created. """
    try:
      nodes = self._find_nodes()
      self._delete_nodes(nodes)
    except KazooException:
      pass

  def release(self):
    """ Release the lock immediately. """
    try:
      self.client.retry(self._inner_release)

      # Try to clean up the group lock path.
      for path in self.paths:
        try:
          self.client.delete(path)
        except (NotEmptyError, NoNodeError):
          pass
      return
    finally:
      if not self.is_acquired:
        EntityLock._tornado_lock.release()

  def ensure_release_tornado_lock(self):
    """ Ensures that tornado lock (which is global for datastore server)
    is released.
    It MUST BE CALLED any time when lock is acquired
    even if entity group lock in zookeeper left acquired after failure.
    """
    if self.is_acquired:
      EntityLock._tornado_lock.release()

  def _inner_release(self):
    """ Release the lock by removing created nodes. """
    if not self.is_acquired:
      return False

    try:
      self._delete_nodes(self.nodes)
    except NoNodeError:
      pass

    self.is_acquired = False
    self.nodes = [None for _ in self.paths]
    return True

  def __enter__(self):
    self.unsafe_acquire()

  def __exit__(self, exc_type, exc_value, traceback):
    self.release()
