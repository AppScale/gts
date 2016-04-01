""" Different tests done against App Engine Datastore API. """
import abc
import logging
import os
import sys
import time

from __init__ import ApiTestBase

from ..common import util
from ..common import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.ext import db

class TestDB(ApiTestBase):
  """ Class implementing DB test. """
  def run(self):
    """ Runs the DB tests.

    Returns:
      A dictionary with results.
    """ 
    result = {}
    thismodule = sys.modules[__name__]
    for test in constants.DBTestIdentifiers.all_tests():
      result[test] = getattr(thismodule, test)(self.uuid_tag)
    return result

  def cleanup(self):
    cleanup()

class TestModel(db.Model):
  """
  A datastore module for measuring latency.
  """
  test_string = db.StringProperty(required=True)
  intial_ts = db.DateTimeProperty(auto_now=True)
  modified_ts = db.DateTimeProperty(auto_now_add=True)
  text_blob = db.TextProperty()

def put(uuid):
  """ Stores entities in the datastore and time them. 

  Args:
    uuid: A str, unique identifier attached to all entities.
  Returns:
    A tuple of two list. A list of float times to store 
    all entities, and a list of errors. A zero value signifies 
    a failure.
  """
  timings = []
  errors = []
  for index in range(0, constants.NUM_SAMPLES):
    random_blob = util.random_string(constants.MAX_STRING_LENGTH)
    test_model = TestModel(key_name=uuid + str(index),
      test_string=uuid, text_blob=random_blob)
    start = time.time()
    try:
      test_model.put()
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0
    timings.append(total_time * constants.SECONDS_TO_MILLI)
  return (timings, errors)
 
def get(uuid):
  """ Retrieves entities from the datastore and time them.

  Args:
    uuid: A str, unique identifier a part of the keynames of entities.
  Returns:
    A tuple of two lists. A list of float times to get
    all entities, and a list of errors. A zero value signifies 
    a failure.

  """
  timings = []
  errors = []
  for index in range(0, constants.NUM_SAMPLES):
    start = time.time()
    try:
      test_model = TestModel.get_by_key_name(key_names=uuid + str(index))
      # Access a variable and modify a variable.
      if not test_model:
        raise Exception("Unable to fetch entity.")
      test_model.test_string = test_model.test_string[:]
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0
    timings.append(total_time * constants.SECONDS_TO_MILLI)
  return (timings, errors)

def query(uuid):
  """ Query stored entities and time them.

  Returns:
    A tuple of two lists. A list of float times to query
    all entities, and a list of errors. A zero value signifies 
    a failure.
  """
  timings = []
  errors = []
  for _ in range(0, constants.NUM_SAMPLES):
    start = time.time()
    try:
      query = TestModel.all()
      query.filter("test_string =", uuid)
      query.fetch(constants.NUM_SAMPLES)
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0
    timings.append(total_time * constants.SECONDS_TO_MILLI)

  return (timings, errors)

def delete(uuid):
  """ Deletes stored entities and time them.

  Args:
    uuid: A str, unique identifier a part of the keynames of entities.
  Returns:
    A tuple of two lists. A list of float times to delete
    all entities, and a list of errors. A zero value signifies 
    a failure.
  """
  timings = []
  errors = []
  for index in range(0, constants.NUM_SAMPLES):
    entity = None
    try:
      entity = TestModel.get_by_key_name(key_names=uuid + str(index))
      if not entity:
        raise Exception("Unable to first fetch entity.")
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0
      timings.append(total_time)
      logging.error("Left over entity with keyname {0}".\
        format(uuid + str(index)))
      continue

    start = time.time()
    try:
      entity.delete()
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0
    timings.append(total_time * constants.SECONDS_TO_MILLI)
  return (timings, errors)

def cleanup():
  """ Cleans up any entities from previous trials. """
  try:
    query = TestModel.all()
    results = query.fetch(constants.MAX_LIMIT)
    db.delete(results)
  except Exception, exception:
    logging.exception(exception)
