"""
 Datastore Constants
"""
import cassandra.cluster
import re

SECRET_LOCATION = "/etc/appscale/secret.key"

ERROR_DEFAULT = "DB_ERROR:"
NONEXISTANT_TRANSACTION = "0"

# The datastore's default HTTP port.
DEFAULT_PORT = 4000

# The lowest character to separate different fields in a row key.
KEY_DELIMITER = '\x00'

# The character used to separate kinds in an ancestry.
KIND_SEPARATOR = '\x01'

# HTTP code to indicate that the request is invalid.
HTTP_BAD_REQUEST = 400

# The length of an ID string. A constant length allows lexicographic ordering.
ID_KEY_LENGTH = 10

# The character between the kind and the ID/name of an entity.
ID_SEPARATOR = ":"

# Maximum number of groups allowed in cross group transactions.
MAX_GROUPS_FOR_XG = 25

# The maximum number of composite indexes an application can have.
MAX_NUMBER_OF_COMPOSITE_INDEXES = 1000

# The maximum number of seconds a transaction can take. In GAE, transactions
# "have a maximum duration of 60 seconds with a 10 second idle expiration time
# after 30 seconds." The 10-second idle check is not yet implemented.
MAX_TX_DURATION = 60

# Matches property names that should not be returned to the user.
RESERVED_PROPERTY_NAME = re.compile('^__.*__$')

# Entities have a .78% chance of getting the scatter property.
SCATTER_CHANCE = .0078

# The scatter threshold is defined within a 2-byte space.
SCATTER_PROPORTION = int(round(256 ** 2 * SCATTER_CHANCE))

# A string used to create end keys when doing range queries.
TERMINATING_STRING = chr(255) * 500

# Tombstone value for soft deletes.
TOMBSTONE = "APPSCALE_SOFT_DELETE"

TRANSIENT_CASSANDRA_ERRORS = (
  cassandra.Unavailable, cassandra.Timeout, cassandra.CoordinationFailure,
  cassandra.OperationTimedOut, cassandra.cluster.NoHostAvailable)

# The database backends supported by the AppScale datastore.
VALID_DATASTORES = ['cassandra', 'fdb']

# Table names
USERS_TABLE = "USERS__"
JOURNAL_TABLE = "JOURNAL__"

ASC_PROPERTY_TABLE = "ASC_PROPERTY__"
DSC_PROPERTY_TABLE = "DSC_PROPERTY__"
COMPOSITE_TABLE = "COMPOSITE_INDEXES__"
APP_ID_TABLE = "APP_IDS__"
APP_ENTITY_TABLE = "ENTITIES__"
APP_KIND_TABLE = "KINDS__"
METADATA_TABLE = "METADATA__"
DATASTORE_METADATA_TABLE = "DATASTORE_METADATA__"
SCHEMA_TABLE = '__key__'

INITIAL_TABLES = [ASC_PROPERTY_TABLE,
                  DSC_PROPERTY_TABLE,
                  APP_ID_TABLE,
                  APP_ENTITY_TABLE,
                  APP_KIND_TABLE,
                  COMPOSITE_TABLE,
                  USERS_TABLE,
                  SCHEMA_TABLE,
                  DATASTORE_METADATA_TABLE]

###########################################
# DB schemas for version 1 of the datastore
###########################################
JOURNAL_SCHEMA = [
  "Encoded_Entity"]

ENTITY_TABLE_SCHEMA = [
  "Encoded_Entity",
  "Txn_Num"]

###########################################
# DB schema for version 2 of the datastore
###########################################

# The schema of the table which holds the encoded entities
APP_ENTITY_SCHEMA = [
  "entity",
  "txnID"]

# Index tables store references are to entity table
PROPERTY_SCHEMA = [
  "reference" ]
APP_ID_SCHEMA = [
  "next_id" ]
APP_KIND_SCHEMA = [
  "reference" ]
COMPOSITE_SCHEMA = [
  "reference" ]
METADATA_SCHEMA = [
  "data" ]

USERS_SCHEMA = [
  "email",
  "pw",
  "date_creation", 
  "date_change",
  "date_last_login",
  "applications",
  "appdrop_rem_token",
  "appdrop_rem_token_exp",
  "visit_cnt",
  "cookie",
  "cookie_ip",
  "cookie_exp",
  "cksum",
  "enabled",
  "type",
  "is_cloud_admin",
  "capabilities" ]

DATASTORE_METADATA_SCHEMA = [
  "version"]

# All schema information for the keyspace is stored in the schema table.
SCHEMA_TABLE_SCHEMA = ['schema']


class TxnActions(object):
  """ Possible values in the 'action' column of the transaction table. """
  START = 0
  GET = 1
  MUTATE = 2
  ENQUEUE_TASK = 3


class Operations(object):
  """ Possible datastore operations on entities. """
  PUT = 'put'
  DELETE = 'delete'


###############################
# Generic Datastore Exceptions
###############################
class AppScaleDBError(Exception):
  """ Tossed for generic datastore errors
  """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value

  def __str__(self):
    return repr(self.value)

class AppScaleDBConnectionError(Exception):
  """ Tossed when there is a bad connection
  """ 
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

class AppScaleMisconfiguredQuery(Exception):
  """ Tossed when a query is misconfigured
  """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

class AppScaleBadArg(Exception):
  """ Bad Argument given for a function
  """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value
  def __str__(self):
    return repr(self.value)

class BadRequest(Exception):
  """ Indicates that a client provided invalid parameters for a request. """
  pass

class ConcurrentModificationException(Exception):
  """ Indicates that an entity fetched during a transaction has changed. """
  pass

class InternalError(Exception):
  """ Indicates that the datastore was unable to perform an operation. """
  pass

class NeedsIndex(Exception):
  """ Indicates that a required index is missing or incomplete. """
  pass

class Timeout(Exception):
  """ Indicates that the datastore timed out while performing an operation. """
  pass

class TooManyGroupsException(Exception):
  """ Indicates that there are too many groups involved in a transaction. """
  pass

class ExcessiveTasks(Exception):
  """ Indicates that there are too many tasks for a transaction. """
  pass

class TxTimeoutException(Exception):
  """ Indicates that the transaction started too long ago. """
  pass
