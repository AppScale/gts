import functools
import inspect
import logging
import random
import traceback
import time

DEFAULT_BACKOFF_BASE = 2
DEFAULT_BACKOFF_MULTIPLIER = 0.2
DEFAULT_BACKOFF_THRESHOLD = 300
DEFAULT_MAX_RETRIES = 10
DEFAULT_RETRYING_TIMEOUT = 60
DEFAULT_RETRY_ON_EXCEPTION = (Exception, )   # Retry after any exception.

MISSED = object()

logger = logging.getLogger(__name__)


class BothMissedException(Exception):
  pass


def not_missed(value_1, value_2):
  if value_1 is not MISSED:
    return value_1
  if value_2 is not MISSED:
    return value_2
  raise BothMissedException()


class _Retry(object):
  def __init__(self, backoff_base, backoff_multiplier, backoff_threshold,
               max_retries, retrying_timeout, retry_on_exception):
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
    self.backoff_base = backoff_base
    self.backoff_multiplier = backoff_multiplier
    self.backoff_threshold = backoff_threshold
    self.max_retries = max_retries
    self.retrying_timeout = retrying_timeout
    self.retry_on_exception = retry_on_exception

  def __call__(self, func=None, backoff_base=MISSED, backoff_multiplier=MISSED,
               backoff_threshold=MISSED, max_retries=MISSED,
               retrying_timeout=MISSED, retry_on_exception=MISSED):
    """ Wraps func with retry mechanism which runs up to max_retries attempts
    with exponential backoff (sleep = backoff_multiplier * backoff_base**X).
    Or just creates another instance of _Retry with custom parameters.

    Args:
      func: a callable to wrap.
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
      A wrapped callable or parametrised instance of its class
      if function was omitted in arguments.
    """
    params = (backoff_base, backoff_multiplier, backoff_threshold, max_retries,
              retrying_timeout, retry_on_exception)

    if any((argument is not MISSED) for argument in params):
      # There are custom retrying parameters
      custom_retry = type(self)(
        backoff_base=not_missed(backoff_base, self.backoff_base),
        backoff_multiplier=not_missed(backoff_multiplier,
                                      self.backoff_multiplier),
        backoff_threshold=not_missed(backoff_threshold, self.backoff_threshold),
        max_retries=not_missed(max_retries, self.max_retries),
        retrying_timeout=not_missed(retrying_timeout, self.retrying_timeout),
        retry_on_exception=not_missed(retry_on_exception,
                                      self.retry_on_exception)
      )

      if func is None:
        # This is probably called using decorator syntax with parameters:
        # @retry_data_watch_coroutine(retrying_timeout=60)
        # def func():
        #   ...
        return custom_retry
      else:
        # This is used as a regular function to get wrapped function.
        return custom_retry.wrap(func)

    return self.wrap(func)

  def wrap(self, func):
    """ Wraps func with retry mechanism which runs up to max_retries attempts
    with exponential backoff (sleep = backoff_multiplier * backoff_base**X).

    Args:
      func: function to wrap.
    Returns:
      A wrapped function.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
      check_exception = self.retry_on_exception

      if inspect.isclass(check_exception):
        if issubclass(check_exception, Exception):
          check_exception = (check_exception, )

      if isinstance(check_exception, (list, tuple)):
        exception_classes = check_exception

        def check_exception_in_list(error):
          return any(
            isinstance(error, exception) for exception in exception_classes
          )

        check_exception = check_exception_in_list

      retries = 0
      backoff = self.backoff_multiplier
      start_time = time.time()
      while True:
        # Start of retrying iteration
        try:
          # Call original function
          return func(*args, **kwargs)

        except Exception as err:
          retries += 1

          # Check if need to retry
          if self.max_retries is not None and retries > self.max_retries:
            logger.error("Giving up retrying after {} attempts during {:0.1f}s"
                         .format(retries, time.time()-start_time))
            raise
          timeout = self.retrying_timeout
          if timeout and time.time() - start_time > timeout:
            logger.error("Giving up retrying after {} attempts during {:0.1f}s"
                         .format(retries, time.time()-start_time))
            raise
          if not check_exception(err):
            raise

          # Proceed with exponential backoff
          backoff = min(backoff * self.backoff_base, self.backoff_threshold)
          sleep_time = backoff * (random.random() * 0.3 + 0.85)
          # Report problem to logs
          stacktrace = traceback.format_exc()
          msg = "Retry #{} in {:0.1f}s".format(retries, sleep_time)
          logger.warning(stacktrace + msg)

          time.sleep(sleep_time)

        # End of retrying iteration

    return wrapped

retry = _Retry(
  backoff_base=DEFAULT_BACKOFF_BASE,
  backoff_multiplier=DEFAULT_BACKOFF_MULTIPLIER,
  backoff_threshold=DEFAULT_BACKOFF_THRESHOLD,
  max_retries=DEFAULT_MAX_RETRIES,
  retrying_timeout=DEFAULT_RETRYING_TIMEOUT,
  retry_on_exception=DEFAULT_RETRY_ON_EXCEPTION
)
