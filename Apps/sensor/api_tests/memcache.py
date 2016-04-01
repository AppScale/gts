""" Different tests done against App Engine Memcache API. """

import logging
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from common import util
from common import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api import memcache

from __init__ import ApiTestBase

class TestMemcache(ApiTestBase):
  """ Class implementing Memcache test. """
  def run(self):
    """ Runs the Memcache tests.

    Returns:
      A dictionary with results.
    """ 
    result = {}
    thismodule = sys.modules[__name__]
    for test in constants.MemcacheTestIdentifiers.all_tests():
      result[test] = getattr(thismodule, test)(self.uuid_tag)
    return result

  def cleanup(self):
    """ Clean up for memcache. Since memcache is transient, we do
      not clean this up.
    """
    pass

def set(uuid):
  """ Stores items in the memcache and times them.

  Args:
    uuid: A unique identifier as part of the keynames of items.
  Returns:
    A tuple of two lists. A list of float times to store all items,
    and a list of errors. A zero value signifies a failure.
  """
  timings = []
  errors = []

  for index in range(0, constants.NUM_SAMPLES):
    random_string = util.random_string(constants.MAX_STRING_LENGTH)

    start = time.time()
    try:
      # Incorporate uuid in the value to be set.
      memcache.set(uuid + str(index), str(uuid) + random_string)
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0

    timings.append(total_time * constants.SECONDS_TO_MILLI)

  return (timings, errors)

def get(uuid):
  """ Retrieves items from the memcache and times them.

  Args:
    uuid: A unique identifier as part of the keynames of items.
  Returns:
    A tuple of two lists. A list of float times to get
    all items, and a list of errors. A zero value signifies
    a failure.
  """
  timings = []
  errors = []

  for index in range(0, constants.NUM_SAMPLES):
    start = time.time()

    try:
      result = memcache.get(uuid + str(index))
      # Look for uuid in the value returned.
      if not result.startswith(uuid):
        raise Exception()

      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0

    timings.append(total_time * constants.SECONDS_TO_MILLI)

  return (timings, errors)

def delete(uuid):
  """ Deletes memcache items and times them.

  Args:
    uuid: A unique identifier as part of the keynames of items.
  Returns:
    A tuple of two lists. A list of float times to delete
    all items, and a list of errors. A zero value signifies
    a failure.
  """
  timings = []
  errors = []

  for index in range(0, constants.NUM_SAMPLES):
    start = time.time()

    try:
      memcache.delete(uuid + str(index))
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0

    timings.append(total_time * constants.SECONDS_TO_MILLI)

  return (timings, errors)
