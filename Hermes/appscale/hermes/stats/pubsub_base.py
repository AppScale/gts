import logging
import sys

from tornado.ioloop import PeriodicCallback


class SubscriberIsAlreadyRegistered(Exception):
  pass


class SubscriberIsNotRegistered(Exception):
  pass


class StatsSource(object):
  def __init__(self, stats_name):
    self._stats_name = stats_name
  
  @property
  def stats_name(self):
    return self._stats_name
  
  def get_current(self):
    raise NotImplemented

  def __repr__(self):
    return self._stats_name

  def __hash__(self):
    return self._stats_name.__hash__()

  def __eq__(self, other):
    return (
      isinstance(other, StatsSource) and self._stats_name == other._stats_name
    )


class StatsSubscriber(object):
  def __init__(self, subscriber_name):
    self._subscriber_name = subscriber_name
  
  @property
  def subscriber_name(self):
    return self._subscriber_name
  
  def receive(self, stats):
    raise NotImplemented

  def __repr__(self):
    return self._subscriber_name


class StatsPublisher(object):
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
