""" Implementation of stats sources for cluster stats (node, processes, proxies) """
import json
import logging
import sys
import time

from appscale.common import appscale_info
from tornado import gen, httpclient
from tornado.options import options
from tornado.web import HTTPError

from appscale.hermes import constants
from appscale.hermes.constants import REQUEST_TIMEOUT, SECRET_HEADER
from appscale.hermes.stats import converter
from appscale.hermes.stats.constants import CLUSTER_STATS_DEBUG_INTERVAL
from appscale.hermes.stats.producers import (
  proxy_stats, node_stats, process_stats
)
from appscale.hermes.stats.pubsub_base import AsyncStatsSource


class BadStatsListFormat(ValueError):
  """ Is used when Hermes slave responds with improperly formatted stats """
  pass


class ClusterNodesStatsSource(AsyncStatsSource):
  """
  Gets node stats from all nodes in the cluster.
  In verbose mode of Hermes it will 'scroll' cached stats from all nodes
  using timestamp as a cursor.
  """

  def __init__(self, local_cache, include_lists=None, limit=None,
               fetch_latest_only=False):
    """ Initialises an instance of ClusterNodeStatsSource.

    Args:
      local_cache: an instance of LocalStatsCache where node stats of this node
          are cached. It's used to avoid HTTP calls to local API.
      include_lists: an instance of IncludeLists
      limit: an integer representing a max number of stats snapshots to fetch
          from slave node per one call.
          Be careful with this number, if you plan to scroll all stats
          history (instead of tracking latest only) master node should collect
          stats a bit faster than it's produced on slaves.
      fetch_latest_only: a boolean determines whether old stats can be ignored.
          If it's True, master will request latest stats always,
          otherwise it will request stats snapshots newer than latest read,
          so if limit is specified, it can get the latest stats with delay.
    """
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit
    self._fetch_latest_only = fetch_latest_only
    self._last_debug = 0

  @gen.coroutine
  def get_current_async(self):
    """ Implements StatsSource.get_current_async() method. Makes concurrent
    asynchronous http calls to cluster nodes and collects new node stats.

    Returns:
      A Future object which wraps a dict with node IP as key and list of
      new NodeStatsSnapshot as value
    """
    all_ips = appscale_info.get_all_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_node_stats_dict = yield {
      node_ip: self._new_node_stats_from_node_async(node_ip)
      for node_ip in all_ips
    }
    if time.time() - self._last_debug > CLUSTER_STATS_DEBUG_INTERVAL:
      self._last_debug = time.time()
      logging.debug(per_node_node_stats_dict)
    raise gen.Return(per_node_node_stats_dict)

  @gen.coroutine
  def _new_node_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
      if self._limit is not None:
        if self._fetch_latest_only and len(new_snapshots) > self._limit:
          new_snapshots = new_snapshots[len(new_snapshots)-self._limit:]
        else:
          new_snapshots = new_snapshots[:self._limit]
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/node/cache',
        stats_class=node_stats.NodeStatsSnapshot,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists, limit=self._limit,
        fetch_latest_only=self._fetch_latest_only
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


class ClusterProcessesStatsSource(AsyncStatsSource):
  """
  Gets processes stats from all nodes in the cluster.
  In verbose mode of Hermes it will 'scroll' cached stats from all nodes
  using timestamp as a cursor.
  """

  def __init__(self, local_cache, include_lists=None, limit=None,
               fetch_latest_only=False):
    """ Initialises an instance of ClusterProcessesStatsSource.

    Args:
      local_cache: an instance of LocalStatsCache where processes stats of this
          node is cached. It's used to avoid HTTP calls to local API
      include_lists: an instance of IncludeLists
      limit: an integer representing a max number of stats snapshots to fetch
          from slave node per one call.
          Be careful with this number, if you plan to scroll all stats
          history (instead of tracking latest only) master node should collect
          stats a bit faster than it's produced on slaves.
      fetch_latest_only: a boolean determines whether old stats can be ignored.
          If it's True, master will request latest stats always,
          otherwise it will request stats snapshots newer than latest read,
          so if limit is specified, it can get the latest stats with delay.
    """
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit
    self._fetch_latest_only = fetch_latest_only
    self._last_debug = 0

  @gen.coroutine
  def get_current_async(self):
    """ Implements StatsSource.get_current_async() method. Makes concurrent
    asynchronous http calls to cluster nodes and collects new processes stats.

    Returns:
      A Future object which wraps a dict with node IP as key and list of
      new ProcessesStatsSnapshot as value
    """
    all_ips = appscale_info.get_all_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_processes_stats_dict = yield {
      node_ip: self._new_processes_stats_from_node_async(node_ip)
      for node_ip in all_ips
    }
    if time.time() - self._last_debug > CLUSTER_STATS_DEBUG_INTERVAL:
      self._last_debug = time.time()
      logging.debug(per_node_processes_stats_dict)
    raise gen.Return(per_node_processes_stats_dict)

  @gen.coroutine
  def _new_processes_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
      if self._limit is not None:
        if self._fetch_latest_only and len(new_snapshots) > self._limit:
          new_snapshots = new_snapshots[len(new_snapshots)-self._limit:]
        else:
          new_snapshots = new_snapshots[:self._limit]
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/processes/cache',
        stats_class=process_stats.ProcessesStatsSnapshot,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists, limit=self._limit,
        fetch_latest_only=self._fetch_latest_only
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


