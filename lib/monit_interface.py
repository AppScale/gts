# Programmer: Navraj Chohan <nlake44@gmail.com>
import logging
import os 
import subprocess
import sys

import file_io
import misc 

""" 
This file contains top level functions for starting and stopping 
monitoring of processes using monit. Each component is in
charge of creating configuration files for the process they want started. 
"""

def start(watch):
  """ Starts a watch on monit given a configuration file.

  Args:
    watch: Name of the watch being started
  Returns:
    True on success, False otherwise
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string (%s) is a possible security violation" % watch)
    return False

  return_status = subprocess.call(['monit', 'start', '-g', watch])
  if return_status != 0:
    logging.error("Monit start command returned with status %d when setting " \
      "up watch %s" % (return_status, watch))
    return False

  logging.info("Starting watch %s" % str(watch))

  return True

def stop(watch):
  """ Stop a watch on monit. 
 
  Args:
    watch: The name of the watch being stopped.
  Returns:
    True on success, False otherwise.
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string (%s) is a possible security violation" % watch)
    return False
  
  return_status = subprocess.call(['monit', 'stop', '-g', watch])
  if return_status != 0:
    logging.error("Monit stop command returned with status %d when stopping " \
      "watch %s" % (return_status, watch))
    return False

  return_status = subprocess.call(['monit', 'unmonitor', '-g', watch])
  if return_status != 0:
    logging.error("Monit unmonitor command returned with status %d when " \
      "unmonitoring watch %s" % (return_status, watch)) 
    return False

  return True
