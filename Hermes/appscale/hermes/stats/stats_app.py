""" Module responsible for configuring Stats API and stats profiling. """
import time
from datetime import datetime

import attr
from tornado.ioloop import PeriodicCallback, IOLoop

from appscale.hermes.handlers import Respond404Handler
from appscale.hermes.stats import profile
from appscale.hermes.stats.constants import PROFILE_NODES_STATS_INTERVAL, \
  PROFILE_PROCESSES_STATS_INTERVAL, PROFILE_PROXIES_STATS_INTERVAL
from appscale.hermes.stats.converter import IncludeLists
from appscale.hermes.stats.handlers import (
  CurrentStatsHandler, CurrentClusterStatsHandler
)
from appscale.hermes.stats.producers.cluster_stats import (
  ClusterNodesStatsSource, ClusterProcessesStatsSource,
  ClusterProxiesStatsSource
)
from appscale.hermes.stats.producers.node_stats import NodeStatsSource
from appscale.hermes.stats.producers.process_stats import ProcessesStatsSource
from appscale.hermes.stats.producers.proxy_stats import ProxiesStatsSource


DEFAULT_INCLUDE_LISTS = IncludeLists({
  # Node stats
  'node': ['utc_timestamp', 'cpu', 'memory',
           'partitions_dict', 'loadavg'],
  'node.cpu': ['percent', 'count'],
  'node.memory': ['available'],
  'node.partition': ['free', 'used'],
  'node.loadavg': ['last_5min'],
  # Processes stats
  'process': ['monit_name', 'unified_service_name', 'application_id',
              'port', 'cpu', 'memory', 'children_stats_sum'],
  'process.cpu': ['user', 'system', 'percent'],
  'process.memory': ['resident', 'virtual', 'unique'],
  'process.children_stats_sum': ['cpu', 'memory'],
  # Proxies stats
  'proxy': ['name', 'unified_service_name', 'application_id',
            'frontend', 'backend'],
  'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
  'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
})


@attr.s
class HandlerInfo(object):
  """ Container for handler information """
  handler_class = attr.ib()
  init_kwargs = attr.ib()


def get_local_stats_api_routes(is_lb_node):
  """ Creates stats sources and API handlers for providing local
  node, processes and proxies (only on LB nodes) stats.

  Args:
    is_lb_node: a boolean indicating whether this node is load balancer
  Returns:
    a list of route-handler tuples
  """

  # Any node provides its node and processes stats
  local_node_stats_handler =  HandlerInfo(
    handler_class=CurrentStatsHandler,
    init_kwargs={'source': NodeStatsSource(),
                 'default_include_lists': DEFAULT_INCLUDE_LISTS})
  local_processes_stats_handler = HandlerInfo(
    handler_class=CurrentStatsHandler,
    init_kwargs={'source': ProcessesStatsSource(),
                 'default_include_lists': DEFAULT_INCLUDE_LISTS})

  if is_lb_node:
    # Only LB nodes provide proxies stats
    local_proxies_stats_handler = HandlerInfo(
      handler_class=CurrentStatsHandler,
      init_kwargs={'source': ProxiesStatsSource(),
                   'default_include_lists': DEFAULT_INCLUDE_LISTS}
    )
  else:
    # Stub handler for non-LB nodes
    local_proxies_stats_handler = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs={'reason': 'Only LB node provides proxies stats'}
    )

  routes = {
    '/stats/local/node': local_node_stats_handler,
    '/stats/local/processes': local_processes_stats_handler,
    '/stats/local/proxies': local_proxies_stats_handler,
  }
  return [
    (route, handler.handler_class, handler.init_kwargs)
    for route, handler in routes.iteritems()
  ]


