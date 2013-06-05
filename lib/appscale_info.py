# Programmer: Navraj Chohan <nlake44@gmail.com>
""" 
This file contains functions for getting and setting information related 
to AppScale and the current node/machine.
"""
import json
import logging
import multiprocessing
import yaml

import constants
import file_io

def get_private_ip():
  """ Get the private IP of the current machine.
  
  Returns:
    String containing the private IP of the current machine.
  """
  return file_io.read(constants.PRIVATE_IP_LOC).rstrip()

def get_public_ip():
  """ Get the public IP of the current machine.
  
  Returns:
    String containing the public IP of the current machine.
  """
  return file_io.read(constants.PUBLIC_IP_LOC).rstrip()

def get_secret():
  """ Get AppScale shared security key for authentication.
    
  Returns:
    String containing the secret key.
  """
  return file_io.read(constants.SECRET_LOC).rstrip()
 
def get_num_cpus():
  """ Get the number of CPU processes on the current machine.
  
  Returns:
    Integer of the number of CPUs on the current machine
  """
  return multiprocessing.cpu_count() 

def get_db_info():
  """ Get information on the database being used.
  
  Returns:
    A dictionary with database info
  """
  info = file_io.read(constants.DB_INFO_LOC) 
  return yaml.load(info) 

def get_taskqueue_nodes():
  """ Returns a list of all the taskqueue nodes (including the master). 
      Strips off any empty lines

  Returns:
    A list of taskqueue nodes.
  """
  nodes = file_io.read(constants.TASKQUEUE_NODE_FILE)
  nodes = nodes.split('\n')
  if nodes[-1] == '':
    nodes = nodes[:-1]
  return nodes

def get_app_path(app_id):
  """ Returns the application path.
  
  Args:
    app_id: The application id.
  Returns:
    A string of the full path of where the application is.
  """
  return constants.APPS_PATH + app_id + '/app/'

def get_zk_locations_string():
  """ Returns the ZooKeeper connection host string. 

  Returns:
    A string of one or more host:port listing separated by commas.listing separated by commas
    and None if there was an error with the file. 
  """
  try:
    info = file_io.read(constants.ZK_LOCATIONS_JSON_FILE) 
    zk_json = json.loads(info) 
    return ":2181".join(zk_json['locations']) + ":2181"
  except IOError, io_error:
    logging.exception(io_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except ValueError, value_error:
    logging.exception(value_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except TypeError, type_error:
    logging.exception(type_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except KeyError, key_error:
    logging.exception(key_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
