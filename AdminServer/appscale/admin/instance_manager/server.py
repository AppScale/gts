""" This service starts and stops application servers of a given application. """

import logging
import tornado.web
from concurrent.futures import ThreadPoolExecutor
from kazoo.client import KazooClient
from tornado import gen
from tornado.escape import json_decode
from tornado.httpclient import HTTPError
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import options

from appscale.admin.instance_manager import InstanceManager
from appscale.admin.instance_manager.constants import (
  BadConfigurationException,
  INSTANCE_CLEANUP_INTERVAL,
  MAX_BACKGROUND_WORKERS
)
from appscale.admin.instance_manager.projects_manager import (
  GlobalProjectsManager)
from appscale.admin.instance_manager.routing_client import RoutingClient
from appscale.admin.instance_manager.source_manager import SourceManager
from appscale.common import (
  appscale_info,
  constants,
  file_io
)
from appscale.common.constants import HTTPCodes
from appscale.common.deployment_config import DeploymentConfig
from appscale.common.monit_interface import MonitOperator


class VersionHandler(tornado.web.RequestHandler):
  """ Handles requests to start and stop instances for a project. """
  def initialize(self, instance_manager):
    self._instance_manager = instance_manager

  @gen.coroutine
  def post(self, version_key):
    """ Starts an AppServer instance on this machine.

    Args:
      version_key: A string specifying a version key.
    """
    try:
      config = json_decode(self.request.body)
    except ValueError:
      raise HTTPError(HTTPCodes.BAD_REQUEST, 'Payload must be valid JSON')

    try:
      yield self._instance_manager.start_app(version_key, config)
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)

  @gen.coroutine
  def delete(self, version_key):
    """ Stops all instances on this machine for a version.

    Args:
      version_key: A string specifying a version key.
    """
    try:
      yield self._instance_manager.stop_app(version_key)
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)


class InstanceHandler(tornado.web.RequestHandler):
  """ Handles requests to stop individual instances. """
  def initialize(self, instance_manager):
    self._instance_manager = instance_manager

  @gen.coroutine
  def delete(self, version_key, port):
    """ Stops an AppServer instance on this machine. """
    try:
      yield self._instance_manager.stop_app_instance(version_key, int(port))
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)


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
  monit_operator = MonitOperator()

  options.define('private_ip', appscale_info.get_private_ip())
  options.define('syslog_server', appscale_info.get_headnode_ip())
  options.define('db_proxy', appscale_info.get_db_proxy())
  options.define('tq_proxy', appscale_info.get_tq_proxy())
  options.define('secret', appscale_info.get_secret())

  routing_client = RoutingClient(zk_client, options.private_ip, options.secret)
  instance_manager = InstanceManager(
    zk_client, monit_operator, routing_client, projects_manager,
    deployment_config, source_manager, options.syslog_server, thread_pool,
    options.private_ip)
  instance_manager.start()
  PeriodicCallback(instance_manager.stop_failed_instances,
                   INSTANCE_CLEANUP_INTERVAL * 1000).start()

  app = tornado.web.Application([
    ('/versions/([a-z0-9-_]+)', VersionHandler,
     {'instance_manager': instance_manager}),
    ('/versions/([a-z0-9-_]+)/([0-9-]+)', InstanceHandler,
     {'instance_manager': instance_manager})
  ])

  app.listen(constants.APP_MANAGER_PORT)
  logging.info('Starting AppManager on {}'.format(constants.APP_MANAGER_PORT))

  io_loop = IOLoop.current()
  io_loop.run_sync(instance_manager.populate_api_servers)
  io_loop.start()
