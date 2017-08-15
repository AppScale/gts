""" Common constants for managing AppServer instances. """

import os


# Max application server log size in bytes.
APP_LOG_SIZE = 250 * 1024 * 1024

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
DEFAULT_MAX_MEMORY = 400

# Default logrotate configuration directory.
LOGROTATE_CONFIG_DIR = os.path.join('/', 'etc', 'logrotate.d')

# A prefix added to instance entries to distinguish them from services.
MONIT_INSTANCE_PREFIX = 'app___'

# A mapping of instance classes to memory limits in MB.
INSTANCE_CLASSES = {'F1': 128,
                    'F2': 256,
                    'F4': 512,
                    'F4_1G': 1024}
