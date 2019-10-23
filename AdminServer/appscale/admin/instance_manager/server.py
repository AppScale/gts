""" This service starts and stops application servers of a given application. """

import logging
from concurrent.futures import ThreadPoolExecutor
from kazoo.client import KazooClient
from tornado.ioloop import IOLoop
from tornado.options import options

from appscale.admin.instance_manager import InstanceManager
from appscale.admin.instance_manager.constants import MAX_BACKGROUND_WORKERS
from appscale.admin.instance_manager.projects_manager import (
  GlobalProjectsManager)
from appscale.admin.instance_manager.routing_client import RoutingClient
from appscale.admin.instance_manager.source_manager import SourceManager
from appscale.common import appscale_info, file_io
from appscale.common.deployment_config import DeploymentConfig
from appscale.common.service_helper import ServiceOperator

logger = logging.getLogger(__name__)


def main():
  file_io.set_logging_format()
  logging.getLogger().setLevel(logging.INFO)

  zk_ips = appscale_info.get_zk_node_ips()
  zk_client = KazooClient(hosts=','.join(zk_ips))
  zk_client.start()

  deployment_config = DeploymentConfig(zk_client)
  projects_manager = GlobalProjectsManager(zk_client)
  thread_pool = ThreadPoolExecutor(MAX_BACKGROUND_WORKERS)
  source_manager = SourceManager(zk_client, thread_pool)
  source_manager.configure_automatic_fetch(projects_manager)
  service_operator = ServiceOperator(thread_pool)

  options.define('private_ip', appscale_info.get_private_ip())
  options.define('syslog_server', appscale_info.get_headnode_ip())
  options.define('db_proxy', appscale_info.get_db_proxy())
  options.define('load_balancer_ip', appscale_info.get_load_balancer_ips()[0])
  options.define('tq_proxy', appscale_info.get_tq_proxy())
  options.define('secret', appscale_info.get_secret())

  routing_client = RoutingClient(zk_client, options.private_ip, options.secret)
  instance_manager = InstanceManager(
    zk_client, service_operator, routing_client, projects_manager,
    deployment_config, source_manager, options.syslog_server, thread_pool,
    options.private_ip)
  instance_manager.start()

  logger.info('Starting AppManager')

  io_loop = IOLoop.current()
  io_loop.run_sync(instance_manager.populate_api_servers)
  io_loop.start()
