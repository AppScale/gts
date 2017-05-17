""" Module responsible for configuring Stats API and stats publishing. """
import attr
from appscale.common import appscale_info

from appscale.hermes import Respond404Handler
from appscale.hermes.stats.constants import (
  UPDATE_NODE_STATS_INTERVAL, UPDATE_PROCESSES_STATS_INTERVAL,
  UPDATE_PROXIES_STATS_INTERVAL, UPDATE_CLUSTER_NODES_STATS_INTERVAL,
  UPDATE_CLUSTER_PROCESSES_STATS_INTERVAL, UPDATE_CLUSTER_PROXIES_STATS_INTERVAL,
  NODE_STATS_CACHE_SIZE, PROCESSES_STATS_CACHE_SIZE, PROXIES_STATS_CACHE_SIZE,
  CLUSTER_NODES_STATS_CACHE_SIZE, CLUSTER_PROCESSES_STATS_CACHE_SIZE,
  CLUSTER_PROXIES_STATS_CACHE_SIZE
)
from appscale.hermes.stats.converter import IncludeLists
from appscale.hermes.stats.handlers import (
  CachedStatsHandler, CurrentStatsHandler
)
from appscale.hermes.stats.handlers import ClusterStatsHandler
from appscale.hermes.stats.producers.cluster_stats import (
  ClusterNodesStatsSource, ClusterProxiesStatsSource,
  ClusterProcessesStatsSource
)
from appscale.hermes.stats.producers.node_stats import NodeStatsSource
from appscale.hermes.stats.producers.process_stats import ProcessesStatsSource
from appscale.hermes.stats.producers.proxy_stats import ProxiesStatsSource
from appscale.hermes.stats.pubsub_base import StatsPublisher
from appscale.hermes.stats.subscribers.cache import (
  StatsCache, ClusterStatsCache
)
from appscale.hermes.stats.subscribers.profile import (
  ClusterNodesProfileLog, ClusterProxiesProfileLog, ClusterProcessesProfileLog
)


@attr.s
class LocalStats(object):
  """ Container for high level information related to local stats """
  cache_size = attr.ib()
  update_interval = attr.ib()
  cache = attr.ib(default=None)
  publisher = attr.ib(default=None)


@attr.s
class ClusterStats(object):
  """ Container for high level information related to cluster stats """
  cache_size = attr.ib()
  update_interval = attr.ib()
  cache = attr.ib(default=None)
  publisher = attr.ib(default=None)
  included_field_lists = attr.ib(default=None)


@attr.s
class HandlerInfo(object):
  """ Container for handler information """
  handler_class = attr.ib()
  init_kwargs = attr.ib()


