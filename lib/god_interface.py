# Programmer: Navraj Chohan <nlake44@gmail.com>
import logging
import os 
import subprocess
import sys

import file_io
import misc 

""" 
This file contains top level functions for starting and stopping 
monitoring of processes using the god framework. Each component is in
charge of creating configuration files for the process they want started. 
"""

def start(config_loc, watch):
  """  Starts a watch on god given a configuration file. Deletes
       the configuration after it is used. 

  Args:
    config_loc: The location of the god configuration file
    watch: Name of the watch being started
  Returns:
    True on success, False otherwise
  """
  if not misc.is_string_secure(config_loc):
    logging.error("Configuration file location str (%s) is a possible security violation"%config_loc)
    return False

  if not misc.is_string_secure(watch):
    logging.error("Watch string (%s) is a possible security violation"%watch)
    return False

  return_status = subprocess.call(['god', 'load', config_loc])
  if return_status != 0:
    logging.error("God load command returned with status %d when setting up watch %s"%(int(return_status), str(watch)))
    return False

  return_status = subprocess.call(['god', 'start', watch])
  if return_status != 0:
    logging.error("God load command returned with status %d when setting up watch %s"%(return_status, watch))
    return False

  logging.info("Starting watch %s"%str(watch))

  file_io.delete(config_loc)
   
  return True

def stop(watch):
  """ Stop a watch on god. 
 
  Args:
    watch: The god tag identifier 
  Returns:
    True on success, False otherwise.
  """
  if not misc.is_string_secure(watch):
    logging.error("Watch string (%s) is a possible security violation"%watch)
    return False
  
  return_status = subprocess.call(['god', 'stop', watch])
  if return_status != 0:
    print return_status
    print watch
    logging.error("God stop command returned with status %d when stopping watch %s"%(return_status, watch))
    return False

  return_status = subprocess.call(['god', 'remove', watch])
  if return_status != 0:
    logging.error("God remove command returned with status %d when removing watch %s"%(return_status, watch)) 
    return False

  return True
