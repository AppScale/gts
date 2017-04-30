import logging
import sys

from tornado.ioloop import PeriodicCallback


class SubscriberIsAlreadyRegistered(Exception):
  """ Raised when you register single subscriber twice on one publisher """
  pass


class SubscriberIsNotRegistered(Exception):
  """ Raised when you unregister subscriber which is not registered yet """
  pass


class StatsSource(object):
  """
  Base class for producers of any kind of stats.
  It's only characteristic is name of stats. It's mostly used for logging
  purposes.
  Subclasses should implement method get_current()
  """

  def __init__(self, stats_name):
    self._stats_name = stats_name
  
  @property
  def stats_name(self):
    return self._stats_name
  
  def get_current(self):
    """
    Returns:
      current value of specific kind of stats
    """
    raise NotImplemented

  def __repr__(self):
    return self._stats_name


class StatsSubscriber(object):
  """
  Base class for producers of any kind of stats.
  It's only characteristic is name of stats. It's mostly used for logging
  purposes.
  Subclasses should implement method get_current()
  """
  def __init__(self, subscriber_name):
    self._subscriber_name = subscriber_name
  
  @property
  def subscriber_name(self):
    return self._subscriber_name
  
  def receive(self, stats):
    """ Handlers another one stats entity

    Args:
      stats: an object containing stats of some kind (node, processes, ...)
    """
    raise NotImplemented

  def __repr__(self):
    return self._subscriber_name


class StatsPublisher(object):
  """
  TODO
  """
  def __init__(self, stats_source, publishing_interval):
    self._subscribers = {}
    self._stats_source = stats_source
    self._publishing_interval = publishing_interval
    self._periodic_callback = PeriodicCallback(
      self.read_and_publish, publishing_interval)

  def subscribe(self, subscriber):
    if subscriber.subscriber_name in self._subscribers:
      raise SubscriberIsAlreadyRegistered(
        "Subscriber with name '{subscriber}' is already subscribed on {stats}"
        .format(subscriber=subscriber.subscriber_name,
                stats=self._stats_source.stats_name)
      )
    self._subscribers[subscriber.subscriber_name] = subscriber

  def unsubscribe(self, subscriber):
    if subscriber.subscriber_name not in self._subscribers:
      raise SubscriberIsNotRegistered(
        "Subscriber with name '{subscriber}' is not subscribed on {stats}"
        .format(subscriber=subscriber.subscriber_name,
                stats=self._stats_source.stats_name)
      )
    del self._subscribers[subscriber.subscriber_name]

  def read_and_publish(self):
    stats = self._stats_source.get_current()
    for name, subscriber in self._subscribers.iteritems():
      try:
        logging.debug(
          "Sending {stats} to {subscriber}"
          .format(stats=self._stats_source.stats_name, subscriber=name)
        )
        subscriber.receive(stats)
      except Exception:
        logging.error(
          "Failed to send {stats} to {subscriber}"
          .format(stats=self._stats_source.stats_name, subscriber=name),
          exc_info=sys.exc_info()
        )

  def start(self):
    return self._periodic_callback.start()

  def stop(self):
    return self._periodic_callback.stop()
