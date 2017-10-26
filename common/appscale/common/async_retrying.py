import collections
import functools
import logging
import random
import traceback
import time

from tornado import locks, gen
from tornado.ioloop import IOLoop

from appscale.common.retrying import (
  DEFAULT_BACKOFF_BASE, DEFAULT_BACKOFF_MULTIPLIER, DEFAULT_BACKOFF_THRESHOLD,
  DEFAULT_MAX_RETRIES, DEFAULT_RETRYING_TIMEOUT, DEFAULT_RETRY_ON_EXCEPTION,
  MISSED, not_missed
)


class _RetryCoroutine(object):
  def __init__(self, backoff_base=MISSED, backoff_multiplier=MISSED,
               backoff_threshold=MISSED, max_retries=MISSED,
               retrying_timeout=MISSED, retry_on_exception=MISSED):
    """
    Args:
      backoff_base: a number to use in backoff calculation.
      backoff_multiplier: a number indicating initial backoff.
      backoff_threshold: a number indicating maximum backoff.
      max_retries: an integer indicating maximum number of retries.
      retrying_timeout: a number indicating number of seconds after which
        retrying should be stopped.
      retry_on_exception: a function receiving one argument: exception object
        and returning True if retry makes sense for such exception.
        Alternatively you can pass list of exception types for which
        retry is needed.
    """
    self.backoff_base = not_missed(backoff_base, DEFAULT_BACKOFF_BASE)
    self.backoff_multiplier = not_missed(backoff_multiplier,
                                         DEFAULT_BACKOFF_MULTIPLIER)
    self.backoff_threshold = not_missed(backoff_threshold,
                                        DEFAULT_BACKOFF_THRESHOLD)
    self.max_retries = not_missed(max_retries, DEFAULT_MAX_RETRIES)
    self.retrying_timeout = not_missed(retrying_timeout,
                                       DEFAULT_RETRYING_TIMEOUT)
    self.retry_on_exception = not_missed(retry_on_exception,
                                         DEFAULT_RETRY_ON_EXCEPTION)

  def __call__(self, func=None, backoff_base=MISSED, backoff_multiplier=MISSED,
               backoff_threshold=MISSED, max_retries=MISSED,
               retrying_timeout=MISSED, retry_on_exception=MISSED):
    """ Wraps python generator with tornado coroutine and retry mechanism
    which runs up to max_retries attempts with exponential backoff
    (sleep = backoff_multiplier * backoff_base**X).

    Args:
      func: a function to wrap.
      backoff_base: a number to use in backoff calculation.
      backoff_multiplier: a number indicating initial backoff.
      backoff_threshold: a number indicating maximum backoff.
      max_retries: an integer indicating maximum number of retries.
      retrying_timeout: a number indicating number of seconds after which
        retrying should be stopped.
      retry_on_exception: a function receiving one argument: exception object
        and returning True if retry makes sense for such exception.
        Alternatively you can pass list of exception types for which
        retry is needed.
    Returns:
      A wrapped coroutine or self if coroutine arg was omitted in arguments.
    """
    if func is None:
      return _RetryCoroutine(
        backoff_base=backoff_base,
        backoff_multiplier=backoff_multiplier,
        backoff_threshold=backoff_threshold,
        max_retries=max_retries,
        retrying_timeout=retrying_timeout,
        retry_on_exception=retry_on_exception
      )

    args = (backoff_base, backoff_multiplier, backoff_threshold, max_retries,
            retrying_timeout, retry_on_exception)
    if any((argument is not MISSED) for argument in args):
      raise TypeError('You should pass either func or parameters')

    coroutine = gen.coroutine(func)

    @functools.wraps(coroutine)
    @gen.coroutine
    def wrapped(*args, **kwargs):
      # Allow runtime customization of retrying parameters.
      base = kwargs.pop('backoff_base', self.backoff_base)
      multiplier = kwargs.pop('backoff_multiplier', self.backoff_multiplier)
      threshold = kwargs.pop('backoff_threshold', self.backoff_threshold)
      retries_limit = kwargs.pop('max_retries', self.max_retries)
      timeout = kwargs.pop('retrying_timeout', self.retrying_timeout)
      check_exception = kwargs.pop('retry_on_exception',
                                   self.retry_on_exception)

      if check_exception is None:
        check_exception = lambda error: True
      elif isinstance(check_exception, (list, tuple)):
        orig_check_exception = check_exception
        check_exception = lambda error: error.__class__ in orig_check_exception

      retries = 0
      backoff = multiplier
      start_time = time.time()
      while True:
        # Start of retrying iteration
        try:
          # Call original coroutine
          result = yield coroutine(*args, **kwargs)
          break

        except Exception as err:
          retries += 1

          # Check if need to retry
          if retries_limit is not None and retries > retries_limit:
            logging.error("Giving up retrying after {} attempts during {:0.1f}s"
                          .format(retries,  - start_time))
            raise
          if timeout and time.time() - start_time > timeout:
            logging.error("Giving up retrying after {} attempts during {:0.1f}s"
                          .format(retries, time.time() - start_time))
            raise
          if not check_exception(err):
            raise

          # Proceed with exponential backoff
          backoff = min(backoff * base, threshold)
          sleep_time = backoff * (random.random() * 0.3 + 0.85)
          # Report problem to logs
          stacktrace = traceback.format_exc()
          msg = "Retry #{} in {:0.1f}s".format(retries, sleep_time)
          logging.warn(stacktrace + msg)

          yield gen.sleep(sleep_time)

        # End of retrying iteration

      raise gen.Return(result)

    return wrapped

