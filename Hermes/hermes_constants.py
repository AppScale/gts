""" Constants that are used for Hermes functionality (backup/restore/etc.). """

# The port br_service listens to.
BR_SERVICE_PORT = "8423"

# The br_service path for starting a new task.
BR_SERVICE_PATH = "/"

# The suffix for backup files from a DB master node.
DB_MASTER_OBJECT_NAME = '/cassandra/db_master.tar.gz'

# Enable DEBUG logging.
DEBUG = False

# The suffix for backup files from a DB slave node.
# The slave ID is populated at runtime.
DB_SLAVE_OBJECT_NAME = '/cassandra/db_slave_{0}.tar.gz'

# The suffix for backup files from a ZK node.
# The zk ID is populated at runtime.
ZK_OBJECT_NAME = '/zookeeper/zk_node_{0}.tar.gz'

# The port Hermes listens to.
HERMES_PORT = "4378"

# The URL for Hermes web server.
HERMES_URL = "http://localhost:{0}".format(HERMES_PORT)

# A constant representing the Tornado HTTPError.
HTTPError = 'HTTPError'

# The interval between polls for new tasks.
POLLING_INTERVAL = 60000

# The AppScale Portal URL for getting new tasks.
PORTAL_URL = "https://portal.appscale.com"

# The AppScale Portal path for getting new tasks.
PORTAL_POLL_PATH = "/get_appscale_task"

# The AppScale Portal path for reporting task status.
PORTAL_STATUS_PATH = "/report_appscale_task"

# A list of required parameters that define a task.
REQUIRED_KEYS = ['task_id', 'type', 'bucket_name', 'storage']

# The amount of time to wait for a node backup in seconds.
REQUEST_TIMEOUT = 12*60*60

class HTTP_Codes(object):
  """ A class with HTTP status codes. """
  HTTP_OK = 200
  HTTP_DENIED = 403
  HTTP_INTERNAL_ERROR = 500
  HTTP_NOT_IMPLEMENTED = 501

class TaskTypes(object):
  """ A class containing supported task types. """
  CASSANDRA_BACKUP = 'cassandra_backup'
  ZOOKEEPER_BACKUP = 'zookeeper_backup'

  CASSANDRA_RESTORE = 'cassandra_restore'
  ZOOKEEPER_RESTORE = 'zookeeper_restore'
