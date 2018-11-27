""" A wrapper that converts Kazoo operations to Tornado futures. """
import datetime
import random
import six
import sys
import time
import uuid

from kazoo.exceptions import (
  CancelledError, ConnectionClosedError, ConnectionLoss, KazooException,
  LockTimeout, NoNodeError, OperationTimeoutError, SessionExpiredError)
from kazoo.retry import (
  ForceRetryError, InterruptedError as KazooInterruptedError,
  RetryFailedError)
from tornado import gen
from tornado.concurrent import Future as TornadoFuture
from tornado.ioloop import IOLoop
from tornado.locks import Event as AsyncEvent, Lock as AsyncLock


class AsyncKazooRetry(object):
  """ A retry helper based on kazoo.retry.KazooRetry and modified to work with
      coroutines. """
  RETRY_EXCEPTIONS = (
    ConnectionLoss,
    OperationTimeoutError,
    ForceRetryError
  )

  EXPIRED_EXCEPTIONS = (
    SessionExpiredError,
  )

  def __init__(self, max_tries=1, delay=0.1, backoff=2, max_jitter=0.8,
               max_delay=60, ignore_expire=True, deadline=None,
               interrupt=None):
    """ Creates an AsyncKazooRetry for retrying coroutines.

    Args:
      max_tries: How many times to retry the command. -1 means infinite tries.
      delay: Initial delay between retry attempts.
      backoff: Backoff multiplier between retry attempts. Defaults to 2 for
        exponential backoff.
      max_jitter: Additional max jitter period to wait between retry attempts
        to avoid slamming the server.
      max_delay: Maximum delay in seconds, regardless of other backoff
        settings. Defaults to one minute.
      ignore_expire: Whether a session expiration should be ignored and treated
        as a retry-able command.
      interrupt:
        Function that will be called with no args that may return
        True if the retry should be ceased immediately. This will
        be called no more than every 0.1 seconds during a wait
        between retries.

    """
    self.max_tries = max_tries
    self.delay = delay
    self.backoff = backoff
    self.max_jitter = int(max_jitter * 100)
    self.max_delay = float(max_delay)
    self._attempts = 0
    self._cur_delay = delay
    self.deadline = deadline
    self._cur_stoptime = None
    self.retry_exceptions = self.RETRY_EXCEPTIONS
    self.interrupt = interrupt
    if ignore_expire:
      self.retry_exceptions += self.EXPIRED_EXCEPTIONS

  def reset(self):
    """ Resets the attempt counter. """
    self._attempts = 0
    self._cur_delay = self.delay
    self._cur_stoptime = None

  def copy(self):
    """ Returns a clone of this retry manager. """
    obj = AsyncKazooRetry(max_tries=self.max_tries,
                          delay=self.delay,
                          backoff=self.backoff,
                          max_jitter=self.max_jitter / 100.0,
                          max_delay=self.max_delay,
                          deadline=self.deadline,
                          interrupt=self.interrupt)
    obj.retry_exceptions = self.retry_exceptions
    return obj

  @gen.coroutine
  def __call__(self, func, *args, **kwargs):
    """ Calls a coroutine with arguments until it completes without
    throwing a Kazoo exception.

    Args:
      func: Coroutine to yield
      args: Positional arguments to call the function with
      kwargs: Keyword arguments to call the function with

    The coroutine will be called until it doesn't throw one of the
    retryable exceptions (ConnectionLoss, OperationTimeout, or
    ForceRetryError), and optionally retrying on session
    expiration.
    """
    self.reset()

    while True:
      try:
        if self.deadline is not None and self._cur_stoptime is None:
          self._cur_stoptime = time.time() + self.deadline
        response = yield func(*args, **kwargs)
        raise gen.Return(response)
      except ConnectionClosedError:
        raise
      except self.retry_exceptions:
        # Note: max_tries == -1 means infinite tries.
        if self._attempts == self.max_tries:
          raise RetryFailedError("Too many retry attempts")
        self._attempts += 1
        sleeptime = self._cur_delay + (
                random.randint(0, self.max_jitter) / 100.0)

        if self._cur_stoptime is not None and \
                time.time() + sleeptime >= self._cur_stoptime:
          raise RetryFailedError("Exceeded retry deadline")

        if self.interrupt:
          while sleeptime > 0:
            # Break the time period down and sleep for no
            # longer than 0.1 before calling the interrupt
            if sleeptime < 0.1:
              yield gen.sleep(sleeptime)
              sleeptime -= sleeptime
            else:
              yield gen.sleep(0.1)
              sleeptime -= 0.1
            if self.interrupt():
              raise KazooInterruptedError()
        else:
          yield gen.sleep(sleeptime)
        self._cur_delay = min(self._cur_delay * self.backoff,
                              self.max_delay)


