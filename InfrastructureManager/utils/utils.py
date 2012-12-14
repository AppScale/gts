"""
A collection of common utility functions which can be used by any
module within the AppScale Infrastructure Manager implementation.
"""
import os
import random
import string
import sys
import time

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

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
  for l in location:
    path = os.path.abspath(l)
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
  alphabet = string.digits + string.letters
  return ''.join(random.choice(alphabet) for i in range(length))


def flatten(list):
  """
  Flatten all the elements in the given list into a single list.
  For an example if the input list is [1, [2,3], [4,5,[6,7]]],
  the resulting list will be [1,2,3,4,5,6,7].

  Args:
    list  A list of items where each member item could be a list

  Returns:
    A single list with no lists as its elements
  """
  result = []
  for l in list:
    if hasattr(l, '__iter__'):
      result.extend(flatten(l))
    else:
      result.append(l)
  return result


def has_parameter(p, params):
  """
  Checks whether the parameter p is present in the params map.

  Args:
    p       A parameter name
    params  A dictionary of parameters

  Returns:
    True if params contains p and the value of p is not None.
    Returns False otherwise.
  """
  return params.has_key(p) and params[p] is not None


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
  return sorted(set(list1) - set(list2))


def obscure_string(string):
  """
  Obscures the input string by replacing all but the last 4 characters
  in the string with the character '*'. Useful for obscuring, security
  credentials, credit card numbers etc.

  Args:
    string  A string of characters

  Returns:
    A new string where all but the last 4 characters of the input
    string has been replaced by '*'.
  """
  if string is None or len(string) < 4:
    return string
  last_four = string[-4:]
  obscured = '*' * (len(string) - 4)
  return obscured + last_four

def sleep(seconds):
  """
  Sleep and delay for the specified number of seconds.

  Args:
    seconds Number of seconds to sleep
  """
  time.sleep(seconds)


