""" Web server providing different metrics of AppScale
nodes, processes and services. """

import argparse
import logging
import signal

import tornado.escape
import tornado.httpclient
import tornado.web
from appscale.common import appscale_info
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from kazoo.client import KazooClient
from tornado.ioloop import IOLoop
from tornado.options import options

from appscale.hermes import constants
from appscale.hermes import stats_app


# A KazooClient for detecting configuration changes.
zk_client = None


def signal_handler(signal, frame):
  """ Signal handler for graceful shutdown. """
  logging.warning("Caught signal: {0}".format(signal))
  zk_client.stop()
  IOLoop.instance().add_callback(shutdown)


def shutdown():
  """ Shuts down the server. """
  logging.warning("Hermes is shutting down.")
  IOLoop.instance().stop()


def main():
  """ Main. """
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  args = parser.parse_args()

  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  options.define('secret', appscale_info.get_secret())

  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  my_ip = appscale_info.get_private_ip()
  is_master = (my_ip == appscale_info.get_headnode_ip())
  is_lb = (my_ip in appscale_info.get_load_balancer_ips())
  is_tq = (my_ip in appscale_info.get_taskqueue_nodes())

  if is_master:
    global zk_client
    zk_client = KazooClient(
      hosts=','.join(appscale_info.get_zk_node_ips()),
      connection_retry=ZK_PERSISTENT_RECONNECTS)
    zk_client.start()
    # Start watching profiling configs in ZooKeeper
    stats_app.ProfilingManager(zk_client)

  app = tornado.web.Application(
    stats_app.get_local_stats_api_routes(is_lb, is_tq)
    + stats_app.get_cluster_stats_api_routes(is_master),
    debug=False
  )
  app.listen(constants.HERMES_PORT)

  # Start loop for accepting http requests.
  IOLoop.instance().start()

  logging.info("Hermes is up and listening on port: {}."
               .format(constants.HERMES_PORT))

if __name__ == '__main__':
  main()
