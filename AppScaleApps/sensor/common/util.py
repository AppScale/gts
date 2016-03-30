#!/usr/bin/env python
""" Helpful utility functions.

DO NOT STORE SENSITIVE INFORMATION IN THIS FILE.
"""

import datetime
import hashlib
import os
import random
import re
import time
from constants import FORCE_LOCAL

def chunks(list, chunk_size):
  """ Yield successive n-sized chunks from list.

    Args:
      list: A list, the list of objects to be cut in chunks.
      chunk_size: A number, the size of each list chunk.
    Returns:
      A list of lists with chunk_size length each.
  """
  for index in xrange(0, len(list), chunk_size):
      yield list[index:index + chunk_size]

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

def remove_non_ascii(string):
  """ A function to clean non-ascii characters to prevent exceptions on db.put.
  """
  return "".join(filter(lambda x: ord(x) < 128, string))

def is_local():
  """ Determine if we are in testing mode.

  Returns:
    True if local, False otherwise.
  """
  return 'SERVER_SOFTWARE' in os.environ and \
    os.environ['SERVER_SOFTWARE'].startswith('Development') or FORCE_LOCAL

def is_appscale():
  """ Determine if we are running on AppScale.

  Returns:
    True if on AppScale, False otherwise.
  """
  return 'SERVER_SOFTWARE' in os.environ and \
    os.environ['SERVER_SOFTWARE'].startswith('AppScale')

def is_gae():
  """ Determine if we are running on GAE.

  Returns:
    True if running on GAE, False otherwise.
  """
  return 'SERVER_SOFTWARE' in os.environ and \
    os.environ['SERVER_SOFTWARE'].startswith('Google')

def timesince(dt, default="just now"):
  """ Returns string representing "time since" e.g. 3 days ago, 5 hours
    ago etc.

  Args:
    dt: The datetime.datetime object for which we're finding the difference.
  Returns:
    A string of the time since the given time.
  """
  now = datetime.datetime.utcnow()
  diff = now - dt

  periods = (
    (diff.days / 365, "year", "years"),
    (diff.days / 30, "month", "months"),
    (diff.days / 7, "week", "weeks"),
    (diff.days, "day", "days"),
    (diff.seconds / 3600, "hour", "hours"),
    (diff.seconds / 60, "minute", "minutes"),
    (diff.seconds, "second", "seconds"),
  )

  for period, singular, plural in periods:
    if period:
      return "%d %s ago" % (period, singular if period == 1 else plural)

  return default
