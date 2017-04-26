""" Utility functions used by the AdminServer. """

from appscale.common.constants import HTTPCodes
from tornado.options import options
from .constants import CustomHTTPError
from .constants import Types


def assert_fields_in_resource(required_fields, resource_name, resource):
  """ Ensures the resource contains the required fields.

  Args:
    required_fields: An iterable specifying the required fields.
    resource_name: A string specifying the resource name.
    resource: A dictionary containing the resource details.
  Raises:
    CustomHTTPError if there are missing fields.
  """
  def missing_field(prefix, group, resource_part):
    field_name = group.pop(0)
    if field_name not in resource_part:
      return '.'.join([prefix, field_name])

    if not group:
      return

    prefix += '.{}'.format(field_name)
    return missing_field(prefix, group, resource_part[field_name])

  missing_fields = []
  for group in required_fields:
    field = missing_field(resource_name, group.split('.'), resource)
    if field is not None:
      missing_fields.append(missing_field)

  if not missing_fields:
    return

  message = 'The request is invalid.'
  description = 'This field is required.'

  if len(missing_fields) == 1:
    message = '{}: {}'.format(missing_fields[0], description)

  violations = [{'field': field, 'description': description}
                for field in missing_fields]

  raise CustomHTTPError(
    HTTPCodes.BAD_REQUEST,
    message=message,
    status='INVALID_ARGUMENT',
    details=[{'@type': Types.BAD_REQUEST, 'fieldViolations': violations}])


def format_operation(operation):
  """ Formats an operation for the client.

  Args:
    operation: A dictionary containing operation details.
  Returns:
    A dictionary containing operation details.
  """
  output = {
    'name': 'apps/{}/operations/{}'.format(operation['project_id'],
                                           operation['id']),
    'metadata': {
      '@type': Types.OPERATION_METADATA,
      'method': operation['method'],
      'insertTime': operation['start_time'].isoformat() + 'Z',
      'target': 'apps/{}/services/{}/versions/{}'.format(
        operation['project_id'], operation['service_id'],
        operation['version_id'])
    },
    'done': operation['done']
  }

  if 'error' in operation:
    output['error'] = operation['error']

  if 'response' in operation:
    output['response'] = operation['response']

  return output


def format_version(operation, status, create_time, http_port):
  """ Formats a version for the client.

  Args:
    operation: A dictionary containing operation details.
    status: A string specifying the serving status of the version.
    create_time: A datetime object specifying the time the version was created.
    http_port: An integer specifying the version's serving port.
  Returns:
    A dictionary containing version details.
  """
  project_id = operation['project_id']
  service_id = operation['service_id']
  version_id = operation['version_id']

  output = {
    '@type': Types.VERSION,
    'name': 'apps/{}/services/{}/versions/{}'.format(project_id, service_id,
                                                     version_id),
    'id': version_id,
    'runtime': operation['runtime'],
    'servingStatus': status,
    'createTime': create_time.isoformat() + 'Z',
    'versionUrl': 'http://{}:{}'.format(options.login_ip, http_port)
  }

  if 'threadsafe' in operation:
    output['threadsafe'] = operation['threadsafe']

  return output