retry_coroutine = _RetryCoroutine()


class _PersistentWatch(object):

  def __init__(self):

    class CompliantLock(object):
      """
      A container which allows to organize compliant locking
      of zk_node by making sure:
       - update function won't be interrupted by another;
       - sleep between retries can be interrupted by newer update;
       - _PersistentWatch is able to identify and remove unused locks.
      """
      def __init__(self):
        self.waiters = 0
        self.lock = locks.Lock()
        self.condition = locks.Condition()

    # Dict of locks for zk_nodes (shared between all functions decorated
    # by an instance of _PersistentWatch)
    self._locks = collections.defaultdict(CompliantLock)

    # Default retrying parameters
    self.backoff_base = DEFAULT_BACKOFF_BASE
    self.backoff_multiplier = DEFAULT_BACKOFF_MULTIPLIER
    self.backoff_threshold = DEFAULT_BACKOFF_THRESHOLD
    self.max_retries = DEFAULT_MAX_RETRIES
    self.retrying_timeout = DEFAULT_RETRYING_TIMEOUT
    self.retry_on_exception = DEFAULT_RETRY_ON_EXCEPTION

  def __call__(self, node, func=None, backoff_base=MISSED,
               backoff_multiplier=MISSED, backoff_threshold=MISSED,
               max_retries=MISSED, retrying_timeout=MISSED,
               retry_on_exception=MISSED):
    """ Wraps func with retry mechanism which runs up to max_retries attempts
    with exponential backoff (sleep = backoff_multiplier * backoff_base**X).

    Args:
      node: a string representing path to zookeeper node.
      func: function or coroutine to wrap.
      backoff_base: a number to use in backoff calculation.
      backoff_multiplier: a number indicating initial backoff.
      backoff_threshold: a number indicating maximum backoff.
      max_retries: an integer indicating maximum number of retries.
      retrying_timeout: a number indicating number of seconds after which
        retrying should be stopped.
      retry_on_exception: a function receiving one argument: exception object
        and returning True if retry makes sense for such exception.
        Alternatively you can pass list of exception types for which
        retry is needed.
    Returns:
      A tornado coroutine wrapping function with retry mechanism.
    """
    if backoff_base is not MISSED:
      self.backoff_base = backoff_base
    if backoff_multiplier is not MISSED:
      self.backoff_multiplier = backoff_multiplier
    if backoff_threshold is not MISSED:
      self.backoff_threshold = backoff_threshold
    if max_retries is not MISSED:
      self.max_retries = max_retries
    if retrying_timeout is not MISSED:
      self.retrying_timeout = retrying_timeout
    if retry_on_exception is not MISSED:
      self.retry_on_exception = retry_on_exception

    if func is None:
      return self

    @functools.wraps(func)
    @gen.coroutine
    def persistent_execute(*args, **kwargs):
      # Allow runtime customization of retrying parameters.
      base = kwargs.pop('backoff_base', self.backoff_base)
      multiplier = kwargs.pop('backoff_multiplier', self.backoff_multiplier)
      threshold = kwargs.pop('backoff_threshold', self.backoff_threshold)
      retries_limit = kwargs.pop('max_retries', self.max_retries)
      timeout = kwargs.pop('retrying_timeout', self.retrying_timeout)
      check_exception = kwargs.pop('retry_on_exception',
                                   self.retry_on_exception)
      if check_exception is None:
        check_exception = lambda error: True
      elif isinstance(check_exception, (list, tuple)):
        check_exception = lambda error: error.__class__ in check_exception

      retries = 0
      backoff = multiplier
      start_time = time.time()
      node_lock = self._locks[node]
      result = None

      # Wake older update calls (*)
      node_lock.condition.notify_all()
      node_lock.waiters += 1
      with (yield node_lock.lock.acquire()):
        node_lock.waiters -= 1

        while True:
          # Start of retrying iteration
          try:
            result = func(*args, **kwargs)
            if isinstance(result, gen.Future):
              result = yield result
            break

          except Exception as e:
            retries += 1

            # Check if need to retry
            if retries_limit is not None and retries > retries_limit:
              logging.error(
                "Giving up retrying after {} attempts during {:0.1f}s"
                .format(retries, time.time() - start_time))
              fail = True
            elif timeout and time.time() - start_time > timeout:
              logging.error(
                "Giving up retrying after {} attempts during {:0.1f}s"
                .format(retries, time.time() - start_time))
              fail = True
            elif not check_exception(e):
              fail = True
            else:
              fail = False

            if fail:
              if not node_lock.waiters:
                del self._locks[node]
              raise

            # Proceed with exponential backoff
            backoff = backoff * base
            if backoff > threshold:
              backoff = threshold
            sleep_time = backoff * (random.random() * 0.3 + 0.85)
            # Report problem to logs
            stacktrace = traceback.format_exc()
            msg = "Retry #{} in {:0.1f}s".format(retries, sleep_time)
            logging.warn(stacktrace + msg)

            # (*) Sleep with one eye open, give up if newer update wakes you
            now = IOLoop.current().time()
            interrupted = yield node_lock.condition.wait(now + sleep_time)
            if interrupted or node_lock.waiters:
              logging.info("Giving up retrying because newer update came up")
              if not node_lock.waiters:
                del self._locks[node]
              raise gen.Return()

          # End of retrying iteration

      if not node_lock.waiters:
        del self._locks[node]
      raise gen.Return(result)

    return persistent_execute


# Two different instances for having two locks namespaces
retry_data_watch_coroutine = _PersistentWatch()
retry_children_watch_coroutine = _PersistentWatch()
