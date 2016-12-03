""" Provides a service which periodically runs the groomer. """
import logging
import sys

from .. import groomer
from ..unpackaged import APPSCALE_LIB_DIR
from ..zkappscale import zktransaction as zk

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info
from constants import LOG_FORMAT

# Location to find the datastore service.
LOCAL_DATASTORE = "localhost:8888"


def main():
  logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
  logger = logging.getLogger(__name__)
  zookeeper_locations = appscale_info.get_zk_locations_string()
  gc_zookeeper = zk.ZKTransaction(host=zookeeper_locations, start_gc=False)
  logger.info("Using ZK locations {0}".format(zookeeper_locations))
  ds_groomer = groomer.DatastoreGroomer(gc_zookeeper, "cassandra", LOCAL_DATASTORE)
  try:
    ds_groomer.start()
  except Exception, exception:
    logger.warning("An exception slipped through:")
    logger.exception(exception)
    logger.warning("Exiting service.")
