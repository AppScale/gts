""" Cassandra-specific constants. """
from cassandra.policies import DCAwareRoundRobinPolicy

# The current data layout version.
CURRENT_VERSION = 2.0

# The load balancing policy to use when connecting to a cluster.
LB_POLICY = DCAwareRoundRobinPolicy()
