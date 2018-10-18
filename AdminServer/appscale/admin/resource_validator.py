""" Validation for Admin API REST resources
"""

import json
import pkgutil

from jsonschema import (
  validate,
  RefResolutionError,
  RefResolver,
  ValidationError
)

VERSION_SCHEMA = 'version'
SCHEMA_FILE_SUFFIX = '.schema.json'
SCHEMAS = {}
RESOLVERS = {}


class ResourceValidationError(Exception):
  """ Resource validation failed, message has details. """
  pass


class LocalOnlyRefResolver(RefResolver):
  """
  JSON Schema ref resolver that will not attempt to fetch remote documents
  """

  def resolve_remote(self, uri):
    """
    Fail on any attempt to resolve a remote uri.
    """
    raise RefResolutionError("Not resolving uri: {}".format(uri))


def _schema_filename(name):
  return name + SCHEMA_FILE_SUFFIX


def _schema(name):
  schema = SCHEMAS.get(name, None)
  if not schema:
    schema_data = pkgutil.get_data(__name__, _schema_filename(name))
    schema = json.loads(schema_data)
    SCHEMAS[name] = schema
  return schema


def _resolver(name):
  schema_resolver = RESOLVERS.get(name, None)
  if not schema_resolver:
    schema_resolver = LocalOnlyRefResolver.from_schema(_schema(name))
    RESOLVERS[name] = schema_resolver
  return schema_resolver


def validate_resource(resource, resource_type):
  """
  Validate the given resource using the validator for the type
  :param resource: The resource object to validate
  :param resource_type: The type of the resource being validated
  """
  try:
    validate(resource, _schema(resource_type),
             resolver=_resolver(resource_type))
  except ValidationError as e:
    schema_message = '{} at {}'.format(e.message, '.'.join(e.path))
    raise ResourceValidationError(schema_message)
