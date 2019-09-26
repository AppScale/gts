""" A server that handles application deployments. """

import argparse
import base64
import errno
import hashlib
import json
import logging
import monotonic
import os
import re
import six
import sys
import time

try:
  from urllib import quote as urlquote
except ImportError:
  from urllib.parse import quote as urlquote

import requests_unixsocket

from appscale.common import appscale_info
from appscale.common.constants import (
  HTTPCodes,
  LOG_FORMAT,
  VERSION_PATH_SEPARATOR,
  ZK_PERSISTENT_RECONNECTS
)
from appscale.common.service_helper import ServiceOperator
from appscale.common.appscale_utils import get_md5
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError
from kazoo.exceptions import NoNodeError
from kazoo.exceptions import NotEmptyError
from tabulate import tabulate
from tornado import gen
from tornado.options import options
from tornado import web
from tornado.escape import json_decode
from tornado.escape import json_encode
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.netutil import bind_unix_socket
from . import utils
from . import constants
from .appengine_api import UpdateCronHandler
from .appengine_api import UpdateIndexesHandler
from .appengine_api import UpdateQueuesHandler
from .base_handler import BaseHandler
from .constants import (
  CustomHTTPError,
  OperationTimeout,
  REDEPLOY_WAIT,
  ServingStatus,
  SUPPORTED_INBOUND_SERVICES,
  VALID_RUNTIMES,
  VersionNotChanged
)
from .controller_state import ControllerState
from .iam import ServiceAccountsHandler
from .operation import (
  DeleteServiceOperation,
  CreateVersionOperation,
  DeleteVersionOperation,
  UpdateVersionOperation,
  UpdateApplicationOperation
)
from .operations_cache import OperationsCache
from .push_worker_manager import GlobalPushWorkerManager
from .resource_validator import validate_resource, ResourceValidationError
from .routing.routing_manager import RoutingManager
from .service_manager import ServiceManager, ServiceManagerHandler
from .summary import get_services

logger = logging.getLogger(__name__)

# The state of each operation.
operations = OperationsCache()


@gen.coroutine
def wait_for_port_to_open(http_port, operation_id, timeout):
  """ Waits until port is open.

  Args:
    http_port: An integer specifying the version's port number.
    operation_id: A string specifying an operation ID.
    timeout: The number of seconds to wait.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  logger.debug('Waiting for {} to open'.format(http_port))
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  deadline = monotonic.monotonic() + timeout
  all_lbs = set(appscale_info.get_load_balancer_ips())
  passed_lbs = set()
  while True:
    for load_balancer in all_lbs:
      if load_balancer in passed_lbs or monotonic.monotonic() > deadline:
        continue

      if utils.port_is_open(load_balancer, http_port):
        passed_lbs.add(load_balancer)

    if len(passed_lbs) == len(all_lbs):
      break

    if monotonic.monotonic() > deadline:
      # If the version is reachable, but it's not reachable from every
      # registered load balancer. It makes more sense to mark the
      # operation as a success than a failure because the lagging load
      # balancers should eventually reflect the registered instances.
      if not passed_lbs:
        message = 'Deploy operation took too long.'
        operation.set_error(message)
        raise OperationTimeout(message)
      else:
        break

    yield gen.sleep(1)


@gen.coroutine
def wait_for_deploy(operation_id, controller_state):
  """ Tracks the progress of a deployment.

  Args:
    operation_id: A string specifying the operation ID.
    controller_state: A ControllerState object.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  http_port = operation.version['appscaleExtensions']['httpPort']
  yield wait_for_port_to_open(http_port, operation_id,
                              constants.MAX_OPERATION_TIME)

  login_host = options.login_ip
  if controller_state.options is not None:
    login_host = controller_state.options.get('login', login_host)

  url = 'http://{}:{}'.format(login_host, http_port)
  operation.finish(url)

  logger.info('Finished operation {}'.format(operation_id))


