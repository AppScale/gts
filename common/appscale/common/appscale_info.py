"""
This file contains functions for getting and setting information related
to AppScale and the current node/machine.
"""
import json
import logging
import multiprocessing
import yaml

from . import constants
from . import file_io

logger = logging.getLogger(__name__)


def read_file_contents(path):
  """ Reads the contents of the given file.

  Returns:
    A str, the contents of the given file.
  """
  with open(path) as file_handle:
    return file_handle.read()

def get_appcontroller_client():
  """ Returns an AppControllerClient instance for this deployment. """
  raw_ips = file_io.read('/etc/appscale/load_balancer_ips')
  ips = raw_ips.split('\n')
  head_node = ips[0]

  secret_file = '/etc/appscale/secret.key'
  secret = read_file_contents(secret_file)

  from appscale.appcontroller_client import AppControllerClient
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

def get_load_balancer_ips():
  """ Get the IPs for all load balancer nodes in the deployment.

  Returns:
    A list of LB node IPs.
  """
  with open(constants.LOAD_BALANCER_IPS_LOC) as lbs_file:
    return [line.strip() for line in lbs_file if line.strip()]

def get_headnode_ip():
  """ Get the private IP of the head node. NOTE: it can change if node
  crashes.

  Returns:
    String containing the private IP of the head node.
  """
  return file_io.read(constants.HEADNODE_IP_LOC).rstrip()

def get_login_ip():
  """ Get the public IP of the head node. NOTE: it can change if node
  crashes.

  Returns:
    String containing the public IP of the head node.
  """
  return file_io.read(constants.LOGIN_IP_LOC).rstrip()

def get_db_proxy():
  """ Get the IP of an active DB load balancer. Since there can be
  more than one for this deployment, we return the first one.

  Returns:
    String containing the IP of an active load balancer.
  """
  raw_ips = file_io.read(constants.LOAD_BALANCER_IPS_LOC)
  ips = raw_ips.split('\n')
  return ips[0]

def get_tq_proxy():
  """ Get the IP of an active TQ load balancer. Since there can be
  more than one for this deployment, we return the first one.

  Returns:
    String containing the IP of an active load balancer.
  """
  raw_ips = file_io.read(constants.LOAD_BALANCER_IPS_LOC)
  ips = raw_ips.split('\n')
  return ips[0]

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
  return yaml.safe_load(info)

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
    with open(constants.ZK_LOCATIONS_FILE) as locations_file:
      return ','.join('{}:2181'.format(line.strip())
                      for line in locations_file if line.strip())
  except IOError as io_error:
    logger.exception(io_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except ValueError as value_error:
    logger.exception(value_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except TypeError as type_error:
    logger.exception(type_error)
    return constants.ZK_DEFAULT_CONNECTION_STR
  except KeyError as key_error:
    logger.exception(key_error)
    return constants.ZK_DEFAULT_CONNECTION_STR

def get_zk_node_ips():
  """ Returns a list of zookeeper node IPs.

  Returns:
    A list containing the hosts that run zookeeper roles in the current
    AppScale deployment.
  """
  try:
    with open(constants.ZK_LOCATIONS_FILE) as locations_file:
      return [line.strip() for line in locations_file if line.strip()]
  except IOError as io_error:
    logger.exception(io_error)
    return []
  except ValueError as value_error:
    logger.exception(value_error)
    return []
  except TypeError as type_error:
    logger.exception(type_error)
    return []
  except KeyError as key_error:
    logger.exception(key_error)
    return []

def get_db_master_ip():
  """ Returns the master datastore IP.

  Returns:
    A str, the IP of the datastore master.
  """
  try:
    return file_io.read(constants.MASTERS_FILE_LOC).rstrip()
  except IOError:
    return []

def get_db_slave_ips():
  """ Returns the slave datastore IPs.

  Returns:
    A list of IP of the datastore slaves.
  """
  try:
    with open(constants.SLAVES_FILE_LOC) as slaves_file:
      return [line.strip() for line in slaves_file if line.strip()]
  except IOError:
    return []

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
    logger.warning("Search role is not configured.")
    return ""
