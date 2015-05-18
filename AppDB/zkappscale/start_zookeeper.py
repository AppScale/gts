""" A test script to start Zookeeper. """

import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import monit_interface

def run(): 
  """ Starts up cassandra. """ 
  logging.warning("Starting Zookeeper.")
  monit_interface.start('zookeeper-9999',
    is_group=False)
  logging.warning("Done!") 

if __name__ == '__main__':
  run()
