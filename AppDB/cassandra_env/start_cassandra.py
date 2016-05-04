""" A test script to start Cassandra. """

import logging
import os
import sys

import cassandra_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import monit_interface

def run(): 
  """ Starts up cassandra. """ 
  logging.warning("Starting Cassandra.")
  monit_interface.start(cassandra_interface.CASSANDRA_MONIT_WATCH_NAME,
    is_group=False)
  logging.warning("Done!") 

if __name__ == '__main__':
  run()
