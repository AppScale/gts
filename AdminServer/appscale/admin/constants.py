""" Constants used by AdminServer. """

from appscale.common.constants import (
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


class Methods(object):
  """ The methods handled by the Admin API. """
  CREATE_VERSION = 'google.appengine.v1.Versions.CreateVersion'


class OperationTimeout(Exception):
  """ Indicates that an operation has taken too long. """
  pass


class ServingStatus(object):
  """ The possible serving states for a project or version. """
  SERVING = 'SERVING'
  STOPPED = 'STOPPED'


class Types(object):
  """ Resource types used in the Admin API. """
  BAD_REQUEST = 'type.googleapis.com/google.rpc.BadRequest'
  OPERATION_METADATA = 'type.googleapis.com/google.appengine.v1.OperationMetadataV1'
  VERSION = 'type.googleapis.com/google.appengine.v1.Version'


# The default port for the AdminServer.
DEFAULT_PORT = 17442

# The default version for a service.
DEFAULT_VERSION = 'default'

# The default service.
DEFAULT_SERVICE = 'default'

# The number of seconds to wait before giving up on a deployment operation.
MAX_DEPLOY_TIME = 100

# Supported runtimes.
VALID_RUNTIMES = {PYTHON27, JAVA, GO, PHP}

# The seconds to wait for redeploys.
REDEPLOY_WAIT = 20
