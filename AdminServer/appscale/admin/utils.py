""" Utility functions used by the AdminServer. """

import errno
import json
import hmac
import logging
import os
import shutil
import socket
import tarfile

from appscale.common.constants import HTTPCodes
from appscale.common.constants import VERSION_PATH_SEPARATOR
from kazoo.exceptions import NoNodeError

from .constants import (
  AUTO_HTTP_PORTS,
  AUTO_HTTPS_PORTS,
  CustomHTTPError,
  HAPROXY_PORTS,
  GO,
  InvalidCronConfiguration,
  InvalidQueueConfiguration,
  InvalidSource,
  JAVA,
  JAVA8,
  REQUIRED_PULL_QUEUE_FIELDS,
  REQUIRED_PUSH_QUEUE_FIELDS,
  SOURCES_DIRECTORY,
  SUPPORTED_PULL_QUEUE_FIELDS,
  SUPPORTED_PUSH_QUEUE_FIELDS,
  Types,
  UNPACK_ROOT,
  VERSION_NODE_TEMPLATE
)
from .instance_manager.utils import copy_modified_jars
from .instance_manager.utils import remove_conflicting_jars

logger = logging.getLogger(__name__)


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


def version_contains_field(version, field):
  """ Checks if the given dictionary contains the given field.

  Args:
    version: A dictionary containing version details.
    field: A string representing a key path.
  Returns:
    A boolean indicating whether or not the version contains the field.
  """
  version_fragment = version
  for field_part in field.split('.'):
    try:
      version_fragment = version_fragment[field_part]
    except KeyError:
      return False

  return True


def apply_mask_to_version(given_version, desired_fields):
  """ Reduces a version to the desired fields.

  Example:
    given_version: {'runtime': 'python27',
                    'appscaleExtensions': {'httpPort': 80}}
    desired_fields: ['appscaleExtensions.httpPort']
    output: {'appscaleExtensions': {'httpPort': 80}}

  Args:
    given_version: A dictionary containing version details.
    desired_fields: A list of strings representing key paths.
  Returns:
    A dictionary containing some version details.
  """
  masked_version = {}
  for field in desired_fields:
    if not version_contains_field(given_version, field):
      continue

    given_version_part = given_version
    masked_version_part = masked_version
    field_parts = field.split('.')
    for index, field_part in enumerate(field_parts):
      if field_part not in masked_version_part:
        if index == (len(field_parts) - 1):
          masked_version_part[field_part] = given_version_part[field_part]
        elif isinstance(given_version_part[field_part], dict):
          masked_version_part[field_part] = {}
        elif isinstance(given_version_part[field_part], list):
          masked_version_part[field_part] = []

      given_version_part = given_version_part[field_part]
      masked_version_part = masked_version_part[field_part]

  return masked_version


def canonical_path(path, base=os.curdir):
  """ Resolves a path, following symlinks.

  Args:
    path: A string specifying a file system location.
    base: The path against which to resolve relative paths.
  Returns:
    A string specifying a file system location.
  """
  return os.path.realpath(os.path.abspath(os.path.join(base, path)))


def valid_link(link_name, link_target, base):
  """ Checks if a link points to a location that resides within base.

  Args:
    link_name: A string specifying the location of the link.
    link_target: A string specifying the target of the link.
    base: A string specifying the root path of the archive.
  Returns:
    A boolean indicating whether or not the link is valid.
  """
  tip = canonical_path(os.path.dirname(link_name), base)
  target = canonical_path(os.path.join(tip, link_target), base)
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


def extract_source(revision_key, location, runtime):
  """ Unpacks an archive from a given location.

  Args:
    revision_key: A string specifying the revision key.
    location: A string specifying the location of the source archive.
    runtime: A string specifying the revision's runtime.
  Raises:
    IOError if version source archive does not exist.
    InvalidSource if the source archive is not valid.
  """
  revision_base = os.path.join(UNPACK_ROOT, revision_key)
  ensure_path(os.path.join(revision_base, 'log'))

  app_path = os.path.join(revision_base, 'app')
  ensure_path(app_path)

  if runtime in (JAVA, JAVA8):
    config_file_name = 'appengine-web.xml'

    def is_version_config(path):
      return path.endswith(config_file_name)
  else:
    config_file_name = 'app.yaml'

    def is_version_config(path):
      return canonical_path(path, app_path) == \
             os.path.join(app_path, config_file_name)

  with tarfile.open(location, 'r:gz') as archive:
    # Check if the archive is valid before extracting it.
    has_config = False
    for file_info in archive:
      file_name = file_info.name
      if not canonical_path(file_name, app_path).startswith(app_path):
        raise InvalidSource(
          'Invalid location in archive: {}'.format(file_name))

      if file_info.issym() or file_info.islnk():
        if not valid_link(file_name, file_info.linkname, app_path):
          raise InvalidSource('Invalid link in archive: {}'.format(file_name))

      if is_version_config(file_name):
        has_config = True

    if not has_config:
      raise InvalidSource('Archive must have {}'.format(config_file_name))

    archive.extractall(path=app_path)

  if runtime == GO:
    try:
      shutil.move(os.path.join(app_path, 'gopath'), revision_base)
    except IOError:
      logger.debug(
        '{} does not have a gopath directory'.format(revision_key))

  if runtime == JAVA:
    remove_conflicting_jars(app_path)
    copy_modified_jars(app_path)


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


