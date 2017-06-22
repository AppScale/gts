""" Structures for keeping track of Admin API operations. """

import datetime
import uuid

from .constants import Methods
from .constants import ServingStatus
from .constants import Types


class Operation(object):
  """ A parent class for keeping track of particular operations. """

  def __init__(self, project_id, service_id, version):
    """ Creates a new CreateVersionOperation.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing verision details.
    """
    self.project_id = project_id
    self.service_id = service_id
    self.version = version

    self.id = str(uuid.uuid4())
    self.start_time = datetime.datetime.utcnow()
    self.done = False
    self.response = None
    self.error = None
    self.method = None

  def set_error(self, message):
    """ Marks the operation as failed.

    Args:
      message: A string specifying the reason the operation failed.
    """
    self.done = True
    self.error = {'message': message}

  def rest_repr(self):
    """ Formats the operation for a REST API response.

    Returns:
      A dictionary containing operation details.
    """
    output = {
      'name': 'apps/{}/operations/{}'.format(self.project_id, self.id),
      'metadata': {
        '@type': Types.OPERATION_METADATA,
        'method': self.method,
        'insertTime': self.start_time.isoformat() + 'Z',
        'target': 'apps/{}/services/{}/versions/{}'.format(
          self.project_id, self.service_id, self.version['id'])
      },
      'done': self.done
    }

    if self.error is not None:
      output['error'] = self.error

    if self.response is not None:
      output['response'] = self.response

    return output


class CreateVersionOperation(Operation):
  """ A container that keeps track of CreateVersion operations. """
  def __init__(self, project_id, service_id, version):
    """ Creates a new CreateVersionOperation.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing verision details.
    """
    super(CreateVersionOperation, self).__init__(
      project_id, service_id, version)
    self.method = Methods.CREATE_VERSION

  def finish(self, url):
    """ Marks the operation as completed.

    Args:
      url: A string specifying the location of the version.
    """
    create_time = datetime.datetime.utcnow()
    self.response = {
      '@type': Types.VERSION,
      'name': 'apps/{}/services/{}/versions/{}'.format(
        self.project_id, self.service_id, self.version['id']),
      'id': self.version['id'],
      'runtime': self.version['runtime'],
      'servingStatus': ServingStatus.SERVING,
      'createTime': create_time.isoformat() + 'Z',
      'versionUrl': url
    }

    if 'threadsafe' in self.version:
      self.response['threadsafe'] = self.version['threadsafe']

    self.done = True


class DeleteVersionOperation(Operation):
  """ A container that keeps track of DeleteVersion operations. """

  def __init__(self, project_id, service_id, version):
    """ Creates a new CreateVersionOperation.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing verision details.
    """
    super(DeleteVersionOperation, self).__init__(
      project_id, service_id, version)
    self.method = Methods.DELETE_VERSION

  def finish(self):
    """ Marks the operation as completed. """
    self.response = {'@type': Types.EMPTY}
    self.done = True


class UpdateVersionOperation(Operation):
  """ A container that keeps track of UpdateVersion operations. """

  def __init__(self, project_id, service_id, version):
    """ Creates a new UpdateVersionOperation.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing verision details.
    """
    super(UpdateVersionOperation, self).__init__(
      project_id, service_id, version)
    self.method = Methods.UPDATE_VERSION
