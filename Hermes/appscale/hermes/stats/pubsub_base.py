""" Base classes for building stats publishers and subscribers """
import logging
import sys

from tornado.ioloop import PeriodicCallback, IOLoop


class SubscriberIsAlreadyRegistered(Exception):
  """ Raised when you register single subscriber twice on one publisher """
  pass


class SubscriberIsNotRegistered(Exception):
  """ Raised when you unregister subscriber which is not registered yet """
  pass


class StatsSource(object):
  """
  Base class for producers of any kind of stats.
  Subclasses should implement method get_current()
  """
  @property
  def stats_name(self):
    return self.__class__.__name__

  def __repr__(self):
    return self.stats_name

  def get_current(self):
    """ Returns: current value of specific kind of stats """
    raise NotImplementedError()


class AsyncStatsSource(object):
  """
  Base class for asynchronous producers of any kind of stats.
  Subclasses should implement get_current_async()
  """
  @property
  def stats_name(self):
    return self.__class__.__name__

  def __repr__(self):
    return self.stats_name

  def get_current_async(self):
    """ Returns: Future wrapper for current value of specific kind of stats """
    raise NotImplementedError()


class StatsSubscriber(object):
  """
  Base class for stats consumers.
  Subclasses should implement method receive(stats)
  """
  @property
  def subscriber_name(self):
      return self.__class__.__name__

  def __repr__(self):
    return self.subscriber_name
  
  def receive(self, stats):
    """ Handlers produced stats entity
    Args:
      stats: an object containing stats of some kind (node, processes, ...)
    """
    raise NotImplementedError()


class StatsPublisher(object):
  """
  Linker between a specific stats source (synchronous or asynchronous)
  and a list of subscribers.
  """

  def __init__(self, stats_source, publishing_interval):
    """ Initializes an instance of stats publisher.
    Args:
      stats_source: an instance of subclass of StatsSource or AsyncStatsSource
      publishing_interval: an integer determines publishing cycle length in ms 
    """
    self._subscribers = {}
    self._stats_source = stats_source
    self._publishing_interval = publishing_interval
    self._periodic_callback = PeriodicCallback(
      self._read_and_publish, publishing_interval)

  def subscribe(self, subscriber):
    """ Adds subscriber to the list of subscribers.
    Args:
      subscriber: an instance of subclass of StatsSubscriber """
    if subscriber.subscriber_name in self._subscribers:
      raise SubscriberIsAlreadyRegistered(
        "Subscriber with name '{subscriber}' is already subscribed on {stats}"
        .format(subscriber=subscriber.subscriber_name,
                stats=self._stats_source.stats_name)
      )
    self._subscribers[subscriber.subscriber_name] = subscriber

  def unsubscribe(self, subscriber_name):
    """ Removes subscriber from the list of subscribers.
    Args:
      subscriber_name: a string representing name of subscriber to remove """
    if subscriber_name not in self._subscribers:
      raise SubscriberIsNotRegistered(
        "Subscriber with name '{subscriber}' is not subscribed on {stats}"
        .format(subscriber=subscriber_name, stats=self._stats_source.stats_name)
      )
    del self._subscribers[subscriber_name]

  def _read_and_publish(self):
    """ Gets stats entity or Future wrapper of it from stats source and sends
        or schedules sending of stats to subscribers
    """
    if isinstance(self._stats_source, AsyncStatsSource):
      stats_future = self._stats_source.get_current_async()
      IOLoop.current().add_future(stats_future, self._publish_callback)
    else:
      stats = self._stats_source.get_current()
      self._publish(stats)

  def _publish_callback(self, future):
    self._publish(future.result())

  def _publish(self, stats):
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
    self._read_and_publish()
    return self._periodic_callback.start()

  def stop(self):
    return self._periodic_callback.stop()
