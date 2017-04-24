import logging
import sys
import threading
from functools import wraps


class StatsBuffer(object):
  """
  It takes care about storing snapshots in limited buffer and provides
  reading method with acknowledgment mechanism.
  Each node has local stats buffer for each kind of stats it collects
  (node stats, processes stats and haproxy stats for LB nodes).
  It is used as a temporary storage for stats which wasn't read by master yet.  
  """

  def __init__(self, snapshots_buffer_size):
    self._snapshots_buf = []
    self._buffer_lock = threading.Lock()
    if snapshots_buffer_size < 1:
      raise ValueError("Snapshots buffer size can be fewer than 1")
    self._snapshots_buffer_size = snapshots_buffer_size

  @stats_subscriber("StatsBuffer")
  def append_stats_snapshot(self, stats_snapshot):
    """ Appends stats_snapshot to the limited buffer.
    If buffer size is exceeded removes oldest snapshots.
    
    Args:
      stats_snapshot: an object with utc_timestamp attribute
    """
    self._buffer_lock.acquire()
    self._snapshots_buf.append(stats_snapshot)
    if len(self._snapshots_buf) > self._snapshots_buffer_size:
      # Remove oldest snapshots which exceed buffer size
      diff = len(self._snapshots_buf) - self._snapshots_buffer_size
      self._snapshots_buf = self._snapshots_buf[diff:]
    self._buffer_lock.release()

  def get_stats_after(self, last_timestamp, clean_older=True):
    """ Gets statistics snapshots which are newer than last_timestamp. 
    Optionally it can remove older snapshots. In this case last_timestamp 
    works like acknowledgment in TCP
    
    Args:
      last_timestamp: unix epoch timestamp of the latest snapshot which was read
      clean_older: determines whether older snapshots should be removed
    Returns:
      a list of statistic snapshots newer than last_timastamp
    """
    self._buffer_lock.acquire()
    try:
      if not last_timestamp:
        # Need to return all snapshots
        start_index = 0
      else:
        try:
          # Need to return only snapshots which are newer than last_timestamp
          start_index = next((
            i for i in xrange(0, len(self._snapshots_buf))
            if self._snapshots_buf[i].utc_timestamp > last_timestamp
          ))
        except StopIteration:
          # There are no newer snapshots
          return []
      result = self._snapshots_buf[start_index:]
      if clean_older:
        self._snapshots_buf = self._snapshots_buf[start_index:]
      return result
    finally:
      self._buffer_lock.release()

  def get_latest_snapshot(self):
    """ Returns the latest snapshot which is in snapshots buffer.
    If buffer is empty - IndexError is raised """
    return self._snapshots_buf[-1]


class SubscriberIsAlreadyRegistered(Exception):
  pass


class SubscriberIsNotRegistered(Exception):
  pass


def stats_subscriber(subscriber_name):
  def decorator(subscriber_function):
    @wraps(subscriber_function)
    def subscriber():
      return subscriber_function()
    subscriber.subscriber_name = subscriber_name
    return subscriber
  return decorator


def stats_reader(stats_name):
  def decorator(reader_function):
    @wraps(reader_function)
    def reader():
      return reader_function()
    reader.stats_name = stats_name
    return reader
  return decorator


class StatsPublisher(object):
  def __init__(self, stats_reader_function):
    self._subscribers = {}
    self._stats_name = stats_reader_function.stats_name
    self._stats_reader = stats_reader_function

  def subscribe(self, subscriber):
    if subscriber.subscriber_name in self._subscribers:
      raise SubscriberIsAlreadyRegistered(
        "Subscriber with name '{subscriber}' is already subscribed on {stats}"
        .format(subscriber=subscriber.subscriber_name, stats=self._stats_name)
      )
    self._subscribers[subscriber.subscriber_name] = subscriber

  def unsubscribe(self, subscriber):
    if subscriber.subscriber_name not in self._subscribers:
      raise SubscriberIsNotRegistered(
        "Subscriber with name '{subscriber}' is not subscribed on {stats}"
        .format(subscriber=subscriber.subscriber_name, stats=self._stats_name)
      )
    del self._subscribers[subscriber.subscriber_name]

  def read_and_publish(self):
    stats = self._stats_reader()
    for name, subscriber in self._subscribers.iteritems():
      try:
        logging.debug(
          "Sending {stats} to {subscriber}"
          .format(stats=self._stats_name, subscriber=name)
        )
        subscriber(stats)
      except Exception:
        logging.error(
          "Failed to send {stats} to {subscriber}"
          .format(stats=self._stats_name, subscriber=name),
          exc_info=sys.exc_info()
        )
