""" Utility functions used by the AdminServer. """

import errno
import logging
import os
import shutil
import socket
import tarfile

from appscale.common.constants import HTTPCodes
from .constants import (
  CustomHTTPError,
  GO,
  JAVA,
  Types,
  UNPACK_ROOT
)


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


def canonical_path(path):
  """ Resolves a path, following symlinks.

  Args:
    path: A string specifying a file system location.
  Returns:
    A string specifying a file system location.
  """
  return os.path.realpath(os.path.abspath(path))


def valid_link(link_name, link_target, base):
  """ Checks if a link points to a location that resides within base.

  Args:
    link_name: A string specifying the location of the link.
    link_target: A string specifying the target of the link.
    base: A string specifying the root path of the archive.
  Returns:
    A boolean indicating whether or not the link is valid.
  """
  tip = canonical_path(os.path.join(base, os.path.dirname(link_name)))
  target = canonical_path(os.path.join(tip, link_target))
  return target.startswith(base)


def ensure_path(path):
  """ Ensures directory exists.

  Args:
    path: A string specifying the path to ensure.
  """
  try:
    os.makedirs(os.path.join(path))
  except OSError as os_error:
    if os_error.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else:
      raise


def extract_source(version, project_id):
  """ Unpacks an archive to a given location.

  Args:
    version: A dictionary containing version details.
    project_id: A string specifying a project ID.
  Raises:
    IOError if version source archive does not exist
  """
  project_base = os.path.join(UNPACK_ROOT, project_id)
  shutil.rmtree(project_base, ignore_errors=True)
  ensure_path(os.path.join(project_base, 'log'))

  app_path = os.path.join(project_base, 'app')
  ensure_path(app_path)
  # The working directory must be the target in order to validate paths.
  os.chdir(app_path)

  source_path = version['deployment']['zip']['sourceUrl']
  with tarfile.open(source_path, 'r:gz') as archive:
    # Check if the archive is valid before extracting it.
    has_config = False
    for file_info in archive:
      file_name = file_info.name
      if not canonical_path(file_name).startswith(app_path):
        message = 'Invalid location in archive: {}'.format(file_name)
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

      if file_info.issym() or file_info.islnk():
        if not valid_link(file_name, file_info.linkname, app_path):
          message = 'Invalid link in archive: {}'.format(file_name)
          raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

      if version['runtime'] == JAVA:
        if file_name.endswith('appengine-web.xml'):
          has_config = True
      else:
        if canonical_path(file_name) == os.path.join(app_path, 'app.yaml'):
          has_config = True

    if not has_config:
      if version['runtime'] == JAVA:
        missing_file = 'appengine.web.xml'
      else:
        missing_file = 'app.yaml'
      message = 'Archive must have {}'.format(missing_file)
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    archive.extractall(path=app_path)

  if version['runtime'] == GO:
    try:
      shutil.move(os.path.join(app_path, 'gopath'), project_base)
    except IOError:
      logging.debug('{} does not have a gopath directory'.format(project_id))


def port_is_open(host, port):
  """ Checks if the given port is open.

  Args:
    host: A string specifying the location of the host.
    port: An integer specifying the port to check.
  Returns:
    A boolean indicating whether or not the port is open.
  """
  sock = socket.socket()
  result = sock.connect_ex((host, port))
  return result == 0