class AsyncKazooLock(object):
  """ A lock based on kazoo.recipe.Lock and modified to work as a coroutine.
  """

  # Node name, after the contender UUID, before the sequence
  # number. Involved in read/write locks.
  _NODE_NAME = "__lock__"

  # Node names which exclude this contender when present at a lower
  # sequence number. Involved in read/write locks.
  _EXCLUDE_NAMES = ["__lock__"]

  def __init__(self, client, path, identifier=None):
    """ Creates an AsyncKazooLock.

    Args:
      client: A KazooClient.
      path: The lock path to use.
      identifier: The name to use for this lock contender. This can be useful
        for querying to see who the current lock contenders are.
    """
    self.client = client
    self.tornado_kazoo = TornadoKazoo(client)
    self.path = path

    # some data is written to the node. this can be queried via
    # contenders() to see who is contending for the lock
    self.data = str(identifier or "").encode('utf-8')
    self.node = None

    self.wake_event = AsyncEvent()

    # props to Netflix Curator for this trick. It is possible for our
    # create request to succeed on the server, but for a failure to
    # prevent us from getting back the full path name. We prefix our
    # lock name with a uuid and can check for its presence on retry.
    self.prefix = uuid.uuid4().hex + self._NODE_NAME
    self.create_path = self.path + "/" + self.prefix

    self.create_tried = False
    self.is_acquired = False
    self.assured_path = False
    self.cancelled = False
    self._retry = AsyncKazooRetry(max_tries=-1)
    self._lock = AsyncLock()

  @gen.coroutine
  def _ensure_path(self):
    yield self.tornado_kazoo.ensure_path(self.path)
    self.assured_path = True

  def cancel(self):
    """ Cancels a pending lock acquire. """
    self.cancelled = True
    self.wake_event.set()

  @gen.coroutine
  def acquire(self, timeout=None, ephemeral=True):
    """ Acquires the lock. By default, it blocks and waits forever.

    Args:
      timeout: A float specifying how long to wait to acquire the lock.
      ephemeral: A boolean indicating that the lock should use an ephemeral
        node.

    Raises:
      LockTimeout if the lock wasn't acquired within `timeout` seconds.
    """
    retry = self._retry.copy()
    retry.deadline = timeout

    # Ensure we are locked so that we avoid multiple coroutines in
    # this acquisition routine at the same time...
    timeout_interval = None
    if timeout is not None:
      timeout_interval = datetime.timedelta(seconds=timeout)

    try:
      with (yield self._lock.acquire(timeout=timeout_interval)):
        already_acquired = self.is_acquired
        gotten = False
        try:
          gotten = yield retry(self._inner_acquire, timeout=timeout,
                               ephemeral=ephemeral)
        except RetryFailedError:
          pass
        except KazooException:
          # if we did ultimately fail, attempt to clean up
          exc_info = sys.exc_info()
          if not already_acquired:
            yield self._best_effort_cleanup()
            self.cancelled = False
          six.reraise(exc_info[0], exc_info[1], exc_info[2])
        if gotten:
          self.is_acquired = gotten
        if not gotten and not already_acquired:
          yield self._best_effort_cleanup()
        raise gen.Return(gotten)
    except gen.TimeoutError:
      raise LockTimeout("Failed to acquire lock on %s after "
                        "%s seconds" % (self.path, timeout))

  def _watch_session(self, state):
    self.wake_event.set()
    return True

  def _watch_session_listener(self, state):
    IOLoop.current().add_callback(self._watch_session, state)

  @gen.coroutine
  def _inner_acquire(self, timeout, ephemeral=True):

    # wait until it's our chance to get it..
    if self.is_acquired:
      raise ForceRetryError()

    # make sure our election parent node exists
    if not self.assured_path:
      yield self._ensure_path()

    node = None
    if self.create_tried:
      node = yield self._find_node()
    else:
      self.create_tried = True

    if not node:
      node = yield self.tornado_kazoo.create(
        self.create_path, self.data, ephemeral=ephemeral, sequence=True)
      # strip off path to node
      node = node[len(self.path) + 1:]

    self.node = node

    while True:
      self.wake_event.clear()

      # bail out with an exception if cancellation has been requested
      if self.cancelled:
        raise CancelledError()

      children = yield self._get_sorted_children()

      try:
        our_index = children.index(node)
      except ValueError:  # pragma: nocover
        # somehow we aren't in the children -- probably we are
        # recovering from a session failure and our ephemeral
        # node was removed
        raise ForceRetryError()

      predecessor = self.predecessor(children, our_index)
      if not predecessor:
        raise gen.Return(True)

      # otherwise we are in the mix. watch predecessor and bide our time
      predecessor = self.path + "/" + predecessor
      self.client.add_listener(self._watch_session_listener)
      try:
        yield self.tornado_kazoo.get(predecessor, self._watch_predecessor)
      except NoNodeError:
        pass  # predecessor has already been deleted
      else:
        try:
          yield self.wake_event.wait(timeout)
        except gen.TimeoutError:
          raise LockTimeout("Failed to acquire lock on %s after "
                            "%s seconds" % (self.path, timeout))
      finally:
        self.client.remove_listener(self._watch_session_listener)

  def predecessor(self, children, index):
    for c in reversed(children[:index]):
      if any(n in c for n in self._EXCLUDE_NAMES):
        return c
    return None

  def _watch_predecessor(self, event):
    self.wake_event.set()

  @gen.coroutine
  def _get_sorted_children(self):
    children = yield self.tornado_kazoo.get_children(self.path)

    # Node names are prefixed by a type: strip the prefix first, which may
    # be one of multiple values in case of a read-write lock, and return
    # only the sequence number (as a string since it is padded and will
    # sort correctly anyway).
    #
    # In some cases, the lock path may contain nodes with other prefixes
    # (eg. in case of a lease), just sort them last ('~' sorts after all
    # ASCII digits).
    def _seq(c):
      for name in ["__lock__", "__rlock__"]:
        idx = c.find(name)
        if idx != -1:
          return c[idx + len(name):]
      # Sort unknown node names eg. "lease_holder" last.
      return '~'

    children.sort(key=_seq)
    raise gen.Return(children)

  @gen.coroutine
  def _find_node(self):
    children = yield self.tornado_kazoo.get_children(self.path)
    for child in children:
      if child.startswith(self.prefix):
        raise gen.Return(child)
    raise gen.Return(None)

  @gen.coroutine
  def _delete_node(self, node):
    yield self.tornado_kazoo.delete(self.path + "/" + node)

  @gen.coroutine
  def _best_effort_cleanup(self):
    try:
      node = self.node
      if not node:
        node = yield self._find_node()
      if node:
        yield self._delete_node(node)
    except KazooException:  # pragma: nocover
      pass

  @gen.coroutine
  def release(self):
    """Release the lock immediately."""
    retry = self._retry.copy()
    release_response = yield retry(self._inner_release)
    raise gen.Return(release_response)

  @gen.coroutine
  def _inner_release(self):
    if not self.is_acquired:
      raise gen.Return(False)

    try:
      yield self._delete_node(self.node)
    except NoNodeError:  # pragma: nocover
      pass

    self.is_acquired = False
    self.node = None
    raise gen.Return(True)

  @gen.coroutine
  def contenders(self):
    """ Returns an ordered list of the current contenders for the lock. """
    # make sure our election parent node exists
    if not self.assured_path:
      yield self._ensure_path()

    children = yield self._get_sorted_children()

    contenders = []
    for child in children:
      try:
        data = yield self.tornado_kazoo.get(self.path + "/" + child)[0]
        contenders.append(data.decode('utf-8'))
      except NoNodeError:  # pragma: nocover
        pass
    raise gen.Return(contenders)