def get_cluster_stats_api_routes(is_master):
  """ Creates stats sources and API handlers for providing cluster
  node, processes and proxies stats (on master node only).
  If this node is slave, it creates stub handlers for cluster stats routes.

  Args:
    is_master: a boolean indicating whether this node is master
  Returns:
    a list of route-handler tuples
  """
  if is_master:
    # Only master node provides cluster stats
    cluster_node_stats_handler = HandlerInfo(
      handler_class=CurrentClusterStatsHandler,
      init_kwargs={'source': ClusterNodesStatsSource(),
                   'default_include_lists': DEFAULT_INCLUDE_LISTS}
    )
    cluster_processes_stats_handler = HandlerInfo(
      handler_class=CurrentClusterStatsHandler,
      init_kwargs={'source': ClusterProcessesStatsSource(),
                   'default_include_lists': DEFAULT_INCLUDE_LISTS}
    )
    cluster_proxies_stats_handler = HandlerInfo(
      handler_class=CurrentClusterStatsHandler,
      init_kwargs={'source': ClusterProxiesStatsSource(),
                   'default_include_lists': DEFAULT_INCLUDE_LISTS}
    )
  else:
    # Stub handler for slave nodes
    cluster_stub_handler = HandlerInfo(
      handler_class=Respond404Handler,
      init_kwargs={'reason': 'Only master node provides cluster stats'}
    )
    cluster_node_stats_handler = cluster_stub_handler
    cluster_processes_stats_handler = cluster_stub_handler
    cluster_proxies_stats_handler = cluster_stub_handler

  routes = {
    '/stats/cluster/nodes': cluster_node_stats_handler,
    '/stats/cluster/processes': cluster_processes_stats_handler,
    '/stats/cluster/proxies': cluster_proxies_stats_handler,
  }
  return [
    (route, handler.handler_class, handler.init_kwargs)
    for route, handler in routes.iteritems()
  ]


def _configure_profiling(stats_source, profiler, interval):

  def write_stats_callback(future_stats):
    """ Gets stats from already finished future wrapper
    and calls profiler to write the stats.

    Args:
      future_stats: a Future wrapper for the cluster stats
    """
    stats = future_stats.result()
    profiler.write(stats)

  def profiling_periodical_callback():
    """ Triggers asynchronous stats collection and schedules writing
    of the cluster stats (when it's collected) to the stats profile.
    """
    newer_than = time.mktime(datetime.utcnow().timetuple())
    future_stats = stats_source.get_current_async(newer_than=newer_than)
    IOLoop.current().add_future(future_stats, write_stats_callback)

  PeriodicCallback(profiling_periodical_callback, interval).start()


def configure_node_stats_profiling():
  """ Configures and starts periodical callback for collecting and than
  writing cluster stats to profile log.
  """
  _configure_profiling(
    stats_source=ClusterNodesStatsSource(),
    profiler=profile.NodesProfileLog(DEFAULT_INCLUDE_LISTS),
    interval=PROFILE_NODES_STATS_INTERVAL
  )


def configure_processes_stats_profiling(write_detailed_stats):
  """ Configures and starts periodical callback for collecting and than
  writing cluster stats to profile log.

  Args:
    write_detailed_stats: a boolean indicating whether detailed stats
      should be written.
  """
  _configure_profiling(
    stats_source=ClusterProcessesStatsSource(),
    profiler= profile.ProcessesProfileLog(
      include_lists=DEFAULT_INCLUDE_LISTS,
      write_detailed_stats=write_detailed_stats),
    interval=PROFILE_PROCESSES_STATS_INTERVAL
  )


def configure_proxies_stats_profiling(write_detailed_stats):
  """ Configures and starts periodical callback for collecting and than
  writing cluster stats to profile log.

  Args:
    write_detailed_stats: a boolean indicating whether detailed stats
      should be written.
  """
  _configure_profiling(
    stats_source=ClusterProxiesStatsSource(),
    profiler= profile.ProxiesProfileLog(
      include_lists=DEFAULT_INCLUDE_LISTS,
      write_detailed_stats=write_detailed_stats),
    interval=PROFILE_PROXIES_STATS_INTERVAL
  )
