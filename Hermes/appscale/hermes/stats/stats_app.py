import attr
from appscale.common import appscale_info

from appscale.hermes.constants import UPDATE_NODE_STATS_INTERVAL, \
  UPDATE_PROCESSES_STATS_INTERVAL, UPDATE_PROXIES_STATS_INTERVAL, \
  UPDATE_CLUSTER_NODES_STATS_INTERVAL, UPDATE_CLUSTER_PROCESSES_STATS_INTERVAL, \
  UPDATE_CLUSTER_PROXIES_STATS_INTERVAL, NODE_STATS_CACHE_SIZE, \
  PROCESSES_STATS_CACHE_SIZE, PROXIES_STATS_CACHE_SIZE, \
  CLUSTER_NODES_STATS_CACHE_SIZE, CLUSTER_PROCESSES_STATS_CACHE_SIZE, \
  CLUSTER_PROXIES_STATS_CACHE_SIZE
from appscale.hermes.stats.handlers import CachedStatsHandler, \
  CurrentStatsHandler, \
  Respond404Handler
from appscale.hermes.stats.handlers import ClusterStatsHandler
from appscale.hermes.stats.producers.cluster_stats import \
  ClusterNodesStatsSource, ClusterProxiesStatsSource, \
  ClusterProcessesStatsSource
from appscale.hermes.stats.producers.node_stats import NodeStatsSource
from appscale.hermes.stats.producers.process_stats import ProcessesStatsSource
from appscale.hermes.stats.producers.proxy_stats import ProxiesStatsSource
from appscale.hermes.stats.pubsub_base import StatsPublisher
from appscale.hermes.stats.subscribers.cache import StatsCache, \
  ClusterStatsCache
from appscale.hermes.stats.subscribers.profile import ClusterNodesProfileLog, \
  ClusterProxiesProfileLog, ClusterProcessesProfileLog


@attr.s
class LocalStats(object):
  cache_size = attr.ib()
  update_interval = attr.ib()
  cache = attr.ib(default=None)
  publisher = attr.ib(default=None)


@attr.s
class ClusterStats(object):
  cache_size = attr.ib()
  update_interval = attr.ib()
  cache = attr.ib(default=None)
  publisher = attr.ib(default=None)
  included_field_lists = attr.ib(default=None)


