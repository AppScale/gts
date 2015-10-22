""" Provides a service which periodically runs the groomer. """
import logging
import os
import sys

import groomer

from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

# Location to find the datastore service.
LOCAL_DATASTORE = "localhost:8888"

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)
  zookeeper_locations = appscale_info.get_zk_locations_string()
  gc_zookeeper = zk.ZKTransaction(host=zookeeper_locations)
  logger.info("Using ZK locations {0}".format(zookeeper_locations))
  ds_groomer = groomer.DatastoreGroomer(gc_zookeeper, "cassandra", LOCAL_DATASTORE)
  try:
    ds_groomer.start()
  except Exception, exception:
    logger.warning("An exception slipped through:")
    logger.exception(exception)
    logger.warning("Exiting service.")