class ClusterProxiesStatsSource(AsyncStatsSource):
  """
  Gets proxies stats from all nodes in the cluster.
  In verbose mode of Hermes it will 'scroll' cached stats from all nodes
  using timestamp as a cursor.
  """

  def __init__(self, local_cache=None, include_lists=None, limit=None,
               fetch_latest_only=False):
    """ Initialises an instance of ClusterProxiesStatsSource.

    Args:
      local_cache: an instance of LocalStatsCache where proxies stats of this
          node is cached. It's used to avoid HTTP calls to local API
      include_lists: an instance of IncludeLists
      limit: an integer representing a max number of stats snapshots to fetch
          from slave node per one call.
          Be careful with this number, if you plan to scroll all stats
          history (instead of tracking latest only) master node should collect
          stats a bit faster than it's produced on slaves.
      fetch_latest_only: a boolean determines whether old stats can be ignored.
          If it's True, master will request latest stats always,
          otherwise it will request stats snapshots newer than latest read,
          so if limit is specified, it can get the latest stats with delay.
    """
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit
    self._fetch_latest_only = fetch_latest_only
    self._last_debug = 0

  @gen.coroutine
  def get_current_async(self):
    """ Implements StatsSource.get_current_async() method. Makes concurrent
    asynchronous http calls to cluster nodes and collects new proxies stats.

    Returns:
      A Future object which wraps a dict with node IP as key and list of
      new ProxiesStatsSnapshot as value
    """
    lb_ips = appscale_info.get_load_balancer_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_proxies_stats_dict = yield {
      node_ip: self._new_proxies_stats_from_node_async(node_ip)
      for node_ip in lb_ips
    }
    if time.time() - self._last_debug > CLUSTER_STATS_DEBUG_INTERVAL:
      self._last_debug = time.time()
      logging.debug(per_node_proxies_stats_dict)
    raise gen.Return(per_node_proxies_stats_dict)

  @gen.coroutine
  def _new_proxies_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
      if self._limit is not None:
        if self._fetch_latest_only and len(new_snapshots) > self._limit:
          new_snapshots = new_snapshots[len(new_snapshots)-self._limit:]
        else:
          new_snapshots = new_snapshots[:self._limit]
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/proxies/cache',
        stats_class=proxy_stats.ProxiesStatsSnapshot,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists, limit=self._limit,
        fetch_latest_only=self._fetch_latest_only
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


@gen.coroutine
def _fetch_remote_stats_cache_async(node_ip, method_path, stats_class,
                                    last_utc_timestamp, limit, include_lists,
                                    fetch_latest_only):
  # Security header
  headers = {SECRET_HEADER: options.secret}
  # Build query arguments
  arguments = {}
  if last_utc_timestamp is not None:
    arguments['last_utc_timestamp'] = last_utc_timestamp
  if limit is not None:
    arguments['limit'] = limit
  if include_lists is not None:
    arguments['include_lists'] = include_lists.to_dict()
  if fetch_latest_only:
    arguments['fetch_latest_only'] = True

  url = "http://{ip}:{port}/{path}".format(
    ip=node_ip, port=constants.HERMES_PORT, path=method_path)
  request = httpclient.HTTPRequest(
    url=url, method='GET', body=json.dumps(arguments), headers=headers,
    validate_cert=False, request_timeout=REQUEST_TIMEOUT,
    allow_nonstandard_methods=True
  )
  async_client = httpclient.AsyncHTTPClient()

  try:
    # Send Future object to coroutine and suspend till result is ready
    response = yield async_client.fetch(request)
  except HTTPError as e:
    logging.error("Failed to get stats from {} ({})".format(url, e))
    raise gen.Return([])

  try:
    stats_dictionaries = json.loads(response.body)
    snapshots = [
      converter.stats_from_dict(stats_class, stats_dict)
      for stats_dict in stats_dictionaries
    ]
  except TypeError as err:
    msg = u"Can't parse stats snapshot ({})".format(err)
    raise BadStatsListFormat(msg), None, sys.exc_info()[2]

  raise gen.Return(snapshots)
