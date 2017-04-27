import threading
import time
from datetime import datetime

from appscale.hermes.stats.pubsub_base import StatsSubscriber

BIG_BANG_TIMESTAMP = 0


class StatsCache(StatsSubscriber):
  """
  It takes care about storing snapshots in limited cache and provides
  reading method with acknowledgment mechanism.
  Each node has local stats cache for each kind of stats it collects
  (node stats, processes stats and haproxy stats for LB nodes).
  It is used as a temporary storage for stats which wasn't read by master yet.  
  """

  def __init__(self, snapshots_cache_size, ttl=None):
    super(StatsCache, self).__init__("StatsCache")
    self._snapshots_cache = []
    self._cache_lock = threading.Lock()
    if snapshots_cache_size < 1:
      raise ValueError("Snapshots cache size can be fewer than 1")
    self._snapshots_cache_size = snapshots_cache_size
    self._ttl = ttl

  def receive(self, stats_snapshot):
    """ Appends stats_snapshot to the limited cache.
    If cache size is exceeded removes oldest snapshots.
    
    Args:
      stats_snapshot: an object with utc_timestamp attribute
    """
    self._cache_lock.acquire()
    try:
      self._snapshots_cache.append(stats_snapshot)
      self._clean_expired()
      if len(self._snapshots_cache) > self._snapshots_cache_size:
        # Remove oldest snapshots which exceed cache size
        diff = len(self._snapshots_cache) - self._snapshots_cache_size
        self._snapshots_cache = self._snapshots_cache[diff:]
    finally:
      self._cache_lock.release()

  def bulk_receive(self, stats_snapshots):
    """ Appends stats_snapshots to the limited cache.
    If cache size is exceeded removes oldest snapshots.
    
    Args:
      stats_snapshots: a list of objects with utc_timestamp attribute
    """
    self._cache_lock.acquire()
    try:
      self._snapshots_cache += stats_snapshots
      self._clean_expired()
      if len(self._snapshots_cache) > self._snapshots_cache_size:
        # Remove oldest snapshots which exceed cache size
        diff = len(self._snapshots_cache) - self._snapshots_cache_size
        self._snapshots_cache = self._snapshots_cache[diff:]
    finally:
      self._cache_lock.release()

  def get_stats_after(self, last_timestamp=BIG_BANG_TIMESTAMP, clean_older=True):
    """ Gets statistics snapshots which are newer than last_timestamp. 
    Optionally it can remove older snapshots. In this case last_timestamp 
    works like acknowledgment in TCP
    
    Args:
      last_timestamp: unix epoch timestamp of the latest snapshot which was read
      clean_older: determines whether older snapshots should be removed
    Returns:
      a list of statistic snapshots newer than last_timastamp
    """
    self._cache_lock.acquire()
    try:
      self._clean_expired()
      try:
        # Need to return only snapshots which are newer than last_timestamp
        start_index = next((
          i for i in xrange(0, len(self._snapshots_cache))
          if self._snapshots_cache[i].utc_timestamp > last_timestamp
        ))
      except StopIteration:
        # There are no newer snapshots
        return []
      result = self._snapshots_cache[start_index:]
      if clean_older:
        self._snapshots_cache = self._snapshots_cache[start_index:]
      return result
    finally:
      self._cache_lock.release()

  def get_latest(self):
    self._cache_lock.acquire()
    try:
      self._clean_expired()
      return self._snapshots_cache[-1]
    finally:
      self._cache_lock.release()

  def _clean_expired(self):
    if not self._ttl:
      return
    now = time.mktime(datetime.utcnow().timetuple())
    while self._snapshots_cache:
      if now - self._snapshots_cache[0].utc_timestamp > self._ttl:
        del self._snapshots_cache[0]
      else:
        break


class ClusterStatsCache(StatsSubscriber):

  def __init__(self, per_node_cache_size, ttl=None):
    super(ClusterStatsCache, self).__init__("ClusterStatsCache")
    self._node_caches = {}
    if per_node_cache_size < 1:
      raise ValueError("Per node cache size can be fewer than 1")
    self._per_node_cache_size = per_node_cache_size
    self._ttl = ttl

  def receive(self, nodes_stats_dict):
    new_node_caches_dict = {}
    for node_ip, stats_snapshots in nodes_stats_dict.iteritems():
      node_stats_cache = self._node_caches.get(node_ip)
      if not node_stats_cache:
        node_stats_cache = StatsCache(self._per_node_cache_size, self._ttl)
      node_stats_cache.bulk_receive(stats_snapshots)
      new_node_caches_dict[node_ip] = node_stats_cache
    self._node_caches = new_node_caches_dict

  def get_stats_after(self, last_timestamps_dict=None, clean_older=True):
    if not last_timestamps_dict:
      return {
        node_ip: cache.get_stats_after(BIG_BANG_TIMESTAMP, clean_older)
        for node_ip, cache in self._node_caches.iteritems()
      }
    return {
      node_ip: cache.get_stats_after(
        last_timestamps_dict.get(node_ip, BIG_BANG_TIMESTAMP), clean_older
      )
      for node_ip, cache in self._node_caches.iteritems()
    }

  def get_latest(self):
    latest_stats = {}
    no_fresh_stats_for = []
    for node_ip, cache in self._node_caches.iteritems():
      try:
        snapshot = cache.get_latest()
        latest_stats[node_ip] = snapshot
      except IndexError:
        no_fresh_stats_for.append(node_ip)
    return latest_stats, no_fresh_stats_for