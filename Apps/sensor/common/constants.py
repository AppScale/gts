""" Constants used by client and server side applications.

DO NOT STORE SENSITIVE INFORMATION IN THIS FILE.
"""
import os
import logging

# Location of the AppScale deployment.
APPSCALE_LOCATION = "portal.appscale.com"

# Whether or not we're in debug mode.
DEBUG_MODE = False

# Force to always think we're in local testing for testing in
# prod environments.
FORCE_LOCAL = False

# HTTP Codes.
HTTP_OK = 200
HTTP_DENIED = 403
HTTP_NOTFOUND = 404
HTTP_ERROR = 500

# Most entities you can query for on GAE.
MAX_LIMIT = 9999

# Length of random test strings.
MAX_STRING_LENGTH = 10000

# Number of samples to test an API.
NUM_SAMPLES = 1

# Convert multiplier from seconds to milliseconds.
SECONDS_TO_MILLI = 1000

if 'SERVER_SOFTWARE' in os.environ and \
  os.environ['SERVER_SOFTWARE'].startswith('Development'):
  logging.info("In DEBUG/TEST mode.")
  TEST_MODE = True
  DEBUG_MODE = True

# High level tags use to communicate between the server and client.
class ApiTags(object):
  """ A class containing shared constants. """
  API_KEY = "api_key"
  APP_ID = "app_id"
  DATA = "data"
  USER_ID = "email"

# A class with all the tests for the DB API.
class DBTestIdentifiers(object):
  """ A class containing shared constants. """
  SUITE_TAG = "DB"
  DISPLAY_TAG = "Datastore"
  PUT = "put"
  GET = "get"
  QUERY = "query"
  DELETE = "delete"

  @classmethod
  def all_tests(cls):
    """ Returns all tests of DB. """
    return [cls.PUT, cls.GET, cls.QUERY, cls.DELETE]

# A class with all the tests for the Memcache API.
class MemcacheTestIdentifiers(object):
  """ A class containing shared constants. """
  SUITE_TAG = "Memcache"
  DISPLAY_TAG = "Memcache"
  SET = "set"
  GET = "get"
  DELETE = "delete"

  @classmethod
  def all_tests(cls):
    """ Returns all tests of Memcache. """
    return [cls.SET, cls.GET, cls.DELETE]

# A class with al tests for URLfetch API.
class UrlfetchTestIdentifiers(object):
  """ A class containing shared constants. """
  SUITE_TAG = "Urlfetch"
  DISPLAY_TAG = "URLFetch"
  GCS = "fetch_gcs"
  AWS = "fetch_aws"
  GOOGLE = "fetch_google"

  # The following are links to fetch for corresponding tests.
  GCS_URL = "http://storage.googleapis.com/appscale-fetch-test/" \
            "417px-AppScale_Systems_Logo.png"
  AWS_URL = "https://s3.amazonaws.com/appscale-fetch-test/" \
            "417px-AppScale_Systems_Logo.png"
  GOOGLE_URL = "http://google.com"

  @classmethod
  def all_tests(cls):
    """ Returns all tests of Urlfetch. """
    return [cls.GCS, cls.AWS, cls.GOOGLE]

# A class to get all test tags.
class AllTestSuites(object):
  """ A class containing all test suites. """
  @classmethod
  def all_displayed_suites(cls):
    """ Returns all high level test suites for display. """
    return [DBTestIdentifiers.DISPLAY_TAG,
      MemcacheTestIdentifiers.DISPLAY_TAG,
      UrlfetchTestIdentifiers.DISPLAY_TAG]

  @classmethod
  def all_suites(cls):
    """ Returns all high level test suites. """
    return [DBTestIdentifiers.SUITE_TAG,
      MemcacheTestIdentifiers.SUITE_TAG,
      UrlfetchTestIdentifiers.SUITE_TAG]

  @classmethod
  def get_all_identifiers(cls):
    """ Returns all the test classes for each suite. """
    return [DBTestIdentifiers, MemcacheTestIdentifiers,
      UrlfetchTestIdentifiers]
