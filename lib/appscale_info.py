# Programmer: Navraj Chohan <nlake44@gmail.com>
""" 
This file contains functions for getting and setting information related 
to AppScale and the current node/machine.
"""
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

