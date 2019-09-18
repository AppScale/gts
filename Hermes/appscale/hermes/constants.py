# Path to haproxy stats sockets
HAPROXY_APPS_STATS_SOCKET_PATH = '/etc/haproxy/stats'
HAPROXY_SERVICES_STATS_SOCKET_PATH = '/etc/haproxy/service-stats'
# Path to haproxy stats sockets
HAPROXY_APPS_CONFIGS_DIR = '/etc/haproxy/app-sites-enabled/'
HAPROXY_SERVICES_CONFIGS_DIR = '/etc/haproxy/service-sites-enabled/'

# Path to dictionary to write profile log
PROFILE_LOG_DIR = '/var/log/appscale/profile'

# The amount of time to wait for remote http requests.
REMOTE_REQUEST_TIMEOUT = 60

# Stats which were produce less than X seconds ago is considered as current
ACCEPTABLE_STATS_AGE = 10

# The ZooKeeper location for storing Hermes configurations
NODES_STATS_CONFIGS_NODE = '/appscale/stats/profiling/nodes'
PROCESSES_STATS_CONFIGS_NODE = '/appscale/stats/profiling/processes'
PROXIES_STATS_CONFIGS_NODE = '/appscale/stats/profiling/proxies'


class _MissedValue(object):
  """
  Instance of this private class denotes missed value.
  It's used to denote values of stats properties which are missed
  in haproxy stats.
  """

  def __bool__(self):
    return False

  def __repr__(self):
    return ''


MISSED = _MissedValue()

# The port Hermes listens to.
HERMES_PORT = 4378

# Name of header where secret should be passed
SECRET_HEADER = 'Appscale-Secret'


class HTTP_Codes(object):
  """ A class with HTTP status codes. """
  HTTP_OK = 200
  HTTP_BAD_REQUEST = 400
  HTTP_DENIED = 403
  HTTP_INTERNAL_ERROR = 500
  HTTP_NOT_IMPLEMENTED = 501