class StatsApp(object):

  def __init__(self, master, track_processes, write_profile,
               minimize_cluster_stats):
    my_ip = appscale_info.get_private_ip()
    lb_ips = appscale_info.get_load_balancer_ips()

    self._is_lb = my_ip in lb_ips
    if master is not None:
      self._is_master = master
    else:
      self._is_master = my_ip == appscale_info.get_headnode_ip()
    self._track_processes = track_processes
    self._write_profile = write_profile

    self._local_node_stats = LocalStats(
      cache_size=NODE_STATS_CACHE_SIZE,
      update_interval=UPDATE_NODE_STATS_INTERVAL)
    self._local_processes_stats = LocalStats(
      cache_size=PROCESSES_STATS_CACHE_SIZE,
      update_interval=UPDATE_PROCESSES_STATS_INTERVAL)
    self._local_proxies_stats = LocalStats(
      cache_size=PROXIES_STATS_CACHE_SIZE,
      update_interval=UPDATE_PROXIES_STATS_INTERVAL)

    self._cluster_nodes_stats = ClusterStats(
      cache_size=CLUSTER_NODES_STATS_CACHE_SIZE,
      update_interval=UPDATE_CLUSTER_NODES_STATS_INTERVAL)
    self._cluster_processes_stats = ClusterStats(
      cache_size=CLUSTER_PROCESSES_STATS_CACHE_SIZE,
      update_interval=UPDATE_CLUSTER_PROCESSES_STATS_INTERVAL)
    self._cluster_proxies_stats = ClusterStats(
      cache_size=CLUSTER_PROXIES_STATS_CACHE_SIZE,
      update_interval=UPDATE_CLUSTER_PROXIES_STATS_INTERVAL)

    if minimize_cluster_stats:
      # To reduce slave-to-master traffic and verbosity of cluster stats
      # you can select which fields of stats to collect on master
      self._cluster_nodes_stats.included_field_lists = {
        # TODO
      }
      self._cluster_processes_stats.included_field_lists = {
        # TODO
      }
      self._cluster_proxies_stats.included_field_lists = {
        # TODO
      }

    # All routes (handlers will be assigned during configuration)
    self._routes = {
      'stats/local/node/cache': None,
      'stats/local/node/current': None,
      'stats/local/processes/cache': None,
      'stats/local/processes/current': None,
      'stats/local/proxies/cache': None,
      'stats/local/proxies/current': None,
      'stats/cluster/nodes': None,
      'stats/cluster/processes': None,
      'stats/cluster/proxies': None,
    }
    self._active_publishers = []

  def configure(self):
    self._init_local_node_stats_publisher()

    if self._track_processes:
      self._init_local_processes_stats_publisher()
    else:
      self._stub_processes_stats_routes()

    if self._is_lb:
      self._init_local_proxies_stats_publisher()
    else:
      self._stub_proxies_stats_routes()

    if self._is_master:
      self._init_cluster_node_stats_publisher()
      if self._track_processes:
        self._init_cluster_processes_stats_publisher()
      self._init_cluster_proxies_stats_publisher()
    else:
      self._stub_cluster_stats_routes()

    return self._active_publishers, self._routes

  def _init_local_node_stats_publisher(self):
    stats = self._local_node_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = NodeStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._active_publishers.append(stats.publisher)
    # Configure handlers
    self._routes['stats/local/node/cache'] = (
      CachedStatsHandler, dict(stats_cache=stats.cache))
    self._routes['stats/local/node/current'] = (
      CurrentStatsHandler, dict(stats_source=stats_source))

  def _init_local_processes_stats_publisher(self):
    stats = self._local_processes_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = ProcessesStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._active_publishers.append(stats.publisher)
    # Configure handlers
    self._routes['stats/local/processes/cache'] = (
      CachedStatsHandler, dict(stats_cache=stats.cache))
    self._routes['stats/local/processes/current'] = (
      CurrentStatsHandler, dict(stats_source=stats_source))

  def _stub_processes_stats_routes(self):
    self._routes['stats/local/processes/cache'] = (
      Respond404Handler, dict(reason='Processes stats is disabled'))
    self._routes['stats/local/processes/current'] = (
      Respond404Handler, dict(reason='Processes stats is disabled'))
    self._routes['stats/cluster/processes'] = (
      Respond404Handler, dict(reason='Processes stats is disabled'))

  def _init_local_proxies_stats_publisher(self):
    stats = self._local_proxies_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = ProxiesStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._active_publishers.append(stats.publisher)
    # Configure handlers
    self._routes['stats/local/proxies/cache'] = (
      CachedStatsHandler, dict(stats_cache=stats.cache))
    self._routes['stats/local/proxies/current'] = (
      CurrentStatsHandler, dict(stats_source=stats_source))

  def _stub_proxies_stats_routes(self):
    self._routes['stats/local/proxies/cache'] = (
      Respond404Handler, dict(reason='Only LB node provides proxies stats'))
    self._routes['stats/local/proxies/current'] = (
      Respond404Handler, dict(reason='Only LB node provides proxies stats'))

  def _init_cluster_node_stats_publisher(self):
    stats = self._cluster_nodes_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterNodesStatsSource(
      local_cache=self._local_node_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      profile_log = ClusterNodesProfileLog()
      stats.publisher.subscribe(profile_log)
    self._active_publishers.append(stats.publisher)
    # Configure handler
    self._routes['stats/cluster/nodes'] = (
      ClusterStatsHandler, dict(cluster_stats_cache=stats.cache))

  def _init_cluster_processes_stats_publisher(self):
    stats = self._cluster_processes_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterProcessesStatsSource(
      local_cache=self._local_processes_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      profile_log = ClusterProcessesProfileLog()
      stats.publisher.subscribe(profile_log)
    self._active_publishers.append(stats.publisher)
    # Configure handler
    self._routes['stats/cluster/processes'] = (
      ClusterStatsHandler, dict(cluster_stats_cache=stats.cache))

  def _init_cluster_proxies_stats_publisher(self):
    stats = self._cluster_proxies_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterProxiesStatsSource(
      local_cache=self._local_proxies_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      profile_log = ClusterProxiesProfileLog()
      stats.publisher.subscribe(profile_log)
    self._active_publishers.append(stats.publisher)
    # Configure handler
    self._routes['stats/cluster/proxies'] = (
      ClusterStatsHandler, dict(cluster_stats_cache=stats.cache))

  def _stub_cluster_stats_routes(self):
    self._routes['stats/cluster/nodes'] = (
      Respond404Handler, dict(reason='Only master node provides cluster stats'))
    self._routes['stats/cluster/processes'] = (
      Respond404Handler, dict(reason='Only master node provides cluster stats'))
    self._routes['stats/cluster/proxies'] = (
      Respond404Handler, dict(reason='Only master node provides cluster stats'))