class StatsApp(object):
  """
  This class holds logic related to start of stats pubsub and API endpoints.

  There are 6 possible kinds of stats:
   - local node stats (cpu, memory, disk, ...);
   - local processes stats (cpu, memory, ... per monitored process);
   - local proxies stats (haproxy stats collected from local haproxy socket);
   - cluster node stats (dict[node_ip, local_node_stats]);
   - cluster processes stats (dict[node_ip, local_processes_stats]);
   - cluster proxies stats (dict[node_ip, local_proxies_stats]);

  Statistics works differently on master node, load balancer node and other
  regular nodes.

  Additionaly to that stats supports different levels of severity:
   - tracking processes can be disabled;
   - csv profile log can be written optionally;
   - cluster stats collected on master node can be reduced by disabling
     verbose cluster stats. It tells cluster stats collector to request only
     limited number of fields;
  """

  def __init__(self, is_master, track_processes, write_profile,
               verbose_cluster_stats):
    """ Initializes all properties which will be used to configure stats

    Args:
      is_master: a boolean indicating whether this node should collect statistics
              from other nodes
      track_processes: a boolean indicating whether process stats should be
              collected and published
      write_profile: a boolean indicating whether CSV log should be written
      verbose_cluster_stats: a boolean indicating whether all available stats
              should be collected on master node (otherwise master will
              select only specific important fields)
    """
    my_ip = appscale_info.get_private_ip()
    lb_ips = appscale_info.get_load_balancer_ips()

    self._is_lb = my_ip in lb_ips
    if is_master is not None:
      self._is_master = is_master
    else:
      self._is_master = my_ip == appscale_info.get_headnode_ip()
    self._track_processes = track_processes
    self._write_profile = write_profile

    # There are 3 kinds of local stats (node/processes/proxies)
    self._local_node_stats = LocalStats(
      cache_size=NODE_STATS_CACHE_SIZE,
      update_interval=UPDATE_NODE_STATS_INTERVAL)
    self._local_processes_stats = LocalStats(
      cache_size=PROCESSES_STATS_CACHE_SIZE,
      update_interval=UPDATE_PROCESSES_STATS_INTERVAL)
    self._local_proxies_stats = LocalStats(
      cache_size=PROXIES_STATS_CACHE_SIZE,
      update_interval=UPDATE_PROXIES_STATS_INTERVAL)

    if self._is_master:
      # And 3 same kinds of cluster stats
      self._cluster_nodes_stats = ClusterStats(
        cache_size=CLUSTER_NODES_STATS_CACHE_SIZE,
        update_interval=UPDATE_CLUSTER_NODES_STATS_INTERVAL)
      self._cluster_processes_stats = ClusterStats(
        cache_size=CLUSTER_PROCESSES_STATS_CACHE_SIZE,
        update_interval=UPDATE_CLUSTER_PROCESSES_STATS_INTERVAL)
      self._cluster_proxies_stats = ClusterStats(
        cache_size=CLUSTER_PROXIES_STATS_CACHE_SIZE,
        update_interval=UPDATE_CLUSTER_PROXIES_STATS_INTERVAL)

      if not verbose_cluster_stats:
        # To reduce slave-to-master traffic and verbosity of cluster stats
        # you can select which fields of stats to collect on master
        self._cluster_nodes_stats.included_field_lists = IncludeLists({
          'node': ['utc_timestamp', 'cpu', 'memory',
                   'partitions_dict', 'loadavg'],
          'node.cpu': ['percent', 'count'],
          'node.memory': ['available'],
          'node.partition': ['free', 'used'],
          'node.loadavg': ['last_5min'],
        })
        self._cluster_processes_stats.included_field_lists = IncludeLists({
          'process': ['monit_name', 'unified_service_name', 'application_id',
                      'port', 'cpu', 'memory', 'children_stats_sum'],
          'process.cpu': ['user', 'system', 'percent'],
          'process.memory': ['resident', 'virtual', 'unique'],
          'process.children_stats_sum': ['cpu', 'memory'],
        })
        self._cluster_proxies_stats.included_field_lists = IncludeLists({
          'proxy': ['name', 'unified_service_name', 'application_id',
                    'frontend', 'backend'],
          'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
          'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
        })

    # All routes (handlers will be assigned during configuration)
    self._routes = {
      '/stats/local/node/cache': None,
      '/stats/local/node/current': None,
      '/stats/local/processes/cache': None,
      '/stats/local/processes/current': None,
      '/stats/local/proxies/cache': None,
      '/stats/local/proxies/current': None,
      '/stats/cluster/nodes': None,
      '/stats/cluster/processes': None,
      '/stats/cluster/proxies': None,
    }
    self._publishers = []

  def configure(self):
    """ Builds publishers list and routes for stats API
        according to configurations
    """
    # Every single node produces node stats
    self._init_local_node_stats_publisher()

    if self._track_processes:
      # Processes stats are optional
      self._init_local_processes_stats_publisher()
    else:
      self._stub_processes_stats_routes()

    if self._is_lb:
      # Load balancer node also provides proxies stats
      self._init_local_proxies_stats_publisher()
    else:
      self._stub_proxies_stats_routes()

    if self._is_master:
      # Master collects stats from all nodes and provides API for access
      self._init_cluster_node_stats_publisher()
      if self._track_processes:
        self._init_cluster_processes_stats_publisher()
      self._init_cluster_proxies_stats_publisher()
    else:
      self._stub_cluster_stats_routes()

  def start_publishers(self):
    """ Starts tornado periodic tasks for each of configured stats publishers
    """
    for publisher in self._publishers:
      publisher.start()

  def get_routes(self):
    """ Returns stats API endpoints.

    Returns:
      a list of tuples (<route>, <handler_class>, <init_kwargs>)
    """
    return [
      (route, handler.handler_class, handler.init_kwargs)
      for route, handler in self._routes.iteritems()
    ]

  def _init_local_node_stats_publisher(self):
    """ Starts node stats publisher, creates cache for local node stats
        and initializes corresponding API endpoints.
    """
    stats = self._local_node_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = NodeStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._publishers.append(stats.publisher)
    # Configure handlers
    self._routes['/stats/local/node/cache'] = HandlerInfo(
      handler_class=CachedStatsHandler,
      init_kwargs=dict(stats_cache=stats.cache)
    )
    self._routes['/stats/local/node/current'] = HandlerInfo(
      handler_class=CurrentStatsHandler,
      init_kwargs=dict(stats_source=stats_source)
    )

  def _init_local_processes_stats_publisher(self):
    """ Starts processes stats publisher, creates cache for local proc. stats
        and initializes corresponding API endpoints.
    """
    stats = self._local_processes_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = ProcessesStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._publishers.append(stats.publisher)
    # Configure handlers
    self._routes['/stats/local/processes/cache'] = HandlerInfo(
      handler_class=CachedStatsHandler,
      init_kwargs=dict(stats_cache=stats.cache)
    )
    self._routes['/stats/local/processes/current'] = HandlerInfo(
      handler_class=CurrentStatsHandler,
      init_kwargs=dict(stats_source=stats_source)
    )

  def _stub_processes_stats_routes(self):
    """ Sets stub handlers to processes stats API endpoints
    """
    self._routes['/stats/local/processes/cache'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Processes stats is disabled')
    )
    self._routes['/stats/local/processes/current'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Processes stats is disabled')
    )
    self._routes['/stats/cluster/processes'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Processes stats is disabled')
    )

  def _init_local_proxies_stats_publisher(self):
    """ Starts proxies stats publisher, creates cache for local proxies stats
        and initializes corresponding API endpoints.
    """
    stats = self._local_proxies_stats
    # Init cache
    stats.cache = StatsCache(stats.cache_size)
    # Init source
    stats_source = ProxiesStatsSource()
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    self._publishers.append(stats.publisher)
    # Configure handlers
    self._routes['/stats/local/proxies/cache'] = HandlerInfo(
      handler_class=CachedStatsHandler,
      init_kwargs=dict(stats_cache=stats.cache)
    )
    self._routes['/stats/local/proxies/current'] = HandlerInfo(
      handler_class=CurrentStatsHandler,
      init_kwargs=dict(stats_source=stats_source)
    )

  def _stub_proxies_stats_routes(self):
    """ Sets stub handlers to proxies stats API endpoints
    """
    self._routes['/stats/local/proxies/cache'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Only LB node provides proxies stats')
    )
    self._routes['/stats/local/proxies/current'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Only LB node provides proxies stats')
    )

  def _init_cluster_node_stats_publisher(self):
    """ Starts cluster node stats publisher,
        creates cache for cluster node stats
        and initializes corresponding API endpoints.
    """
    stats = self._cluster_nodes_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterNodesStatsSource(
      local_cache=self._local_node_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size,
      fetch_latest_only=True
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      include = self._cluster_nodes_stats.included_field_lists
      profile_log = ClusterNodesProfileLog(include)
      stats.publisher.subscribe(profile_log)
    self._publishers.append(stats.publisher)
    # Configure handler
    self._routes['/stats/cluster/nodes'] = HandlerInfo(
      handler_class=ClusterStatsHandler,
      init_kwargs=dict(cluster_stats_cache=stats.cache)
    )

  def _init_cluster_processes_stats_publisher(self):
    """ Starts cluster processes stats publisher,
        creates cache for cluster processes stats
        and initializes corresponding API endpoints.
    """
    stats = self._cluster_processes_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterProcessesStatsSource(
      local_cache=self._local_processes_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size,
      fetch_latest_only=True
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      include = self._cluster_processes_stats.included_field_lists
      profile_log = ClusterProcessesProfileLog(include)
      stats.publisher.subscribe(profile_log)
    self._publishers.append(stats.publisher)
    # Configure handler
    self._routes['/stats/cluster/processes'] = HandlerInfo(
      handler_class=ClusterStatsHandler,
      init_kwargs=dict(cluster_stats_cache=stats.cache)
    )

  def _init_cluster_proxies_stats_publisher(self):
    """ Starts cluster proxies stats publisher,
        creates cache for cluster proxies stats
        and initializes corresponding API endpoints.
    """
    stats = self._cluster_proxies_stats
    # Init cache
    stats.cache = ClusterStatsCache(stats.cache_size)
    # Init source
    stats_source = ClusterProxiesStatsSource(
      local_cache=self._local_proxies_stats.cache,
      include_lists=stats.included_field_lists,
      limit=stats.cache_size,
      fetch_latest_only=True
    )
    # Configure stats publishing
    stats.publisher = StatsPublisher(stats_source, stats.update_interval)
    stats.publisher.subscribe(stats.cache)
    if self._write_profile:
      include = self._cluster_proxies_stats.included_field_lists
      profile_log = ClusterProxiesProfileLog(include)
      stats.publisher.subscribe(profile_log)
    self._publishers.append(stats.publisher)
    # Configure handler
    self._routes['/stats/cluster/proxies'] = HandlerInfo(
      handler_class=ClusterStatsHandler,
      init_kwargs=dict(cluster_stats_cache=stats.cache)
    )

  def _stub_cluster_stats_routes(self):
    """ Sets stub handlers to cluster stats API endpoints
    """
    self._routes['/stats/cluster/nodes'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Only master node provides cluster stats')
    )
    self._routes['/stats/cluster/processes'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Only master node provides cluster stats')
    )
    self._routes['/stats/cluster/proxies'] = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs=dict(reason='Only master node provides cluster stats')
    )
