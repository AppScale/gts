from stats.handlers import CachedStatsHandler, CurrentStatsHandler, \
  Respond404Handler
from stats.producers.node_stats import NodeStatsSource
from stats.producers.process_stats import ProcessesStatsSource

from appscale.hermes.stats.subscribers.cache import StatsCache


def configure_node(cache_size, track_processes):
  node_stats_source = NodeStatsSource()
  node_stats_cache = StatsCache(cache_size)

  pubsub = {
    node_stats_source: [node_stats_cache]
  }
  routes = [
    ('stats/local/node/cache',
     CachedStatsHandler, dict(stats_cache=node_stats_cache)),
    ('stats/local/node/current',
     CurrentStatsHandler, dict(stats_source=node_stats_source)),
    ('stats/local/proxies/cache',
     Respond404Handler, dict(reason='Only LB nodes has this endpoint')),
    ('stats/local/proxies/current',
     Respond404Handler, dict(reason='Only LB nodes has this endpoint')),
    ('stats/cluster/node',
     Respond404Handler, dict(reason='Only master node has this endpoint')),
    ('stats/cluster/processes',
     Respond404Handler, dict(reason='Only master node has this endpoint')),
    ('stats/cluster/proxies',
     Respond404Handler, dict(reason='Only master node has this endpoint')),
  ]

  if track_processes:
    processes_stats_source = ProcessesStatsSource()
    processes_stats_cache = StatsCache(cache_size)

    pubsub[processes_stats_source] = [processes_stats_cache]
    routes += [
      ('stats/local/processes/cache',
       CachedStatsHandler, dict(stats_cache=processes_stats_cache)),
      ('stats/local/processes/current',
       CurrentStatsHandler, dict(stats_source=processes_stats_source))
    ]
  else:
    routes += [
      ('stats/local/processes/cache',
       Respond404Handler, dict(reason='Tracking processes stats is disabled')),
      ('stats/local/processes/current',
       Respond404Handler, dict(reason='Tracking processes stats is disabled'))
    ]
  return pubsub, routes


class StatsApp(object):

  def __init__(self, track_processes, write_profile, minimize_cluster_stats):
    my_ip =
    lb_ips =
    self._is_lb = False
    self._is_master = False
    self._track_processes = track_processes
    self._write_profile = write_profile

    # Local caches sizes
    self._local_node_stats_cache_size = 50
    self._local_processes_stats_cache_size = 50
    self._local_proxies_stats_cache_size = 50
    # Cluster caches sizes (only on master node)
    self._cluster_nodes_stats_cache_size = 1
    self._cluster_processes_stats_cache_size = 1
    self._cluster_proxies_stats_cache_size = 1

    # Local stats publishing interval
    self._update_local_node_stats_interval = 10
    self._update_local_processes_stats_interval = 30
    self._update_local_proxies_stats_interval = 10
    # Cluster stats publishing interval
    self._update_cluster_nodes_stats_interval = 10
    self._update_cluster_processes_stats_interval = 30
    self._update_cluster_proxies_stats_interval = 10

    if minimize_cluster_stats:
      # To reduce slave-to-master traffic and verbosity of cluster stats
      # you can select which fields of stats to collect on master
      self._cluster_nodes_stats_include = {
        "node": [],
        "node.cpu": []
        # TODO
      }
      self._cluster_processes_stats_include = {
        "process": [],
        "process.cpu": []
        # TODO
      }
      self._cluster_proxies_stats_include = {
        "proxy": [],
        "proxy.frontend": []
        # TODO
      }
    else:
      # Include all
      self._cluster_nodes_stats_include = None
      self._cluster_processes_stats_include = None
      self._cluster_proxies_stats_include = None


    # Attributes bellow will be initialized in configure method:

    # Local caches
    self._local_node_stats_cache = None
    self._local_processes_stats_cache = None
    self._local_proxies_stats_cache = None
    # Cluster caches (only on master node)
    self._cluster_nodes_stats_cache = None
    self._cluster_processes_stats_cache = None
    self._cluster_proxies_stats_cache = None

    # Local stats publishers
    self._node_stats_publisher = None
    self._processes_stats_publisher = None
    self._proxies_stats_publisher = None
    # Cluster stats publishers (only on master node)
    self._cluster_nodes_stats_publisher = None
    self._cluster_processes_stats_publisher = None
    self._cluster_proxies_stats_publisher = None

  def configure(self):
    pass

  def _
    pass