class IncompleteOperation(Exception):
  """ Indicates that a Kazoo operation is not complete. """
  pass


class TornadoKazooFuture(TornadoFuture):
  """ A TornadoFuture that handles Kazoo results. """
  def handle_zk_result(self, async_result):
    """ Completes the TornadoFuture.

    Args:
      async_result: An IAsyncResult.
    """
    io_loop = IOLoop.instance()

    # This method should not be called if the result is not ready.
    if not async_result.ready():
      error = IncompleteOperation('Kazoo operation is not ready')
      io_loop.add_callback(self.set_exception, error)
      return

    if async_result.successful():
      io_loop.add_callback(self.set_result, async_result.value)
    else:
      io_loop.add_callback(self.set_exception, async_result.exception)


class TornadoKazoo(object):
  """ A wrapper that converts Kazoo operations to Tornado futures. """
  def __init__(self, zk_client):
    """ Creates a new TornadoKazoo manager.

    Args:
      zk_client: A KazooClient.
    """
    self._zk_client = zk_client

  def create(self, path, value=b'', acl=None, ephemeral=False, sequence=False,
             makepath=False):
    """ Creates a node with the given value as its data.

    Args:
      path: A string specifying the path of the node.
      value: A byte string specifying the node contents.
      acl: A kazoo.security.ACL list.
      ephemeral: A boolean indicating whether or not the node should be removed
        upon client disconnection.
      sequence: A boolean indicating whether or not the path should be suffixed
        with a unique index.
      makepath: A boolean indicating whether or not the parent path should be
        created if it doesn't exist.
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.create_async(
      path, value, acl=acl, ephemeral=ephemeral, sequence=sequence,
      makepath=makepath)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def get(self, path, watch=None):
    """ Gets the value of a node.

    Args:
      path: A string specifying the path of the node.
      watch: A function that is called when the node changes.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    if watch is None:
      wrapped_watch = None
    else:
      wrapped_watch = self._wrap_in_io_loop(watch)

    zk_future = self._zk_client.get_async(path, wrapped_watch)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def get_children(self, path, watch=None, include_data=False):
    """ Gets a list of child nodes of a path.

    Args:
      path: A string specifying the path of the parent node.
      watch: A function that is called when the node changes.
      include_data: A boolean specifying that the parent node contents should
        also be fetched.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    if watch is None:
      wrapped_watch = None
    else:
      wrapped_watch = self._wrap_in_io_loop(watch)

    zk_future = self._zk_client.get_children_async(
      path, wrapped_watch, include_data)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def delete(self, path, version=-1):
    """ Deletes a node.

    Args:
      path: A string specifying the path of the node.
      version: An integer specifying the expected version of the node.
    Returns:
      A TornadoKazooFuture.
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.delete_async(path, version=version)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  def ensure_path(self, path, acl=None):
    """ Ensures a node exists.

    Args:
      path: A string specifying the path of the node.
      acl: Permissions for the node (a kazoo.security.ACL list).
    """
    tornado_future = TornadoKazooFuture()
    zk_future = self._zk_client.ensure_path_async(path, acl)
    zk_future.rawlink(tornado_future.handle_zk_result)
    return tornado_future

  @staticmethod
  def _wrap_in_io_loop(watch):
    """ Returns a function that runs the given function in the main IO loop.

    Args:
      watch: The function to wrap.
    """
    def run_in_io_loop(*args):
      IOLoop.current().add_callback(watch, *args)

    return run_in_io_loop
