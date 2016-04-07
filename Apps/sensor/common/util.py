#!/usr/bin/env python
""" Helpful utility functions.

DO NOT STORE SENSITIVE INFORMATION IN THIS FILE.
"""


import hashlib
import random
import time

def get_uuid():
  """ Returns a time based UUID.
  Returns:
    A str, based off time.
  """
  return str(time.time())

def random_string(length):
  """ Returns a string of a given length.

  Args:
    length: The length of the random string which is returned.
  Returns:
    A random string.
  """
  hash = hashlib.sha256()
  ret = "a"
  while len(ret) < length:
    hash.update(str(random.random()))
    ret += hash.hexdigest()
  return ret[0:length]
