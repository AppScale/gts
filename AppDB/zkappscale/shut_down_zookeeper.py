""" A test script to shut down Zookeeper. """
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import monit_interface

def run():
  """ Shuts down Zookeeper. """
  logging.warning("Stopping Zookeeper.")
  monit_interface.stop('zookeeper-9999', is_group=False)
  logging.warning("Done!")

  return True

if __name__ == "__main__":
  run()
