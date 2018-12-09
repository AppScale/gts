""" Constants used by AdminServer. """

import os

from appscale.common.constants import (
  DASHBOARD_APP_ID,
  PYTHON27,
  JAVA,
  JAVA8,
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

# The default port for the AdminServer.
DEFAULT_PORT = 17442

# The default version for a service.
DEFAULT_VERSION = 'v1'

# The default service.
DEFAULT_SERVICE = 'default'

# The number of seconds to wait before giving up on an operation.
MAX_OPERATION_TIME = 120

# Supported runtimes.
VALID_RUNTIMES = {PYTHON27, JAVA, JAVA8, GO, PHP}

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
