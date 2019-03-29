""" Implementation of stats sources for cluster stats. """
import asyncio
import inspect
import logging
import time
import random

import aiohttp

from appscale.common import appscale_info
from appscale.hermes import constants, converter
from appscale.hermes.producers import (
  proxy_stats, node_stats, process_stats, rabbitmq_stats,
  taskqueue_stats, cassandra_stats
)

logger = logging.getLogger(__name__)

max_concurrency = asyncio.Semaphore(100)


class RemoteHermesError(aiohttp.ClientError):
  """ Represents an error while getting stats from remote Hermes. """
  pass


class ClusterStatsSource(object):
  """
  Cluster stats sources.
  Gets new local stats from all nodes in the cluster.
  """
  def __init__(self, ips_getter, method_path, stats_model, local_stats_source):
    self.ips_getter = ips_getter
    self.method_path = method_path
    self.stats_model = stats_model
    self.local_stats_source = local_stats_source

  async def get_current(self, max_age=None, include_lists=None,
                        exclude_nodes=None):
    """ Makes concurrent asynchronous http calls to cluster nodes
    and collects current stats. Local stats is got from local stats source.

    Args:
      max_age: UTC timestamp, allow to use cached snapshot if it's newer.
      include_lists: An instance of IncludeLists.
      exclude_nodes: A list of node IPs to ignore when fetching stats.
    Returns:
      A Future object which wraps a dict with node IP as key and
      an instance of stats snapshot as value.
    """
    exclude_nodes = exclude_nodes or []
    start = time.time()

    stats_per_node = {}
    failures = {}

    # Do multiple requests asynchronously and wait for all results
    async def get_remote_result(node_ip):
      try:
        stats_per_node[node_ip] = await self._stats_from_node_async(
          node_ip, max_age, include_lists
        )
      except RemoteHermesError as err:
        failures[node_ip] = str(err)

    async with max_concurrency:
      await asyncio.wait([
        get_remote_result(node_ip)
        for node_ip in self.ips_getter() if node_ip not in exclude_nodes
      ])

    logger.info("Fetched {stats} from {nodes} nodes in {elapsed:.2f}s."
                .format(stats=self.stats_model.__name__,
                        nodes=len(stats_per_node),
                        elapsed=time.time()-start))
    return stats_per_node, failures

  async def _stats_from_node_async(self, node_ip, max_age, include_lists):
    if node_ip == appscale_info.get_private_ip():
      try:
        snapshot = self.local_stats_source.get_current()
        if inspect.isawaitable(snapshot):
          snapshot = await snapshot
        return snapshot
      except Exception as err:
        logger.error("Failed to prepare local stats: {err}".format(err=err))
        raise RemoteHermesError(str(err))
    else:
      snapshot = await self._fetch_remote_stats_async(
        node_ip, max_age, include_lists
      )
    return snapshot

  async def _fetch_remote_stats_async(self, node_ip, max_age, include_lists):
    # Security header
    headers = {constants.SECRET_HEADER: appscale_info.get_secret()}
    # Build query arguments
    arguments = {}
    if include_lists is not None:
      arguments['include_lists'] = include_lists.asdict()
    if max_age is not None:
      arguments['max_age'] = max_age

    url = "http://{ip}:{port}/{path}".format(
      ip=node_ip, port=constants.HERMES_PORT, path=self.method_path)

    try:
      async with aiohttp.ClientSession() as session:
        awaitable_get = session.get(
          url, headers=headers, json=arguments,
          timeout=constants.REMOTE_REQUEST_TIMEOUT
        )
        async with awaitable_get as resp:
          if resp.status >= 400:
            resp_text = await resp.text()
            err_message = resp_text or resp.reason
            logger.error("Failed to get {} ({})".format(url, err_message))
            raise RemoteHermesError(err_message)
          snapshot = await resp.json()
          return converter.stats_from_dict(self.stats_model, snapshot)

    except aiohttp.ClientError as err:
      logger.error("Failed to get {} ({})".format(url, err))
      raise RemoteHermesError(str(err))


async def get_random_lb_node():
  return [random.choice(appscale_info.get_load_balancer_ips())]


async def get_random_db_node():
  return [random.choice(appscale_info.get_db_ips())]


cluster_nodes_stats = ClusterStatsSource(
  ips_getter=appscale_info.get_all_ips,
  method_path='stats/local/node',
  stats_model=node_stats.NodeStatsSnapshot,
  local_stats_source=node_stats.NodeStatsSource
)

cluster_processes_stats = ClusterStatsSource(
  ips_getter=appscale_info.get_all_ips,
  method_path='stats/local/processes',
  stats_model=process_stats.ProcessesStatsSnapshot,
  local_stats_source=process_stats.ProcessesStatsSource
)

cluster_proxies_stats = ClusterStatsSource(
  ips_getter=appscale_info.get_load_balancer_ips,
  method_path='stats/local/proxies',
  stats_model=proxy_stats.ProxiesStatsSnapshot,
  local_stats_source=proxy_stats.ProxiesStatsSource
)

cluster_taskqueue_stats = ClusterStatsSource(
  ips_getter=get_random_lb_node,
  method_path='stats/local/taskqueue',
  stats_model=taskqueue_stats.TaskqueueServiceStatsSnapshot,
  local_stats_source=taskqueue_stats.taskqueue_stats_source
)

cluster_rabbitmq_stats = ClusterStatsSource(
  ips_getter=appscale_info.get_taskqueue_nodes,
  method_path='stats/local/rabbitmq',
  stats_model=rabbitmq_stats.RabbitMQStatsSnapshot,
  local_stats_source=rabbitmq_stats.RabbitMQStatsSource
)

cluster_push_queues_stats = ClusterStatsSource(
  ips_getter=lambda: [appscale_info.get_taskqueue_nodes()[0]],
  method_path='stats/local/push_queues',
  stats_model=rabbitmq_stats.PushQueueStatsSnapshot,
  local_stats_source=rabbitmq_stats.PushQueueStatsSource
)

cluster_cassandra_stats = ClusterStatsSource(
  ips_getter=get_random_db_node,
  method_path='stats/local/cassandra',
  stats_model=cassandra_stats.CassandraStatsSnapshot,
  local_stats_source=cassandra_stats.CassandraStatsSource
)
