""" Cassandra-specific constants. """
from cassandra.policies import DCAwareRoundRobinPolicy

# The load balancing policy to use when connecting to a cluster.
LB_POLICY = DCAwareRoundRobinPolicy()
