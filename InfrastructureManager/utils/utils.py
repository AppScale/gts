"""
A collection of common utility functions which can be used by any
module within the AppScale Infrastructure Manager implementation.
"""
import os
import subprocess
import sys
import time
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), '../../lib'))
from constants import SERVICES_DIR

# The directory that contains the deployment's private SSH key.
KEY_DIRECTORY = '/etc/appscale/keys/cloud1'


class ExitCodes(object):
  """ Shell exit codes. """
  SUCCESS = 0


class MonitStates(object):
  RUNNING = 'Running'
  UNMONITORED = 'Not monitored'


class ServiceException(Exception):
  pass


def get_secret(filename='/etc/appscale/secret.key'):
  """
  Reads a secret key string from the specified file and returns
  it.

  Args:
    filename  The input file from which the secret should be
              read from (Optional). If not specified defaults to
              /etc/appscale/secret.key

  Returns:
    A secret key string read from the input file

  Raises
    IOError   If the input file does not exist
  """
  return read_file(os.path.abspath(filename), chomp=True)


def read_file(location, chomp=True):
  """
  Read the specified file and return the contents. Optionally
  the file content could be subjected to a chomp operation
  before returning.

  Args:
    location  Location of the file that needs to be read
    chomp     True if the file content needs to be chomped
              prior to returning. This is an optional parameter
              and defaults to True.

  Raises:
    IOError   If the specified file does not exist
  """
  file_handle = open(location, 'r')
  contents = file_handle.read()
  file_handle.close()
  if chomp:
    return contents.rstrip('\n')
  else:
    return contents


def write_key_file(location, content):
  """
  Write the specified content to the file locations in the given the list
  and set the file permissions to 0600.

  Args:
    location  A file name (string) or a list of file names
    content   Content of the cryptographic key
  """
  if type(location) == type(''):
    location = [location]
  for entry in location:
    path = os.path.abspath(entry)
    file_handle = open(path, 'w')
    file_handle.write(content)
    file_handle.close()
    os.chmod(path, 0600)


def log(msg):
  """
  Log the specified message to the stdout and flush the stream.

  Args:
    msg  Message to be logged
  """
  print msg
  sys.stdout.flush()


def get_random_alphanumeric(length=10):
  """
  Generate a random alphanumeric string of the specified length.

  Args:
    length  Length of the random string that should be
            generated (Optional). Defaults to 10.

  Returns:
    A random alphanumeric string of the specified length.
  """
  return str(uuid.uuid4()).replace('-', '')[:length]


def flatten(the_list):
  """
  Flatten all the elements in the given list into a single list.
  For an example if the input list is [1, [2,3], [4,5,[6,7]]],
  the resulting list will be [1,2,3,4,5,6,7].

  Args:
    the_list  A list of items where each member item could be a list

  Returns:
    A single list with no lists as its elements
  """
  result = []
  for entry in the_list:
    if hasattr(entry, '__iter__'):
      result.extend(flatten(entry))
    else:
      result.append(entry)
  return result


def has_parameter(param, params):
  """
  Checks whether the parameter param is present in the params map.

  Args:
    param       A parameter name
    params  A dictionary of parameters

  Returns:
    True if params contains param.
    Returns False otherwise.
  """
  return params.has_key(param)


def diff(list1, list2):
  """
  Returns the list of entries that are present in list1 but not
  in list2.

  Args:
    list1 A list of elements
    list2 Another list of elements

  Returns:
    A list of elements unique to list1
  """
  diffed_list = []
  for item in list1:
    if item not in list2:
      diffed_list.append(item)
  return diffed_list


def obscure_string(input_string):
  """
  Obscures the input string by replacing all but the last 4 characters
  in the string with the character '*'. Useful for obscuring, security
  credentials, credit card numbers etc.

  Args:
    input_string  A string of characters

  Returns:
    A new string where all but the last 4 characters of the input
    string has been replaced by '*'.
  """
  if input_string is None or len(input_string) < 4:
    return input_string
  last_four = input_string[-4:]
  obscured = '*' * (len(input_string) - 4)
  return obscured + last_four

def sleep(seconds):
  """
  Sleep and delay for the specified number of seconds.

  Args:
    seconds Number of seconds to sleep
  """
  time.sleep(seconds)


def get_public_key(keyname):
  """ Fetches the deployment's public key.

  Args:
    keyname: A string containing the deployment's keyname.
  """
  private_key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  return subprocess.check_output(
    ['ssh-keygen', '-y', '-f', private_key_file]).strip()


def ssh(ip_address, keyname, cmd, method=subprocess.check_call):
  """ Runs a command on a given machine.

  Args:
    ip_address: A string containing the IP address of the remote machine.
    keyname: A string containing the deployment's keyname.
    cmd: The command to run on the remote machine.
    method: The function to run the command with.
  Returns:
    The output of the function defined by method.
  """
  key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  ssh_cmd = ['ssh', '-i', key_file, ip_address, cmd]
  return method(ssh_cmd)


def scp_to(ip_address, keyname, local_file, remote_file):
  """ Copies a file from the local machine to a remote one.

  Args:
    ip_address: A string containing the IP address of the remote machine.
    keyname: A string containing the deployment's keyname.
    local_file: A string containing the location of a file.
    remote_file: A string containing a location on the remote machine.
  """
  key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  remote_location = '{}:{}'.format(ip_address, remote_file)
  scp_cmd = ['scp', '-i', key_file, local_file, remote_location]
  subprocess.check_call(scp_cmd)


def scp_from(ip_address, keyname, remote_file, local_file):
  """ Copies a file from a remote machine to the local one.

  Args:
    ip_address: A string containing the IP address of the remote machine.
    keyname: A string containing the deployment's keyname.
    remote_file: A string containing a location on the remote machine.
    local_file: A string containing the location of a file.
  """
  key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  remote_location = '{}:{}'.format(ip_address, remote_file)
  scp_cmd = ['scp', '-i', key_file, remote_location, local_file]
  subprocess.check_call(scp_cmd)


def zk_service_name(ip_address, keyname):
  """ Fetches the name of the zookeeper service on a given machine.

  Args:
    ip_address: A string containing the IP address of the ZooKeeper machine.
    keyname: A string containing the deployment's keyname.
  Returns:
    A string containing the name of the zookeeper service.
  Raises:
    OSError if the zookeeper service cannot be found.
  """
  key_file = '{}/{}.key'.format(KEY_DIRECTORY, keyname)
  ssh_cmd = ['ssh', '-i', key_file, ip_address, 'ls {}'.format(SERVICES_DIR)]
  response = subprocess.check_output(ssh_cmd)
  init_files = response.split()
  for init_file in init_files:
    if 'zookeeper' in init_file:
      return init_file
  raise OSError('Unable to find ZooKeeper on {}'.format(ip_address))


def monit_status(summary, service):
  """ Retrieves the status of a Monit service.

  Args:
    summary: A string containing the output of 'monit summary'.
    service: A string containing the name of a service.
  Raises:
    ServiceException if summary does not include service.
  """
  for line in summary.split('\n'):
    if service in line:
      return ' '.join(line.split()[2:])
  raise ServiceException('Unable to find Monit entry for {}')
