# Programmer: Navraj Chohan
import logging
import os 
import subprocess
import sys

import file_io

""" 
This file contains top level functions for starting and stopping 
monitoring of processes using the God framework. Each component is in
charge of creating their own configuration file when starting up a new
process.
"""

def start(config_loc, watch):
  """  Starts a watch on God given a configuration file. Deletes
  the configuration after it is used. 

  Args:
    config_loc: The location of the God configuration file
    watch: Name of the watch being started
  Returns:
    True on success, False otherwise
  """
  return_status = subprocess.call(['god', 'load', config_loc])
  if return_status != 0:
    logging.error("God load command returned with status %d when setting " \
                  "up watch %s"%(return_status, watch))
    return False

  return_status = subprocess.call(['god', 'start', watch])
  if return_status != 0:
    logging.error("God load command returned with status %d when setting " \
                  "up watch %s"%(return_status, watch))
    return False

  logging.info("Starting watch %s"%(watch))

  file_io.delete(config_loc)
   
  return True

def stop(watch):
  """ Stop a watch on God. 
 
  Args:
    watch: The God tag identifier which will be stopped 
  Returns:
    True on success, False otherwise.
  """

  return_status = subprocess.call(['god', 'stop', watch])
  if return_status != 0:
    logging.error("God stop command returned with status %d when stopping \
                  watch %s"%(return_status, watch))
    return False
  return True
