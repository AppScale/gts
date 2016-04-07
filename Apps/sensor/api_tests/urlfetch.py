""" Different tests done against App Engine Urlfetch API. """

import logging
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from common import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api import urlfetch

from __init__ import ApiTestBase

class TestUrlfetch(ApiTestBase):
  """ Class implementing URLfetch test. """
  def run(self):
    """ Runs the URLfetch tests.

    Returns:
      A dictionary with results.
    """ 
    result = {}
    thismodule = sys.modules[__name__]
    for test in constants.UrlfetchTestIdentifiers.all_tests():
      result[test] = getattr(thismodule, test)(self.uuid_tag)
    return result

  def cleanup(self):
    """ Clean up for URLfetch. Do nothing since operations are
    idempotent.
    """
    pass

def fetch(url):
  """ Fetches an item from the given URL and returns timings.

  Args:
    url: The URL to fetch from.
  Returns:
    A tuple of two lists. A list of float times to store all items,
    and a list of errors. A zero value signifies a failure.
  """
  timings = []
  errors = []

  for _ in range(0, constants.NUM_SAMPLES):
    start = time.time()
    try:
      result = urlfetch.fetch(url)
      if result.status_code != constants.HTTP_OK:
        errors.append("Fetch code returned {0}".format(result.status_code))
      total_time = time.time() - start
    except Exception, exception:
      logging.exception(exception)
      errors.append(str(exception))
      total_time = 0

    timings.append(total_time * constants.SECONDS_TO_MILLI)

  return (timings, errors)

def fetch_gcs(uuid):
  """ Fetches an image from Google Cloud Storage. 

  Args:
    uuid: A str, a unique identifier.
  Returns:
    A tuple of two lists. A list of float times to store all items,
    and a list of errors. A zero value signifies a failure.
  """
  fetch_url = constants.UrlfetchTestIdentifiers.GCS_URL
  return fetch(fetch_url)

def fetch_aws(uuid):
  """ Fetches an image from Amazon's S3.

  Args:
    uuid: A str, a unique identifier.
  Returns:
    A tuple of two lists. A list of float times to store all items,
    and a list of errors. A zero value signifies a failure.
  """
  fetch_url = constants.UrlfetchTestIdentifiers.AWS_URL
  return fetch(fetch_url)

def fetch_google(uuid):   
  """ Fetches from Google home page.

  Args:
    uuid: A str, a unique identifier.
  Returns:
    A tuple of two lists. A list of float times to store all items,
    and a list of errors. A zero value signifies a failure.
  """
  fetch_url = constants.UrlfetchTestIdentifiers.GOOGLE_URL
  return fetch(fetch_url)
