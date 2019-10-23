""" Common constants for managing AppServer instances. """

import os
import urllib2

from appscale.common.constants import APPSCALE_HOME


class BadConfigurationException(Exception):
  """ An application is configured incorrectly. """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value

  def __str__(self):
    return repr(self.value)


class NoRedirection(urllib2.HTTPErrorProcessor):
  """ A url opener that does not automatically redirect. """
  def http_response(self, request, response):
    """ Processes HTTP responses.

    Args:
      request: An HTTP request object.
      response: An HTTP response object.
    Returns:
      The HTTP response object.
    """
    return response
  https_response = http_response


# The location of the API server start script.
API_SERVER_LOCATION = os.path.join('/', 'opt', 'appscale_venvs', 'api_server',
                                   'bin', 'appscale-api-server')

# Prefix for API server services.
API_SERVER_PREFIX = 'appscale-api-server@'

# Max application server log size in bytes.
APP_LOG_SIZE = 250 * 1024 * 1024

# The amount of seconds to wait between checking if an application is up.
BACKOFF_TIME = 1

# Patterns that match jars that should be stripped from version sources.
CONFLICTING_JARS = [
  'appengine-api-1.0-sdk-*.jar',
  'appengine-api-stubs-*.jar',
  'appengine-api-labs-*.jar',
  'appengine-jsr107cache-*.jar',
  'jsr107cache-*.jar',
  'appengine-mapreduce*.jar',
  'appengine-pipeline*.jar',
  'appengine-gcs-client*.jar'
]

# The dashboard's project ID.
DASHBOARD_PROJECT_ID = 'appscaledashboard'

# Max log size for AppScale Dashboard servers.
DASHBOARD_LOG_SIZE = 10 * 1024 * 1024

# The default amount of memory in MB to allow an instance.
DEFAULT_MAX_APPSERVER_MEMORY = 400

# The web path to fetch to see if the application is up
FETCH_PATH = '/_ah/health_check'

# The location of the App Engine SDK for Go.
GO_SDK = os.path.join('/', 'opt', 'go_appengine')

# The Java class that runs AppServer instances.
JAVA_APPSERVER_CLASS = ('com.google.appengine.tools.development.'
                        'DevAppServerMain')

# Default logrotate configuration directory.
LOGROTATE_CONFIG_DIR = os.path.join('/', 'etc', 'logrotate.d')

# The location on the filesystem where the PHP executable is installed.
PHP_CGI_LOCATION = "/usr/bin/php-cgi"

# A template for an instance's pidfile location.
PIDFILE_TEMPLATE = os.path.join('/', 'var', 'run', 'appscale',
                                'app___{revision}-{port}.pid')

# The modified Java SDK's lib directory.
REPACKED_LIB_DIR = os.path.join(
  APPSCALE_HOME, 'AppServer_Java', 'appengine-java-sdk-repacked', 'lib')

# The number of seconds to wait for a health check response.
HEALTH_CHECK_TIMEOUT = 2

# The highest available port to assign to an API server.
MAX_API_SERVER_PORT = 19999

# The maximum number of threads to use for executing blocking tasks.
MAX_BACKGROUND_WORKERS = 4

# The number of seconds an instance is allowed to finish serving requests after
# it receives a shutdown signal.
MAX_INSTANCE_RESPONSE_TIME = 600

# Patterns that match jars that should be copied to version sources.
MODIFIED_JARS = [
  os.path.join(REPACKED_LIB_DIR, 'user', '*.jar'),
  os.path.join(REPACKED_LIB_DIR, 'impl', 'appscale-*.jar'),
  os.path.join('/', 'usr', 'share', 'appscale', 'ext', '*')
]

# Common prefix for instance services.
SERVICE_INSTANCE_PREFIX = 'appscale-instance-run@'

# The script used for starting Python AppServer instances.
PYTHON_APPSERVER = os.path.join(APPSCALE_HOME, 'AppServer',
                                'dev_appserver.py')

# A mapping of instance classes to memory limits in MB.
INSTANCE_CLASSES = {
    'F1': 128,
    'F2': 256,
    'F4': 512,
    'F4_1G': 1024,
    'B1': 128,
    'B2': 256,
    'B4': 512,
    'B4_1G': 1024,
    'B8': 1024,
}

# The amount of seconds to wait for an application to start up.
START_APP_TIMEOUT = 180

# The lowest port to use when starting instances.
STARTING_INSTANCE_PORT = 20000

# Apps which can access any application's data.
TRUSTED_APPS = ["appscaledashboard"]

# The ZooKeeper node that keeps track of running AppServers by version.
VERSION_REGISTRATION_NODE = '/appscale/instances_by_version'

# The port Hermes listens on.
HERMES_PORT = 4378
