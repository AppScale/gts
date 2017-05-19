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


# This constant can be defined when all stat models and
# converter.IncludeLists are imported. So it can't be in constants module
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
  """
  This class holds logic related to start of stats profiling and API endpoints.

  There are 6 possible kinds of stats:
   - local node stats (cpu, memory, disk, ...);
   - local processes stats (cpu, memory, ... per monitored process);
   - local proxies stats (haproxy stats collected from local haproxy socket);
   - cluster node stats (dict[node_ip, local_node_stats]);
   - cluster processes stats (dict[node_ip, local_processes_stats]);
   - cluster proxies stats (dict[node_ip, local_proxies_stats]);

  Statistics works differently on master node, load balancer node and other
  regular nodes.

  Additionally to that stats supports different levels of severity:
   - csv profile log can be written optionally;
   - default set of stats fields can be configured;
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
    """ Is called when cluster stats were collected and are ready to be written
    """
    stats = future_stats.result()
    profiler.write(stats)

  def profiling_periodical_callback():
    """ Is called periodically to trigger stats collection from cluster
    """
    newer_than = time.mktime(datetime.utcnow().timetuple())
    future_stats = stats_source.get_current_async(newer_than=newer_than)
    IOLoop.current().add_future(future_stats, write_stats_callback)

  PeriodicCallback(profiling_periodical_callback, interval).start()


def configure_node_stats_profiling():
  """ Configure and start periodical callback for collecting and than
  writing cluster stats to profile log.
  """
  _configure_profiling(
    stats_source=ClusterNodesStatsSource(),
    profiler=profile.NodesProfileLog(),
    interval=PROFILE_NODES_STATS_INTERVAL
  )


def configure_processes_stats_profiling(write_detailed_stats):
  """ Configure and start periodical callback for collecting and than
  writing cluster stats to profile log.
  """
  _configure_profiling(
    stats_source=ClusterProcessesStatsSource(),
    profiler= profile.ProcessesProfileLog(
      write_detailed_stats=write_detailed_stats),
    interval=PROFILE_PROCESSES_STATS_INTERVAL
  )


def configure_proxies_stats_profiling(write_detailed_stats):
  """ Configure and start periodical callback for collecting and than
  writing cluster stats to profile log.
  """
  _configure_profiling(
    stats_source=ClusterProxiesStatsSource(),
    profiler= profile.ProxiesProfileLog(
      write_detailed_stats=write_detailed_stats),
    interval=PROFILE_PROXIES_STATS_INTERVAL
  )