def rename_source_archive(project_id, service_id, version):
  """ Renames the given source archive to keep track of it.

  Args:
    project_id: A string specifying a project ID.
    service_id: A string specifying a service ID.
    version: A dictionary containing version details.
  Returns:
    A string specifying the new location of the archive.
  """
  new_filename = VERSION_PATH_SEPARATOR.join(
    [project_id, service_id, version['id'],
     '{}.tar.gz'.format(version['revision'])])
  new_location = os.path.join(SOURCES_DIRECTORY, new_filename)
  os.rename(version['deployment']['zip']['sourceUrl'], new_location)
  return new_location


def remove_old_archives(project_id, service_id, version):
  """ Cleans up old revision archives.

  Args:
    project_id: A string specifying a project ID.
    service_id: A string specifying a service ID.
    version: A dictionary containing version details.
  """
  prefix = VERSION_PATH_SEPARATOR.join(
    [project_id, service_id, version['id']])
  current_name = os.path.basename(version['deployment']['zip']['sourceUrl'])
  old_sources = [os.path.join(SOURCES_DIRECTORY, archive) for archive
                 in os.listdir(SOURCES_DIRECTORY)
                 if archive.startswith(prefix) and archive < current_name]
  for archive in old_sources:
    os.remove(archive)


def assigned_locations(zk_client):
  """ Discovers the locations assigned for all existing versions.

  Args:
    zk_client: A KazooClient.
  Returns:
    A set containing used ports.
  """
  try:
    project_nodes = [
      '/appscale/projects/{}'.format(project)
      for project in zk_client.get_children('/appscale/projects')]
  except NoNodeError:
    project_nodes = []

  service_nodes = []
  for project_node in project_nodes:
    project_id = project_node.split('/')[3]
    try:
      new_service_ids = zk_client.get_children(
        '{}/services'.format(project_node))
    except NoNodeError:
      continue
    service_nodes.extend([
      '/appscale/projects/{}/services/{}'.format(project_id, service_id)
      for service_id in new_service_ids])

  version_nodes = []
  for service_node in service_nodes:
    project_id = service_node.split('/')[3]
    service_id = service_node.split('/')[5]
    try:
      new_version_ids = zk_client.get_children(
        '{}/versions'.format(service_node))
    except NoNodeError:
      continue
    version_nodes.extend([
      VERSION_NODE_TEMPLATE.format(
        project_id=project_id, service_id=service_id, version_id=version_id)
      for version_id in new_version_ids])

  locations = set()
  for version_node in version_nodes:
    try:
      version = json.loads(zk_client.get(version_node)[0])
    except NoNodeError:
      continue

    # Extensions and ports should always be defined when written to a node.
    extensions = version['appscaleExtensions']
    locations.add(extensions['httpPort'])
    locations.add(extensions['httpsPort'])
    locations.add(extensions['haproxyPort'])

  return locations


def assign_ports(old_version, new_version, zk_client):
  """ Assign ports for a version.

  Args:
    old_version: A dictionary containing version details.
    new_version: A dictionary containing version details.
    zk_client: A KazooClient.
  Returns:
    A dictionary specifying the ports to reserve for the version.
  """
  old_extensions = old_version.get('appscaleExtensions', {})
  old_http_port = old_extensions.get('httpPort')
  old_https_port = old_extensions.get('httpsPort')
  haproxy_port = old_extensions.get('haproxyPort')

  new_extensions = new_version.get('appscaleExtensions', {})
  new_http_port = new_extensions.get('httpPort')
  new_https_port = new_extensions.get('httpsPort')

  # If this is not the first revision, and the client did not request
  # particular ports, just use the ports from the last revision.
  if old_http_port is not None and new_http_port is None:
    new_http_port = old_http_port

  if old_https_port is not None and new_https_port is None:
    new_https_port = old_https_port

  # If the ports have not changed, do not check for conflicts.
  if (new_http_port == old_http_port and new_https_port == old_https_port and
      haproxy_port is not None):
    return {'httpPort': new_http_port, 'httpsPort': new_https_port,
            'haproxyPort': haproxy_port}

  taken_locations = assigned_locations(zk_client)

  # Consider the version's old ports as available.
  taken_locations.discard(old_http_port)
  taken_locations.discard(old_https_port)

  # If ports were requested, make sure they are available.
  if new_http_port is not None and new_http_port in taken_locations:
    raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                          message='Requested httpPort is already taken')

  if new_https_port is not None and new_https_port in taken_locations:
    raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                          message='Requested httpsPort is already taken')

  if new_http_port is None:
    try:
      new_http_port = next(port for port in AUTO_HTTP_PORTS
                           if port not in taken_locations)
    except StopIteration:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Unable to find HTTP port for version')

  if new_https_port is None:
    try:
      new_https_port = next(port for port in AUTO_HTTPS_PORTS
                            if port not in taken_locations)
    except StopIteration:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Unable to find HTTPS port for version')

  if haproxy_port is None:
    try:
      haproxy_port = next(port for port in HAPROXY_PORTS
                          if port not in taken_locations)
    except StopIteration:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Unable to find HAProxy port for version')

  return {'httpPort': new_http_port, 'httpsPort': new_https_port,
          'haproxyPort': haproxy_port}


