# Containers for txid sequences start with this string.
CONTAINER_PREFIX = 'txids'

# Transaction ID sequence nodes start with this string.
COUNTER_NODE_PREFIX = 'tx'

# ZooKeeper stores the sequence counter as a signed 32-bit integer.
MAX_SEQUENCE_COUNTER = 2 ** 31 - 1

# The name of the node used for manually setting a txid offset.
OFFSET_NODE = 'txid_offset'
