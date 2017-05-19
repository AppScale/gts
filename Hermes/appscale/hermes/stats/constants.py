# The intervals for updating cluster stats profile (in milliseconds)
PROFILE_NODES_STATS_INTERVAL = 15*1000
PROFILE_PROCESSES_STATS_INTERVAL = 65*1000
PROFILE_PROXIES_STATS_INTERVAL = 35*1000

# Path to haproxy stats socket
HAPROXY_STATS_SOCKET_PATH = '/etc/haproxy/stats'

# Quiet logging intervals
LOCAL_STATS_DEBUG_INTERVAL = 5*60
CLUSTER_STATS_DEBUG_INTERVAL = 15*60

# Path to dictionary to write profile log
PROFILE_LOG_DIR = '/var/log/appscale/profile'

# Stats which were produce less than X seconds ago is considered as current
ACCEPTABLE_STATS_AGE = 10


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
