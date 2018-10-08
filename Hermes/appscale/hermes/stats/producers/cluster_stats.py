""" Implementation of stats sources for cluster stats. """
import json
import logging
import sys
import time

import random
import socket

from appscale.common import appscale_info
from tornado import gen, httpclient
from tornado.options import options
from tornado.simple_httpclient import SimpleAsyncHTTPClient

from appscale.hermes import constants
from appscale.hermes.constants import SECRET_HEADER
from appscale.hermes.stats import converter
from appscale.hermes.stats.constants import STATS_REQUEST_TIMEOUT
from appscale.hermes.stats.producers import (
  proxy_stats, node_stats, process_stats, rabbitmq_stats,
  taskqueue_stats, cassandra_stats
)

# Allow tornado to fetch up to 100 concurrent requests
httpclient.AsyncHTTPClient.configure(SimpleAsyncHTTPClient, max_clients=100)


class BadStatsListFormat(ValueError):
  """ Is used when Hermes slave responds with improperly formatted stats. """
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

  @gen.coroutine
  def get_current(self, max_age=None, include_lists=None,
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

    # Do multiple requests asynchronously and wait for all results
    stats_or_error_per_node = yield {
      node_ip: self._stats_from_node_async(node_ip, max_age, include_lists)
      for node_ip in self.ips_getter() if node_ip not in exclude_nodes
    }
    stats_per_node = {
      ip: snapshot_or_err
      for ip, snapshot_or_err in stats_or_error_per_node.iteritems()
      if not isinstance(snapshot_or_err, (str, unicode))
    }
    failures = {
      ip: snapshot_or_err
      for ip, snapshot_or_err in stats_or_error_per_node.iteritems()
      if isinstance(snapshot_or_err, (str, unicode))
    }
    logging.info("Fetched {stats} from {nodes} nodes in {elapsed:.1f}s."
                 .format(stats=self.stats_model.__name__,
                         nodes=len(stats_per_node),
                         elapsed=time.time() - start))
    raise gen.Return((stats_per_node, failures))

  @gen.coroutine
  def _stats_from_node_async(self, node_ip, max_age, include_lists):
    if node_ip == appscale_info.get_private_ip():
      try:
        snapshot = self.local_stats_source.get_current()
        if isinstance(snapshot, gen.Future):
          snapshot = yield snapshot
      except Exception as err:
        snapshot = unicode(err)
        logging.exception(
          u"Failed to prepare local stats: {err}".format(err=err))
    else:
      snapshot = yield self._fetch_remote_stats_async(
        node_ip, max_age, include_lists)
    raise gen.Return(snapshot)

  @gen.coroutine
  def _fetch_remote_stats_async(self, node_ip, max_age, include_lists):
    # Security header
    headers = {SECRET_HEADER: options.secret}
    # Build query arguments
    arguments = {}
    if include_lists is not None:
      arguments['include_lists'] = include_lists.asdict()
    if max_age is not None:
      arguments['max_age'] = max_age

    url = "http://{ip}:{port}/{path}".format(
      ip=node_ip, port=constants.HERMES_PORT, path=self.method_path)
    request = httpclient.HTTPRequest(
      url=url, method='GET', body=json.dumps(arguments), headers=headers,
      request_timeout=STATS_REQUEST_TIMEOUT, allow_nonstandard_methods=True
    )
    async_client = httpclient.AsyncHTTPClient()

    try:
      # Send Future object to coroutine and suspend till result is ready
      response = yield async_client.fetch(request)
    except (socket.error, httpclient.HTTPError) as err:
      msg = u"Failed to get stats from {url} ({err})".format(url=url, err=err)
      if hasattr(err, 'response') and err.response and err.response.body:
        msg += u"\nBODY: {body}".format(body=err.response.body)
      logging.error(msg)
      raise gen.Return(unicode(err))

    try:
      snapshot = json.loads(response.body)
      raise gen.Return(converter.stats_from_dict(self.stats_model, snapshot))
    except TypeError as err:
      msg = u"Can't parse stats snapshot ({})".format(err)
      raise BadStatsListFormat(msg), None, sys.exc_info()[2]


def get_random_lb_node():
  return [random.choice(appscale_info.get_load_balancer_ips())]


def get_random_db_node():
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
