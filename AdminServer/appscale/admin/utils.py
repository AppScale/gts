""" Utility functions used by the AdminServer. """

from appscale.common.constants import HTTPCodes
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
      missing_fields.append(field)

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
