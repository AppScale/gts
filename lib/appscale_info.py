# Programmer: Navraj Chohan
""" 
This file contains functions for getting information related to AppScale
and the current node/machine
"""
import file_io
import constants
import multiprocessing

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
  """ Get the number of CPU processes on the current machine
  
  Returns:
    Integer of the number of CPUs on the current machine
  """
  
  return multiprocessing.cpu_count() 
