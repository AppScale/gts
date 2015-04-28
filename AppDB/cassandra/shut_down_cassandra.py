""" A test script to shut down cassandra. """
import logging
import os
import sys

import cassandra_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import monit_interface

def run():
  """ Shuts down cassandra. """
  logging.warning("Stopping Cassandra")
  monit_interface.stop(cassandra_interface.CASSANDRA_MONIT_WATCH_NAME, is_group=False)
  logging.warning("Done!")

if __name__ == "__main__":
  run()
