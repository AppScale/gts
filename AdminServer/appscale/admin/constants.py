""" Constants used by AdminServer. """

import os

from appscale.common.constants import (
  DASHBOARD_APP_ID,
  PYTHON27,
  JAVA,
  GO,
  PHP
)
from tornado.web import HTTPError


class CustomHTTPError(HTTPError):
  """ An HTTPError that keeps track of keyword arguments. """
  def __init__(self, status_code=500, **kwargs):
    # Pass standard HTTPError arguments along.
    log_message = kwargs.get('log_message', None)
    reason = kwargs.get('reason', None)
    super(CustomHTTPError, self).__init__(status_code, log_message=log_message,
                                          reason=reason)
    self.kwargs = kwargs


class AccessTokenErrors:
  INVALID_REQUEST = 'invalid_request'
  INVALID_CLIENT = 'invalid_client'
  INVALID_GRANT = 'invalid_grant'
  INVALID_SCOPE = 'invalid_scope'
  UNAUTHORIZED_CLIENT = 'unauthorized_client'
  UNSUPPORTED_GRANT_TYPE = 'unsupported_grant_type'


class Methods(object):
  """ The methods handled by the Admin API. """
  DELETE_PROJECT = 'google.appengine.v1.Projects.DeleteProject'
  DELETE_SERVICE = 'google.appengine.v1.Services.DeleteService'
  CREATE_VERSION = 'google.appengine.v1.Versions.CreateVersion'
  DELETE_VERSION = 'google.appengine.v1.Versions.DeleteVersion'
  UPDATE_VERSION = 'google.appengine.v1.Versions.UpdateVersion'


class OperationTimeout(Exception):
  """ Indicates that an operation has taken too long. """
  pass


class InvalidSource(Exception):
  """ Indicates that a revision's source code is invalid. """
  pass


class VersionNotChanged(Exception):
  """ Indicates that the version node was not updated. """
  pass


class NoPortsAvailable(Exception):
  """ Indicates that the service exhausted available ports. """
  pass


class ServingStatus(object):
  """ The possible serving states for a project or version. """
  SERVING = 'SERVING'
  STOPPED = 'STOPPED'


class Types(object):
  """ Resource types used in the Admin API. """
  BAD_REQUEST = 'type.googleapis.com/google.rpc.BadRequest'
  EMPTY = 'type.googleapis.com/google.protobuf.Empty'
  OPERATION_METADATA = 'type.googleapis.com/google.appengine.v1.OperationMetadataV1'
  VERSION = 'type.googleapis.com/google.appengine.v1.Version'


# The parent directory for source code extraction.
UNPACK_ROOT = os.path.join('/', 'var', 'apps')

# The ZooKeeper node that keeps track of the head node's state.
CONTROLLER_STATE_NODE = '/appcontroller/state'

# The default port for the AdminServer.
DEFAULT_PORT = 17442

# The default version for a service.
DEFAULT_VERSION = 'v1'

# The default service.
DEFAULT_SERVICE = 'default'

# The number of seconds to wait before giving up on an operation.
MAX_OPERATION_TIME = 120

# Supported runtimes.
VALID_RUNTIMES = {PYTHON27, JAVA, GO, PHP}

# The seconds to wait for redeploys.
REDEPLOY_WAIT = 20

# A list of projects that cannot be modified by users.
IMMUTABLE_PROJECTS = [DASHBOARD_APP_ID]

# The directory where source archives are stored.
SOURCES_DIRECTORY = os.path.join('/', 'opt', 'appscale', 'apps')

# The inbound services that are supported.
SUPPORTED_INBOUND_SERVICES = ('INBOUND_SERVICE_WARMUP',
                              'INBOUND_SERVICE_XMPP_MESSAGE',
                              'INBOUND_SERVICE_XMPP_SUBSCRIBE',
                              'INBOUND_SERVICE_XMPP_PRESENCE')

# The ZooKeeper location for storing project details.
PROJECT_NODE_TEMPLATE = '/appscale/projects/{}'

# The ZooKeeper location for storing version details.
VERSION_NODE_TEMPLATE = ('/appscale/projects/{project_id}'
                         '/services/{service_id}/versions/{version_id}')

# The ZooKeeper node that prevents concurrent location assignments.
VERSION_UPDATE_LOCK_NODE = '/appscale/version_update_lock'

# The ranges to use for automatically assigned ports.
AUTO_HTTP_PORTS = range(8080, 8100)
AUTO_HTTPS_PORTS = range(4380, 4400)

# The ports that can be assigned to versions.
ALLOWED_HTTP_PORTS = [80, 1080] + list(AUTO_HTTP_PORTS)
ALLOWED_HTTPS_PORTS = [443, 1443] + list(AUTO_HTTPS_PORTS)

# The range of HAProxy ports to assign to versions.
HAPROXY_PORTS = range(10000, 10020)

BOOKED_PORTS = set(
  list(ALLOWED_HTTP_PORTS)
  + list(ALLOWED_HTTPS_PORTS)
  + list(HAPROXY_PORTS)
  + [
    2181,     # Zookeeper
    2812,     # Monit
    3306,     # MySQL
    4341,     # UserAppServer service
    4342,     # UserAppServer server
    5222,     # ejabberd
    5432,     # PostgreSQL
    5555,     # Celery Flower
    6106,     # Blobstore service
    8888,     # Datastore service
    9999,     # Search service
    17441,    # AdminServer
    17443,    # AppController
    17446,    # TaskQueue service
  ]
  # list(range(4000, 5999))    # service_manager manages Datastore servers
  + list(range(6107, 7107))    # Blobstore servers (up to 1000 instances)
  + list(range(10000, 10100))  # Application ports
  + list(range(17447, 18447))  # TaskQueue servers (up to 1000 instances)
  + list(range(20000, 25000))  # Application server ports
  # list(range(31000, 32000))  # service_manager manages Search servers
)