@gen.coroutine
def wait_for_delete(operation_id, ports_to_close):
  """ Tracks the progress of removing version(s).

  Args:
    operation_id: A string specifying the operation ID.
    ports_to_close: A list of integers specifying the ports to wait for.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  deadline = monotonic.monotonic() + constants.MAX_OPERATION_TIME

  finished = 0
  ports = ports_to_close[:]
  while True:
    if monotonic.monotonic() > deadline:
      message = 'Delete operation took too long.'
      operation.set_error(message)
      raise OperationTimeout(message)
    to_remove = []
    for http_port in ports:
      # If the port is open, continue to process other ports.
      if utils.port_is_open(options.login_ip, int(http_port)):
        continue
      # Otherwise one more port has finished and remove it from the list of
      # ports to check.
      finished += 1
      to_remove.append(http_port)
    ports = [p for p in ports if p not in to_remove]
    if finished == len(ports_to_close):
      break

    yield gen.sleep(1)

  operation.finish()


def update_project_state(zk_client, project_id, new_state):
  """ Method for updating a project and its state in zookeeper."""
  project_path = constants.PROJECT_NODE_TEMPLATE.format(project_id)
  state_json, _ = zk_client.get(project_path)
  if state_json:
    state = json.loads(state_json)
  else:
    state = {
      'projectId': project_id,
      'lifecycleState': new_state
    }
  state.update({'lifecycleState': LifecycleState.DELETE_REQUESTED})
  zk_client.set(project_path, json.dumps(state))


class LifecycleState(object):
  ACTIVE = 'ACTIVE'
  LIFECYCLE_STATE_UNSPECIFIED = 'LIFECYCLE_STATE_UNSPECIFIED'
  DELETE_REQUESTED = 'DELETE_REQUESTED'
  DELETE_IN_PROGRESS = 'DELETE_IN_PROGRESS'


class AppsHandler(BaseHandler):
  """ Manages applications. """
  def initialize(self, ua_client, zk_client):
    """ Defines required resources to handle requests.

    Args:
      ua_client: A UAClient.
      zk_client: A KazooClient.
    """
    self.ua_client = ua_client
    self.zk_client = zk_client


  @gen.coroutine
  def patch(self, project_id):
    """ Updates an Application. Currently this is only supported for the
    dispatch rules.

    Args:
      project_id: A string specifying a project ID.
    """
    self.authenticate(project_id, self.ua_client)

    if project_id in constants.IMMUTABLE_PROJECTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} cannot be updated'.format(project_id))

    update_mask = self.get_argument('updateMask', None)
    if not update_mask:
      message = 'At least one field must be specified for this operation.'
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    desired_fields = update_mask.split(',')
    supported_fields = {'dispatchRules'}
    for field in desired_fields:
      if field not in supported_fields:
        message = ('This operation is only supported on the following '
                   'field(s): [{}]'.format(', '.join(supported_fields)))
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    project_node = '/appscale/projects/{}'.format(project_id)
    services_node = '{}/services'.format(project_node)
    if not self.zk_client.exists(project_node):
      raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                            message='Project does not exist')

    try:
      service_ids = self.zk_client.get_children(services_node)
    except NoNodeError:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Services node not found for project')
    payload = json.loads(self.request.body)

    try:
      dispatch_rules = utils.routing_rules_from_dict(payload=payload,
                                                     services=service_ids)
    except utils.InvalidDispatchConfiguration as error:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error.message)

    dispatch_node = '/appscale/projects/{}/dispatch'.format(project_id)

    try:
      self.zk_client.set(dispatch_node, json.dumps(dispatch_rules))
    except NoNodeError:
      try:
        self.zk_client.create(dispatch_node, json.dumps(dispatch_rules))
      except NoNodeError:
        raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                              message='{} not found'.format(project_id))

    logger.info('Updated dispatch for {}'.format(project_id))
    # TODO: add verification for dispatchRules being applied. For now,
    # assume the controller picks it up instantly.
    patch_operation = UpdateApplicationOperation(project_id)
    patch_operation.finish(dispatch_rules)
    operations[patch_operation.id] = patch_operation
    self.write(json_encode(patch_operation.rest_repr()))



class BaseVersionHandler(BaseHandler):

  def get_version(self, project_id, service_id, version_id):
    """ Fetches a version node.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    Returns:
      A dictionary containing version details.
    """
    version_node = constants.VERSION_NODE_TEMPLATE.format(
      project_id=project_id, service_id=service_id, version_id=version_id)

    try:
      version_json = self.zk_client.get(version_node)[0]
    except NoNodeError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND, message='Version not found')

    return json.loads(version_json)

  @gen.coroutine
  def start_delete_version(self, project_id, service_id, version_id):
    """ Starts the process of deleting a version by deleting the version
    node. Returns the version's port that will be closing, the caller should
    wait for this port to close.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    Returns:
      The version's port.
    """
    version = self.get_version(project_id, service_id, version_id)
    try:
      http_port = int(version['appscaleExtensions']['httpPort'])
    except KeyError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                            message='Version serving port not found')

    version_node = constants.VERSION_NODE_TEMPLATE.format(
      project_id=project_id, service_id=service_id, version_id=version_id)

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      try:
        self.zk_client.delete(version_node)
      except NoNodeError:
        pass
    finally:
      self.version_update_lock.release()

    raise gen.Return(http_port)


class ProjectsHandler(BaseVersionHandler):
  """ Manages projects. """

  def initialize(self, acc, ua_client, zk_client, version_update_lock,
                 thread_pool):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      ua_client: A UAClient.
      zk_client: A KazooClient.
      version_update_lock: A kazoo lock.
      thread_pool: A ThreadPoolExecutor.
    """
    self.acc = acc
    self.ua_client = ua_client
    self.zk_client = zk_client
    self.version_update_lock = version_update_lock
    self.thread_pool = thread_pool

  @gen.coroutine
  def get(self):
    """ List projects.
    """
    if 'AppScale-Secret' not in self.request.headers:
      # Run all the authenticate functions in authenticate_access_token but
      # don't check if user is authenticated for a specific project,
      # get projects user can access.
      try:
        token = self.request.headers['Authorization'].split()[1]
      except IndexError:
        message = 'A required header is missing: Authorization'
        raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=message)
      method_base64, metadata_base64, signature = token.split('.')
      self.check_token_hash(method_base64, metadata_base64, signature)

      metadata = json.loads(base64.urlsafe_b64decode(metadata_base64))
      self.check_token_expiration(metadata)
      self.check_token_scope(metadata)
      user = metadata['user']
      try:
        is_user_cloud_admin = self.ua_client.is_user_cloud_admin(user)
      except UAException:
        message = 'Unable to determine user data for {}.'.format(user)
        raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

      if is_user_cloud_admin:
        projects = self.get_projects_from_zookeeper()
      else:
        projects = self.get_users_projects(user, self.ua_client)
    else:
      self.authenticate(project_id=None, ua_client=None)
      projects = self.get_projects_from_zookeeper()

    project_dicts = []
    for project in projects:
      project_json, metadata = self.zk_client.get(
        constants.PROJECT_NODE_TEMPLATE.format(project))
      project_dict = json.loads(project_json)
      created = datetime.fromtimestamp(metadata.ctime / 1000.0).isoformat() + 'Z'
      project_dict.update({'createTime': created})

      project_dicts.append(project_dict)

    self.write(json.dumps({'projects': project_dicts}))

  def get_projects_from_zookeeper(self):
    """ Wrapper function for getting list of projects from zookeeper. """
    try:
      return self.zk_client.get_children('/appscale/projects')
    except NoNodeError:
      return []