def validate_job(job):
  """ Checks if a cron job configuration is valid.

  Args:
    job: A dictionary containing cron job configuration details.
  Raises:
    InvalidCronConfiguration if configuration is invalid.
  """
  required_fields = ('schedule', 'url')
  supported_fields = ('description', 'schedule', 'url', 'target')

  for field in required_fields:
    if field not in job:
      raise InvalidCronConfiguration(
        'Cron job is missing {}: {}'.format(field, job))

  for field in job:
    if field not in supported_fields:
      raise InvalidCronConfiguration('{} is not supported'.format(field))


def validate_queue(queue):
  """ Checks if a queue configuration is valid.

  Args:
    queue: A dictionary containing queue configuration details.
  Raises:
    InvalidQueueConfiguration if configuration is invalid.
  """
  mode = queue.get('mode', 'push')

  if mode not in ['push', 'pull']:
    raise InvalidQueueConfiguration('Invalid queue mode: {}'.format(mode))

  if mode == 'push':
    required_fields = REQUIRED_PUSH_QUEUE_FIELDS
    supported_fields = SUPPORTED_PUSH_QUEUE_FIELDS
  else:
    required_fields = REQUIRED_PULL_QUEUE_FIELDS
    supported_fields = SUPPORTED_PULL_QUEUE_FIELDS

  for field in required_fields:
    if field not in queue:
      raise InvalidQueueConfiguration(
        'Queue is missing {}: {}'.format(field, queue))

  for field in queue:
    value = queue[field]
    try:
      rule = supported_fields[field]
    except KeyError:
      raise InvalidQueueConfiguration('{} is not supported'.format(field))

    if isinstance(rule, dict):
      required_sub_fields = rule
      for sub_field in value:
        sub_value = value[sub_field]
        try:
          sub_rule = required_sub_fields[sub_field]
        except KeyError:
          raise InvalidQueueConfiguration(
            '{}.{} is not supported'.format(field, sub_field))

        if not sub_rule(sub_value):
          raise InvalidQueueConfiguration(
            'Invalid {}.{} value: {}'.format(field, sub_field, sub_value))
    elif not rule(value):
      raise InvalidQueueConfiguration(
        'Invalid {} value: {}'.format(field, value))


def cron_from_dict(payload):
  """ Validates and prepares a project's cron configuration.

  Args:
    payload: A dictionary containing cron configuration.
  Returns:
    A dictionary containing cron information.
  Raises:
    InvalidCronConfiguration if configuration is invalid.
  """
  try:
    given_jobs = payload['cron']
  except KeyError:
    raise InvalidCronConfiguration('Payload must contain cron directive')

  for directive in payload:
    # There are no other directives in the GAE docs. This check is in case more
    # are added later.
    if directive != 'cron':
      raise InvalidCronConfiguration('{} is not supported'.format(directive))

  for job in given_jobs:
    validate_job(job)

  return payload


def queues_from_dict(payload):
  """ Validates and prepares a project's queue configuration.

  Args:
    payload: A dictionary containing queue configuration.
  Returns:
    A dictionary containing queue information.
  Raises:
    InvalidQueueConfiguration if configuration is invalid.
  """
  try:
    given_queues = payload['queue']
  except KeyError:
    raise InvalidQueueConfiguration('Payload must contain queue directive')

  for directive in payload:
    # total_storage_limit is not yet supported.
    if directive != 'queue':
      raise InvalidQueueConfiguration('{} is not supported'.format(directive))

  queues = {'default': {'mode': 'push', 'rate': '5/s'}}
  for queue in given_queues:
    validate_queue(queue)
    name = queue.pop('name')
    queues[name] = queue

  return {'queue': queues}


def _constant_time_compare(val_a, val_b):
  """ Compares the two input values in a way that prevents timing analysis.

  Args:
    val_a: A string.
    val_b: A string.
  Returns:
    A boolean indicating whether or not the given strings are equal.
  """
  if len(val_a) != len(val_b):
    return False

  values_equal = True
  for char_a, char_b in zip(val_a, val_b):
    if char_a != char_b:
      # Do not break early here in order to keep the compare constant time.
      values_equal = False

  return values_equal


if hasattr(hmac, 'compare_digest'):
  constant_time_compare = hmac.compare_digest
else:
  constant_time_compare = _constant_time_compare
