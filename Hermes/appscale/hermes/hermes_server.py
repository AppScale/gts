""" Web server providing different metrics of AppScale
nodes, processes and services. """

import argparse
import logging

from aiohttp import web

from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT

from appscale.hermes import constants
from appscale.hermes.handlers import (
  verify_secret_middleware, LocalStatsHandler, ClusterStatsHandler, not_found
)
from appscale.hermes.producers.cluster_stats import (
  cluster_nodes_stats, cluster_processes_stats, cluster_proxies_stats,
  cluster_rabbitmq_stats, cluster_push_queues_stats, cluster_taskqueue_stats,
  cluster_cassandra_stats
)
from appscale.hermes.producers.cassandra_stats import CassandraStatsSource
from appscale.hermes.producers.node_stats import NodeStatsSource
from appscale.hermes.producers.process_stats import ProcessesStatsSource
from appscale.hermes.producers.proxy_stats import ProxiesStatsSource
from appscale.hermes.producers.rabbitmq_stats import PushQueueStatsSource
from appscale.hermes.producers.rabbitmq_stats import RabbitMQStatsSource
from appscale.hermes.producers.taskqueue_stats import TaskqueueStatsSource

logger = logging.getLogger(__name__)


def get_local_stats_api_routes(is_lb_node, is_tq_node, is_db_node):
  """ Creates stats sources and API handlers for providing local stats.
  Routes which are not applicable for node role are stubbed with
  404 handler.

  Args:
    is_lb_node: A boolean indicating whether this node is load balancer.
    is_tq_node: A boolean indicating whether this node runs taskqueue service.
    is_db_node: A boolean indicating whether this node runs cassandra service.
  Returns:
    A list of route-handler tuples.
  """

  # Any node provides its node and processes stats
  node_stats_handler = LocalStatsHandler(NodeStatsSource)
  processes_stats_handler = LocalStatsHandler(ProcessesStatsSource)
  if is_lb_node:
    # Only LB nodes provide proxies and service stats
    proxies_stats_handler = LocalStatsHandler(ProxiesStatsSource)
    tq_stats_handler = LocalStatsHandler(TaskqueueStatsSource())
  else:
    # Stub handler for non-LB nodes
    proxies_stats_handler = not_found('Only LB nodes provides proxies stats')
    tq_stats_handler = not_found('Only LB nodes provide TQ service stats')

  if is_tq_node:
    # Only TQ nodes provide RabbitMQ stats.
    rabbitmq_stats_handler = LocalStatsHandler(RabbitMQStatsSource)
    push_queue_stats_handler = LocalStatsHandler(PushQueueStatsSource)
  else:
    # Stub handler for non-TQ nodes
    rabbitmq_stats_handler = not_found('Only TQ nodes provide RabbitMQ stats')
    push_queue_stats_handler = not_found('Only TQ nodes provide queue stats')

  if is_db_node:
    # Only DB nodes provide Cassandra stats.
    cassandra_stats_handler = LocalStatsHandler(CassandraStatsSource)
  else:
    # Stub handler for non-DB nodes
    cassandra_stats_handler = not_found('Only DB nodes provide Cassandra stats')

  return [
    ('/stats/local/node', node_stats_handler),
    ('/stats/local/processes', processes_stats_handler),
    ('/stats/local/proxies', proxies_stats_handler),
    ('/stats/local/rabbitmq', rabbitmq_stats_handler),
    ('/stats/local/push_queues', push_queue_stats_handler),
    ('/stats/local/taskqueue', tq_stats_handler),
    ('/stats/local/cassandra', cassandra_stats_handler),
  ]


def get_cluster_stats_api_routes(is_lb):
  """ Creates stats sources and API handlers for providing cluster nodes.
  If this node is not Load balancer,
  it creates stub handlers for cluster stats routes.

  Args:
    is_lb: A boolean indicating whether this node is load balancer.
  Returns:
    A list of route-handler tuples.
  """
  if is_lb:
    # Only LB nodes provide cluster stats
    node_stats_handler = ClusterStatsHandler(cluster_nodes_stats)
    processes_stats_handler = ClusterStatsHandler(cluster_processes_stats)
    proxies_stats_handler = ClusterStatsHandler(cluster_proxies_stats)
    taskqueue_stats_handler = ClusterStatsHandler(cluster_taskqueue_stats)
    rabbitmq_stats_handler = ClusterStatsHandler(cluster_rabbitmq_stats)
    push_queue_stats_handler = ClusterStatsHandler(cluster_push_queues_stats)
    cassandra_stats_handler = ClusterStatsHandler(cluster_cassandra_stats)
  else:
    # Stub handler for slave nodes
    cluster_stub_handler = not_found('Only LB nodes provide cluster stats')
    node_stats_handler = cluster_stub_handler
    processes_stats_handler = cluster_stub_handler
    proxies_stats_handler = cluster_stub_handler
    taskqueue_stats_handler = cluster_stub_handler
    rabbitmq_stats_handler = cluster_stub_handler
    push_queue_stats_handler = cluster_stub_handler
    cassandra_stats_handler = cluster_stub_handler

  return [
    ('/stats/cluster/nodes', node_stats_handler),
    ('/stats/cluster/processes', processes_stats_handler),
    ('/stats/cluster/proxies', proxies_stats_handler),
    ('/stats/cluster/taskqueue', taskqueue_stats_handler),
    ('/stats/cluster/rabbitmq', rabbitmq_stats_handler),
    ('/stats/cluster/push_queues', push_queue_stats_handler),
    ('/stats/cluster/cassandra', cassandra_stats_handler),
  ]


def main():
  """ Main. """
  parser = argparse.ArgumentParser()
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Output debug-level logging')
  parser.add_argument('--port', type=int, default=constants.HERMES_PORT,
                      help='The port to listen on')
  args = parser.parse_args()

  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  my_ip = appscale_info.get_private_ip()
  is_master = (my_ip == appscale_info.get_headnode_ip())
  is_lb = (my_ip in appscale_info.get_load_balancer_ips())
  is_tq = (my_ip in appscale_info.get_taskqueue_nodes())
  is_db = (my_ip in appscale_info.get_db_ips())

  app = web.Application(middlewares=[verify_secret_middleware])

  route_items = []
  route_items += get_local_stats_api_routes(is_lb, is_tq, is_db)
  route_items += get_cluster_stats_api_routes(is_master)
  for route, handler in route_items:
    app.router.add_get(route, handler)

  logger.info("Starting Hermes on port: {}.".format(args.port))
  web.run_app(app, port=args.port, access_log=logger,
              access_log_format='%a "%r" %s %bB %Tfs "%{User-Agent}i"')