class ProjectHandler(BaseVersionHandler):
  """ Manages a project. """

  def initialize(self, acc, ua_client, zk_client, version_update_lock,
                 thread_pool):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      ua_client: A UAClient.
      zk_client: A KazooClient.
      version_update_lock: A kazoo lock.
      thread_pool: A ThreadPoolExecutor.
    """
    self.acc = acc
    self.ua_client = ua_client
    self.zk_client = zk_client
    self.version_update_lock = version_update_lock
    self.thread_pool = thread_pool

  @gen.coroutine
  def delete(self, project_id):
    """ Deletes a project.

    Args:
      project_id: The id of the project to delete.
    """
    self.authenticate(project_id, self.ua_client)
    raise CustomHTTPError(HTTPCodes.NOT_IMPLEMENTED,
                          message='Project deletion is not supported')


class ServicesHandler(BaseVersionHandler):
  """ Manages a project's services. """
  def initialize(self, ua_client, zk_client):
    self._ua_client = ua_client
    self._zk_client = zk_client

  def get(self, project_id):
    """ Lists all the services in a project. """
    self.authenticate(project_id, self._ua_client)
    project_node = '/'.join(['/appscale', 'projects', project_id])
    services_node = '/'.join([project_node, 'services'])
    if not self._zk_client.exists(project_node):
      raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                            message='Project does not exist')

    try:
      service_ids = self._zk_client.get_children(services_node)
    except NoNodeError:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Services node not found for project')

    prefix = '/'.join(['apps', project_id, 'services'])
    services = [{'name': '/'.join([prefix, service_id]), 'id': service_id}
                for service_id in service_ids]
    json.dump({'services': services}, self)


