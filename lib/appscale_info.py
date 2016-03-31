""" 
This file contains functions for getting and setting information related 
to AppScale and the current node/machine.
"""
import json
import logging
import multiprocessing
import os
import sys
import yaml

import constants
import file_io

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppServer'))
from google.appengine.api.appcontroller_client import AppControllerClient

def read_file_contents(path):
  """ Reads the contents of the given file.

  Returns:
    A str, the contents of the given file.
  """
  with open(path) as file_handle:
    return file_handle.read()

def get_appcontroller_client():
  """ Returns an AppControllerClient instance for this deployment. """
  head_node_ip_file = '/etc/appscale/head_node_ip'
  head_node = read_file_contents(head_node_ip_file).rstrip('\n')

  secret_file = '/etc/appscale/secret.key'
  secret = read_file_contents(secret_file)

  return AppControllerClient(head_node, secret)

def get_keyname():
  """ Returns the keyname for this deployment. """
  return get_db_info()[':keyname']

def get_all_ips():
  """ Get the IPs for all deployment nodes.

  Returns:
    A list of node IPs.
  """
  nodes = file_io.read(constants.ALL_IPS_LOC)
  nodes = nodes.split('\n')
  return filter(None, nodes)

def get_login_ip():
  """ Get the public IP of the head node.

  Returns:
    String containing the public IP of the head node.
  """
  return file_io.read(constants.LOGIN_IP_LOC).rstrip()

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
    A string containing one or more host:port listings, separated by commas. 
    None is returned if there was a problem getting the location string.
  """
  try:
    info = file_io.read(constants.ZK_LOCATIONS_JSON_FILE) 
    zk_json = json.loads(info) 
    return ":2181,".join(zk_json['locations']) + ":2181"
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

def get_zk_node_ips():
  """ Returns a list of zookeeper node IPs.

  Returns:
    A list containing the hosts that run zookeeper roles in the current
    AppScale deployment.
  """
  try:
    info = file_io.read(constants.ZK_LOCATIONS_JSON_FILE)
    zk_json = json.loads(info)
    return zk_json['locations']
  except IOError, io_error:
    logging.exception(io_error)
    return []
  except ValueError, value_error:
    logging.exception(value_error)
    return []
  except TypeError, type_error:
    logging.exception(type_error)
    return []
  except KeyError, key_error:
    logging.exception(key_error)
    return []

def get_db_master_ip():
  """ Returns the master datastore IP.

  Returns:
    A str, the IP of the datastore master.
  """
  return file_io.read(constants.MASTERS_FILE_LOC).rstrip()

def get_db_slave_ips():
  """ Returns the slave datastore IPs.

  Returns:
    A list of IP of the datastore slaves.
  """
  nodes = file_io.read(constants.SLAVES_FILE_LOC).rstrip()
  nodes = nodes.split('\n')
  if nodes[-1] == '':
    nodes = nodes[:-1]
  return nodes

def get_db_ips():
  """ Returns a list of database machines.

  Returns:
    A list of strings containing IP addresses.
  """
  return list(set([get_db_master_ip()] + get_db_slave_ips()))

def get_search_location():
  """ Returns the IP and port of where the search service is running.

  Returns:
    A str, the IP and port in the format: IP:PORT. Empty string if the service
    is not available.
  """
  try:
    return file_io.read(constants.SEARCH_FILE_LOC).rstrip()
  except IOError:
    logging.warning("Search role is not configured.")
    return ""
