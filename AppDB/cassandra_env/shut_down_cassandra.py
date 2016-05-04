""" A test script to shut down Cassandra. """
import logging
import os
import sys

import cassandra_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import monit_interface

def run():
  """ Shuts down Cassandra. """
  logging.warning("Stopping Cassandra.")
  monit_interface.stop(
    cassandra_interface.CASSANDRA_MONIT_WATCH_NAME, is_group=False)
  logging.warning("Done!")

  return True

if __name__ == "__main__":
  run()