class ServiceHandler(BaseVersionHandler):
  def initialize(self, acc, ua_client, zk_client, version_update_lock,
                 thread_pool):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      ua_client: A UAClient.
      zk_client: A KazooClient.
      version_update_lock: A kazoo lock.
      thread_pool: A ThreadPoolExecutor.
    """
    self.acc = acc
    self.ua_client = ua_client
    self.zk_client = zk_client
    self.version_update_lock = version_update_lock
    self.thread_pool = thread_pool

  @gen.coroutine
  def delete(self, project_id, service_id):
    """ Deletes a service.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """
    self.authenticate(project_id, self.ua_client)
    service_path = '/appscale/projects/{0}/services/{1}'.format(project_id,
                                                                service_id)
    ports_to_close = []
    # Delete each version of the service.
    for version_id in self.zk_client.get_children(
        "{0}/versions".format(service_path)):

      port = yield self.start_delete_version(project_id, service_id,
                                             version_id)
      ports_to_close.append(port)

    del_operation = DeleteServiceOperation(project_id, service_id)
    operations[del_operation.id] = del_operation

    IOLoop.current().spawn_callback(wait_for_delete,
                                    del_operation.id, ports_to_close)

    # Cleanup the service in zookeeper.
    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      try:
        self.zk_client.delete(service_path, recursive=True)
      except NoNodeError:
        pass
    finally:
      self.version_update_lock.release()

    self.write(json_encode(del_operation.rest_repr()))


class VersionsHandler(BaseHandler):
  """ Manages service versions. """

  # A rule for validating project IDs.
  PROJECT_ID_RE = re.compile(r'^[a-z][a-z0-9\-]{5,29}$')

  # A rule for validating version IDs.
  VERSION_ID_RE = re.compile(r'^(?!-)[a-z0-9-]{0,62}[a-z0-9]$')

  # A rule for validating service IDs.
  SERVICE_ID_RE = re.compile(r'^(?!-)[a-z0-9-]{0,62}[a-z0-9]$')


  # Reserved names for version IDs.
  RESERVED_VERSION_IDS = ('^default$', '^latest$', '^ah-.*$')

  def initialize(self, acc, ua_client, zk_client, version_update_lock,
                 thread_pool, controller_state):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      ua_client: A UAClient.
      zk_client: A KazooClient.
      version_update_lock: A kazoo lock.
      thread_pool: A ThreadPoolExecutor.
      controller_state: A ControllerState object.
    """
    self.acc = acc
    self.ua_client = ua_client
    self.zk_client = zk_client
    self.version_update_lock = version_update_lock
    self.thread_pool = thread_pool
    self.controller_state = controller_state

  def get_current_user(self):
    """ Retrieves the current user.

    Returns:
      A string specifying the user's email address.
    Raises:
      CustomHTTPError if the user is invalid.
    """
    if 'AppScale-User' not in self.request.headers:
      message = 'A required header is missing: AppScale-User'
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    user = self.request.headers['AppScale-User']
    try:
      user_exists = self.ua_client.does_user_exist(user)
    except UAException:
      message = 'Unable to determine if user exists: {}'.format(user)
      logger.exception(message)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    if not user_exists:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='User does not exist: {}'.format(user))

    return user

  def version_from_payload(self):
    """ Constructs version from payload.

    Returns:
      A dictionary containing version details.
    Raises:
      CustomHTTPError if payload is invalid.
    """
    try:
      version = json_decode(self.request.body)
    except ValueError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Payload must be valid JSON')
    required_fields = ('deployment.zip.sourceUrl', 'id', 'runtime')
    utils.assert_fields_in_resource(required_fields, 'version', version)
    if version['runtime'] not in VALID_RUNTIMES:
      message = 'Invalid runtime: {}'.format(version['runtime'])
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    if version['runtime'] in [constants.JAVA, constants.PYTHON27]:
      utils.assert_fields_in_resource(['threadsafe'], 'version', version)

    version['id'] = str(version['id'])

    # Prevent multiple versions per service.
    if version['id'] != constants.DEFAULT_VERSION:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='AppScale currently does not support versions, '
                                    'so you have to use default version ID, i.e. "v1"')

    if not self.VERSION_ID_RE.match(version['id']):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid version ID. '
                                    'May only contain lowercase letters, digits, '
                                    'and hyphens. Must begin and end with a letter '
                                    'or digit. Must not exceed 63 characters.')

    for reserved_id in self.RESERVED_VERSION_IDS:
      if re.match(reserved_id, version['id']):
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                              message='Reserved version ID')

    if 'basicScaling' in version:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid scaling, basicScaling is not supported')

    for inbound_service in version.get('inboundServices', []):
      if inbound_service not in SUPPORTED_INBOUND_SERVICES:
        message = '{} is not supported'.format(inbound_service)
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    # Create a revision ID to differentiate between deployments of the same
    # version.
    version['revision'] = int(time.time() * 1000)

    extensions = version.get('appscaleExtensions', {})
    http_port = extensions.get('httpPort', None)
    https_port = extensions.get('httpsPort', None)
    if http_port is not None and http_port not in constants.ALLOWED_HTTP_PORTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid HTTP port')

    if (https_port is not None and
        https_port not in constants.ALLOWED_HTTPS_PORTS):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid HTTPS port')

    try:
      validate_resource(version, 'version')
    except ResourceValidationError as e:
        resource_message = 'Invalid request: {}'.format(e.message)
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=resource_message)

    return version

  def version_exists(self, project_id, service_id, version_id):
    """ Checks if a version exists.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      project_id, service_id, version_id)
    return self.zk_client.exists(version_node) is not None

  def put_version(self, project_id, service_id, new_version):
    """ Create or update version node.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      new_version: A dictionary containing version details.
    Returns:
      A dictionary containing updated version details.
    """
    version_node = constants.VERSION_NODE_TEMPLATE.format(
      project_id=project_id, service_id=service_id,
      version_id=new_version['id'])

    try:
      old_version_json, _ = self.zk_client.get(version_node)
      old_version = json.loads(old_version_json)
    except NoNodeError:
      old_version = {}

    if 'appscaleExtensions' not in new_version:
      new_version['appscaleExtensions'] = {}

    new_version['appscaleExtensions'].update(
      utils.assign_ports(old_version, new_version, self.zk_client))

    new_project = {
      'projectId': project_id,
      'lifecycleState': LifecycleState.ACTIVE
    }
    project_path = constants.PROJECT_NODE_TEMPLATE.format(project_id)
    try:
      self.zk_client.create(project_path, json.dumps(new_project),
                            makepath=True)
    except NodeExistsError:
      if self.zk_client.get(project_path):
        pass
      self.zk_client.set(project_path, json.dumps(new_project))

    try:
      self.zk_client.create(version_node, json.dumps(new_version),
                            makepath=True)
    except NodeExistsError:
      if project_id in constants.IMMUTABLE_PROJECTS:
        if 'md5' not in new_version['appscaleExtensions']:
          message = '{} cannot be modified'.format(project_id)
          raise CustomHTTPError(HTTPCodes.FORBIDDEN, message=message)

        old_md5 = old_version.get('appscaleExtensions', {}).get('md5')
        if new_version['appscaleExtensions']['md5'] == old_md5:
          raise VersionNotChanged('Proposed revision matches the previous one')

      self.zk_client.set(version_node, json.dumps(new_version))

    return new_version

  @gen.coroutine
  def identify_as_hoster(self, project_id, service_id, version):
    """ Marks this machine as having a version's source code.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing version details.
    """
    revision_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id'], str(version['revision'])])
    hoster_node = '/apps/{}/{}'.format(revision_key, options.private_ip)
    source_location = version['deployment']['zip']['sourceUrl']

    md5 = yield self.thread_pool.submit(get_md5, source_location)
    try:
      self.zk_client.create(hoster_node, md5, makepath=True)
    except NodeExistsError:
      raise CustomHTTPError(
        HTTPCodes.INTERNAL_ERROR, message='Revision already exists')

  def stop_hosting_revision(self, project_id, service_id, version):
    """ Removes a revision and its hosting entry.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing version details.
    """
    revision_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id'], str(version['revision'])])
    revision_node = '/apps/{}'.format(revision_key)
    hoster_node = '/'.join([revision_node, options.private_ip])

    try:
      self.zk_client.delete(hoster_node)
    except NoNodeError:
      pass

    # Clean up revision container since it's probably empty.
    try:
      self.zk_client.delete(revision_node)
    except (NotEmptyError, NoNodeError):
      pass

    source_location = version['deployment']['zip']['sourceUrl']
    try:
      os.remove(source_location)
    except OSError as error:
      if error.errno != errno.ENOENT:
        raise

  def clean_up_revision_nodes(self, project_id, service_id, version):
    """ Removes old revision nodes.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version: A dictionary containing version details.
    """
    revision_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id'], str(version['revision'])])
    version_prefix = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id']])
    old_revisions = [node for node in self.zk_client.get_children('/apps')
                     if node.startswith(version_prefix)
                     and node < revision_key]
    for node in old_revisions:
      logger.info('Removing hosting entries for {}'.format(node))
      self.zk_client.delete('/apps/{}'.format(node), recursive=True)

  @gen.coroutine
  def post(self, project_id, service_id):
    """ Creates or updates a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """

    if not self.PROJECT_ID_RE.match(project_id):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid project ID. '
                                    'It must be 6 to 30 lowercase letters, digits, '
                                    'or hyphens. It must start with a letter.')

    if not self.SERVICE_ID_RE.match(service_id):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid service ID. '
                                    'May only contain lowercase letters, digits, '
                                    'and hyphens. Must begin and end with a letter '
                                    'or digit. Must not exceed 63 characters.')

    self.authenticate(project_id, self.ua_client)
    version = self.version_from_payload()

    version_exists = self.version_exists(project_id, service_id, version['id'])
    revision_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id'], str(version['revision'])])
    try:
      yield self.thread_pool.submit(
        utils.extract_source, revision_key,
        version['deployment']['zip']['sourceUrl'], version['runtime'])
    except IOError:
      message = '{} does not exist'.format(
        version['deployment']['zip']['sourceUrl'])
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)
    except constants.InvalidSource as error:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message=six.text_type(error))

    new_path = utils.rename_source_archive(project_id, service_id, version)
    version['deployment']['zip']['sourceUrl'] = new_path
    yield self.identify_as_hoster(project_id, service_id, version)

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.put_version(project_id, service_id, version)
    except VersionNotChanged as warning:
      logger.info(six.text_type(warning))
      self.stop_hosting_revision(project_id, service_id, version)
      return
    finally:
      self.version_update_lock.release()

    self.clean_up_revision_nodes(project_id, service_id, version)
    utils.remove_old_archives(project_id, service_id, version)

    operation = CreateVersionOperation(project_id, service_id, version)
    operations[operation.id] = operation

    pre_wait = REDEPLOY_WAIT if version_exists else 0
    logger.debug(
      'Starting operation {} in {}s'.format(operation.id, pre_wait))
    IOLoop.current().call_later(pre_wait, wait_for_deploy, operation.id,
                                self.controller_state)

    # Update the project's cron configuration. This is a bit messy  because it
    # means acc.update_cron is often called twice when deploying a version.
    # However, it's needed for now to handle the following case:
    # 1. The user updates a project's cron config, referencing a module that
    #    isn't deployed yet.
    # 2. The user deploys the referenced module from a directory that does not
    #    have any cron configuration.
    # In order for the cron entries to use the correct location,
    # acc.update_cron needs to be called again even though the client did not
    # request a cron configuration update. This can be eliminated in the
    # future by routing requests based on the host header like in GAE.
    if not version_exists:
      self.acc.update_cron(project_id)

    self.write(json_encode(operation.rest_repr()))


class VersionHandler(BaseVersionHandler):
  """ Manages particular service versions. """

  def initialize(self, acc, ua_client, zk_client, version_update_lock,
                 thread_pool, controller_state):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      ua_client: A UAClient.
      zk_client: A KazooClient.
      version_update_lock: A kazoo lock.
      thread_pool: A ThreadPoolExecutor.
      controller_state: A ControllerState object.
    """
    self.acc = acc
    self.ua_client = ua_client
    self.zk_client = zk_client
    self.version_update_lock = version_update_lock
    self.thread_pool = thread_pool
    self.controller_state = controller_state

  def get_version(self, project_id, service_id, version_id):
    """ Fetches a version node.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    Returns:
      A dictionary containing version details.
    """
    version_node = constants.VERSION_NODE_TEMPLATE.format(
      project_id=project_id, service_id=service_id, version_id=version_id)

    try:
      version_json, _ = self.zk_client.get(version_node)
    except NoNodeError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND, message='Version not found')

    return json.loads(version_json)

  def version_from_payload(self):
    """ Constructs version from payload.

    Returns:
      A dictionary containing version details.
    """
    update_mask = self.get_argument('updateMask', None)
    if not update_mask:
      message = 'At least one field must be specified for this operation.'
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    desired_fields = update_mask.split(',')
    supported_fields = {
      'appscaleExtensions.httpPort',
      'appscaleExtensions.httpsPort',
      'automaticScaling.standard_scheduler_settings.max_instances',
      'automaticScaling.standard_scheduler_settings.min_instances',
      'servingStatus'}
    mapped_fields = {
      'automaticScaling.standard_scheduler_settings.max_instances':
        'automaticScaling.standardSchedulerSettings.maxInstances',
      'automaticScaling.standard_scheduler_settings.min_instances':
        'automaticScaling.standardSchedulerSettings.minInstances'}
    for field in desired_fields:
      if field not in supported_fields:
        message = ('This operation is only supported on the following '
                   'field(s): [{}]'.format(', '.join(supported_fields)))
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=message)

    try:
      given_version = json_decode(self.request.body)
    except ValueError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Payload must be valid JSON')
    rest_to_json = lambda field : mapped_fields.get(field, field)
    masked_version = utils.apply_mask_to_version(
      given_version,
      list(map(rest_to_json, desired_fields)))

    extensions = masked_version.get('appscaleExtensions', {})
    http_port = extensions.get('httpPort', None)
    https_port = extensions.get('httpsPort', None)
    if http_port is not None and http_port not in constants.ALLOWED_HTTP_PORTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid HTTP port')

    if (https_port is not None and
        https_port not in constants.ALLOWED_HTTPS_PORTS):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid HTTPS port')

    return masked_version

  def update_version(self, project_id, service_id, version_id, new_fields):
    """ Updates a version node.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      new_fields: A dictionary containing version details.
    Returns:
      A dictionary containing completed version details.
    """
    version_node = constants.VERSION_NODE_TEMPLATE.format(
      project_id=project_id, service_id=service_id, version_id=version_id)

    try:
      version_json, _ = self.zk_client.get(version_node)
    except NoNodeError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND, message='Version not found')

    version = json.loads(version_json)

    if 'automaticScaling' in new_fields:
      if 'manualScaling' in version:
        scaling_error = 'Invalid scaling update for Manual Scaling version'
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=scaling_error)

      (version.setdefault('automaticScaling', {})
              .setdefault('standardSchedulerSettings',{})
              .update(new_fields.get('automaticScaling')
                                .get('standardSchedulerSettings',{})))

    if 'servingStatus' in new_fields:
      if not 'manualScaling' in version:
        scaling_error = ('Serving status cannot be changed for Automatic '
                         'Scaling versions')
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=scaling_error)

      if ServingStatus.STOPPED == new_fields['servingStatus']:
        version['servingStatus'] = ServingStatus.STOPPED
      elif 'servingStatus' in version:
        del version['servingStatus']

    new_ports = utils.assign_ports(version, new_fields, self.zk_client)
    version['appscaleExtensions'].update(new_ports)

    self.zk_client.set(version_node, json.dumps(version))
    return version

  @gen.coroutine
  def relocate_version(self, project_id, service_id, version_id, http_port,
                       https_port):
    """ Assigns new ports to a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      http_port: An integer specifying a port.
      https_port: An integer specifying a port.
    Returns:
      A dictionary containing completed version details.
    """
    new_fields = {'appscaleExtensions': {}}
    if http_port is not None:
      new_fields['appscaleExtensions']['httpPort'] = http_port

    if https_port is not None:
      new_fields['appscaleExtensions']['httpsPort'] = https_port

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.update_version(project_id, service_id, version_id,
                                    new_fields)
    finally:
      self.version_update_lock.release()

    raise gen.Return(version)

  @gen.coroutine
  def update_scaling_for_version(self, project_id, service_id, version_id,
                                 min_instances, max_instances):
    """ Updates scaling settings for a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      min_instances: An integer specifying minimum instances.
      max_instances: An integer specifying maximum instances.
    Returns:
      A dictionary containing completed version details.
    """
    new_fields = {'automaticScaling': {'standardSchedulerSettings': {}}}
    scheduler_fields = new_fields['automaticScaling']['standardSchedulerSettings']
    if min_instances is not None:
      scheduler_fields['minInstances'] = min_instances

    if max_instances is not None:
      scheduler_fields['maxInstances'] = max_instances

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.update_version(project_id, service_id, version_id,
                                    new_fields)
    finally:
      self.version_update_lock.release()

    raise gen.Return(version)

  @gen.coroutine
  def update_serving_status_for_version(self, project_id, service_id,
                                        version_id, serving_status):
    """ Updates service status for a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      serving_status: The desired status (SERVING|STOPPED)
    Returns:
      A dictionary containing completed version details.
    """
    new_fields = {'servingStatus': serving_status}
    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.update_version(project_id, service_id, version_id,
                                    new_fields)
    finally:
      self.version_update_lock.release()

    raise gen.Return(version)

  def get(self, project_id, service_id, version_id):
    """ Gets the specified version resource.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate(project_id, self.ua_client)

    version_details = self.get_version(project_id, service_id, version_id)

    login_host = options.login_ip
    if self.controller_state.options is not None:
      login_host = self.controller_state.options.get('login', login_host)

    # Hide details that aren't needed for the public API.
    version_details.pop('revision', None)
    version_details.get('appscaleExtensions', {}).pop('haproxyPort', None)

    http_port = version_details['appscaleExtensions']['httpPort']
    response = {
      'name': 'apps/{}/services/{}/versions/{}'.format(project_id, service_id,
                                                       version_id),
      'servingStatus': ServingStatus.SERVING,
      'versionUrl': 'http://{}:{}'.format(login_host, http_port)
    }
    response.update(version_details)
    self.write(json_encode(response))

  @gen.coroutine
  def delete(self, project_id, service_id, version_id):
    """ Deletes a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate(project_id, self.ua_client)

    if project_id in constants.IMMUTABLE_PROJECTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} cannot be deleted'.format(project_id))

    if version_id != constants.DEFAULT_VERSION:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid version')

    port = yield self.start_delete_version(project_id, service_id,
                                           version_id)
    ports_to_close = [port]
    del_operation = DeleteVersionOperation(project_id, service_id, version_id)
    operations[del_operation.id] = del_operation

    IOLoop.current().spawn_callback(wait_for_delete,
                                    del_operation.id, ports_to_close)

    self.write(json_encode(del_operation.rest_repr()))

  @gen.coroutine
  def patch(self, project_id, service_id, version_id):
    """ Updates a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate(project_id, self.ua_client)

    if project_id in constants.IMMUTABLE_PROJECTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} cannot be updated'.format(project_id))

    version = self.version_from_payload()

    extensions = version.get('appscaleExtensions', {})
    if 'httpPort' in extensions or 'httpsPort' in extensions:
      new_http_port = extensions.get('httpPort')
      new_https_port = extensions.get('httpsPort')
      version = yield self.relocate_version(
        project_id, service_id, version_id, new_http_port, new_https_port)

    automatic_scaling = version.get('automaticScaling', {})
    standard_settings = automatic_scaling.get(
      'standardSchedulerSettings', {})
    if ('minInstances' in standard_settings or
        'maxInstances' in standard_settings):
      new_min_instances = standard_settings.get('minInstances', None)
      new_max_instances = standard_settings.get('maxInstances', None)
      version = yield self.update_scaling_for_version(
        project_id, service_id, version_id, new_min_instances,
        new_max_instances)

    serving_status = version.get('servingStatus', None)
    if serving_status:
      version = yield self.update_serving_status_for_version(
        project_id, service_id, version_id, serving_status)

    operation = UpdateVersionOperation(project_id, service_id, version)
    self.write(json_encode(operation.rest_repr()))


class OperationsHandler(BaseHandler):
  """ Retrieves operations. """
  def initialize(self, ua_client):
    """ Defines required resources to handle requests.

    Args:
      ua_client: A UAClient.
    """
    self.ua_client = ua_client

  def get(self, project_id, operation_id):
    """ Retrieves operation status.

    Args:
      project_id: A string specifying a project ID.
      operation_id: A string specifying an operation ID.
    """
    self.authenticate(project_id, self.ua_client)

    try:
      operation = operations[operation_id]
    except KeyError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                            message='Operation not found.')

    self.write(json_encode(operation.rest_repr()))


class OAuthHandler(BaseHandler):
  """ Authorize users and give them Access Tokens."""
  def initialize(self, ua_client):
    """ Defines required resources to handle requests.

    Args:
      ua_client: A UAClient.
    """
    self.ua_client = ua_client

  def post(self):
    """Grants Access Tokens."""
    if self.get_argument('scope', None) != self.AUTH_SCOPE:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid scope')

    grant_type = self.get_argument('grant_type', None)
    metadata = {'scope': self.AUTH_SCOPE, 'exp': int(time.time()) + 3600}
    if grant_type == 'password':
      username = self.get_argument('username', '')
      self._check_user(username, self.get_argument('password', ''))
      metadata['user'] = username
    elif grant_type == 'secret':
      secret = self.get_argument('secret', '').encode('utf-8')
      if not utils.constant_time_compare(secret, options.secret):
        raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

      metadata['project'] = self.get_argument('project_id', '')
    else:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid grant type')

    metadata_base64 = base64.urlsafe_b64encode(json.dumps(metadata))

    method = {'type': 'JWT', 'alg': 'SHA-1'}

    method_base64 = base64.urlsafe_b64encode(json.dumps(method))

    hasher = hashlib.sha1()
    hasher.update(method_base64)
    hasher.update(metadata_base64)
    hasher.update(options.secret)
    token = '{}.{}.{}'.format(method_base64, metadata_base64,
                              hasher.hexdigest())

    auth_response = {
      'access_token': token,
      'token_type': 'bearer',
      'expires_in': 3600,
      'scope': self.AUTH_SCOPE
    }

    self.write(json_encode(auth_response))

  def _check_user(self, username, password):
    """ Ensures the given password is correct for the user. """
    try:
      user_data = self.ua_client.get_user_data(username)
    except UAException:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Unable to fetch user data')

    # Get the stored hash for the user.
    server_re = re.search(self.ua_client.USER_DATA_PASSWORD_REGEX, user_data)
    if not server_re:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Invalid user data')

    stored_hash = server_re.group(1)

    # Check against the stored hash.
    hash_input = ''.join([username, password])
    if stored_hash != hashlib.sha1(hash_input).hexdigest():
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid password')


def main():
  """ Starts the AdminServer. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(
    prog='appscale-admin', description='Manages AppScale-related processes')
  subparsers = parser.add_subparsers(dest='command')
  subparsers.required = True

  serve_parser = subparsers.add_parser(
    'serve', description='Starts the server that manages AppScale processes')
  serve_parser.add_argument(
    '-p', '--port', type=int, default=constants.DEFAULT_PORT,
    help='The port to listen on')
  serve_parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')

  subparsers.add_parser(
    'summary', description='Lists AppScale processes running on this machine')
  restart_parser = subparsers.add_parser(
    'restart',
    description='Restart AppScale processes running on this machine')
  restart_parser.add_argument('service', nargs='+',
                              help='The process or service ID to restart')

  args = parser.parse_args()
  if args.command == 'summary':
    table = sorted(list(get_services().items()))
    print(tabulate(table, headers=['Service', 'State']))
    sys.exit(0)

  if args.command == 'restart':
    socket_path = urlquote(ServiceManagerHandler.SOCKET_PATH, safe='')
    session = requests_unixsocket.Session()
    response = session.post(
      'http+unix://{}/'.format(socket_path),
      data={'command': 'restart', 'arg': [args.service]})
    response.raise_for_status()
    return

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  options.define('secret', appscale_info.get_secret())
  options.define('login_ip', appscale_info.get_login_ip())
  options.define('private_ip', appscale_info.get_private_ip())
  options.define('zk_locations', appscale_info.get_zk_node_ips())
  options.define('load_balancers', appscale_info.get_load_balancer_ips())

  acc = appscale_info.get_appcontroller_client()
  ua_client = UAClient()
  zk_client = KazooClient(
    hosts=','.join(options.zk_locations),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()
  version_update_lock = zk_client.Lock(constants.VERSION_UPDATE_LOCK_NODE)
  thread_pool = ThreadPoolExecutor(4)
  service_operator = ServiceOperator(thread_pool)
  all_resources = {
    'acc': acc,
    'ua_client': ua_client,
    'zk_client': zk_client,
    'version_update_lock': version_update_lock,
    'thread_pool': thread_pool
  }

  if options.private_ip in appscale_info.get_taskqueue_nodes():
    logger.info('Starting push worker manager')
    GlobalPushWorkerManager(zk_client, service_operator)

  if options.private_ip in appscale_info.get_load_balancer_ips():
    logger.info('Starting RoutingManager')
    routing_manager = RoutingManager(zk_client)
    routing_manager.start()

  service_manager = ServiceManager(zk_client)
  service_manager.start()

  controller_state = ControllerState(zk_client)

  app = web.Application([
    ('/oauth/token', OAuthHandler, {'ua_client': ua_client}),
    ('/v1/apps/([^/]*)/services/([^/]*)/versions', VersionsHandler,
     {'acc': acc, 'ua_client': ua_client, 'zk_client': zk_client,
      'version_update_lock': version_update_lock, 'thread_pool': thread_pool,
      'controller_state': controller_state}),
    ('/v1/projects', ProjectsHandler, all_resources),
    ('/v1/projects/([a-z0-9-]+)', ProjectHandler, all_resources),
    ('/v1/apps/([^/]*)/services', ServicesHandler,
     {'ua_client': ua_client, 'zk_client': zk_client}),
    ('/v1/apps/([^/]*)/services/([^/]*)', ServiceHandler,
     all_resources),
    ('/v1/apps/([^/]*)/services/([^/]*)/versions/([^/]*)',
     VersionHandler,
     {'acc': acc, 'ua_client': ua_client, 'zk_client': zk_client,
      'version_update_lock': version_update_lock, 'thread_pool': thread_pool,
      'controller_state': controller_state}),
    ('/v1/apps/([^/]*)', AppsHandler,
     {'ua_client': ua_client, 'zk_client': zk_client}),
    ('/v1/apps/([^/]*)/operations/([a-z0-9-]+)', OperationsHandler,
     {'ua_client': ua_client}),
    ('/api/cron/update', UpdateCronHandler,
     {'acc': acc, 'zk_client': zk_client, 'ua_client': ua_client}),
    ('/api/datastore/index/add', UpdateIndexesHandler,
     {'zk_client': zk_client, 'ua_client': ua_client}),
    ('/api/queue/update', UpdateQueuesHandler,
     {'zk_client': zk_client, 'ua_client': ua_client}),
    ('/v1/projects/([^/]*)/serviceAccounts', ServiceAccountsHandler,
     {'zk_client': zk_client, 'ua_client': ua_client})
  ])
  logger.info('Starting AdminServer')
  app.listen(args.port)

  management_app = web.Application([
    ('/', ServiceManagerHandler, {'service_manager': service_manager})])
  management_server = HTTPServer(management_app)
  management_socket = bind_unix_socket(ServiceManagerHandler.SOCKET_PATH)
  management_server.add_socket(management_socket)

  io_loop = IOLoop.current()
  io_loop.start()
