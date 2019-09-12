""" Provides a service which periodically runs the groomer. """
import logging

from kazoo.client import KazooClient, KazooRetry

from appscale.common import appscale_info
from appscale.common.constants import DB_SERVER_PORT
from appscale.common.constants import LOG_FORMAT
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS
from .. import groomer
from ..zkappscale import zktransaction as zk


def main():
  logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
  logger = logging.getLogger(__name__)
  zookeeper_locations = appscale_info.get_zk_locations_string()
  retry_policy = KazooRetry(max_tries=5)
  zk_client = KazooClient(
    zookeeper_locations, connection_retry=ZK_PERSISTENT_RECONNECTS,
    command_retry=retry_policy)
  zk_client.start()
  gc_zookeeper = zk.ZKTransaction(zk_client)
  logger.info("Using ZK locations {0}".format(zookeeper_locations))

  datastore_location = ':'.join([appscale_info.get_db_proxy(),
                                 str(DB_SERVER_PORT)])
  ds_groomer = groomer.DatastoreGroomer(gc_zookeeper, "cassandra",
                                        datastore_location)
  try:
    ds_groomer.start()
  except Exception, exception:
    logger.warning("An exception slipped through:")
    logger.exception(exception)
    logger.warning("Exiting service.")
