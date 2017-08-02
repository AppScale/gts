# The intervals for writing to cluster stats profile
PROFILE_NODES_STATS_INTERVAL = 15
PROFILE_PROCESSES_STATS_INTERVAL = 65
PROFILE_PROXIES_STATS_INTERVAL = 35

# Path to haproxy stats socket
HAPROXY_STATS_SOCKET_PATH = '/etc/haproxy/stats'

# Path to dictionary to write profile log
PROFILE_LOG_DIR = '/var/log/appscale/profile'

# The amount of time to wait for local stats from a slave node.
STATS_REQUEST_TIMEOUT = 60

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

  def __nonzero__(self):
    return False

  def __repr__(self):
    return ''


MISSED = _MissedValue()
