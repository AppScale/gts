""" A server that handles application deployments. """

import argparse
import base64
import errno
import hashlib
import json
import logging
import os
import re
import time

from appscale.appcontroller_client import AppControllerException
from appscale.common import appscale_info
from appscale.common.constants import (
  HTTPCodes,
  LOG_FORMAT,
  VERSION_PATH_SEPARATOR,
  ZK_PERSISTENT_RECONNECTS
)
from appscale.common.monit_interface import MonitOperator
from appscale.common.appscale_utils import get_md5
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError
from kazoo.exceptions import NoNodeError
from kazoo.exceptions import NotEmptyError
from tornado import gen
from tornado.options import options
from tornado import web
from tornado.escape import json_decode
from tornado.escape import json_encode
from tornado.ioloop import IOLoop
from . import utils
from . import constants
from .appengine_api import UpdateCronHandler
from .appengine_api import UpdateQueuesHandler
from .base_handler import BaseHandler
from .constants import (
  AccessTokenErrors,
  CustomHTTPError,
  OperationTimeout,
  REDEPLOY_WAIT,
  ServingStatus,
  SUPPORTED_INBOUND_SERVICES,
  VALID_RUNTIMES,
  VersionNotChanged
)
from .operation import (
  DeleteServiceOperation,
  CreateVersionOperation,
  DeleteVersionOperation,
  UpdateVersionOperation
)
from .operations_cache import OperationsCache
from .push_worker_manager import GlobalPushWorkerManager
from .service_manager import ServiceManager

logger = logging.getLogger('appscale-admin')

# The state of each operation.
operations = OperationsCache()


@gen.coroutine
def wait_for_port_to_open(http_port, operation_id, deadline):
  """ Waits until port is open.

  Args:
    http_port: An integer specifying the version's port number.
    operation_id: A string specifying an operation ID.
    deadline: A float containing a unix timestamp.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  logger.debug('Waiting for {} to open'.format(http_port))
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  while True:
    if time.time() > deadline:
      message = 'Deploy operation took too long.'
      operation.set_error(message)
      raise OperationTimeout(message)

    if utils.port_is_open(options.login_ip, http_port):
      break

    yield gen.sleep(1)

  for load_balancer in appscale_info.get_load_balancer_ips():
    while True:
      if time.time() > deadline:
        # The version is reachable from the login IP, but it's not reachable
        # from every registered load balancer. It makes more sense to mark the
        # operation as a success than a failure because the lagging load
        # balancers should eventually reflect the registered instances.
        break

      if utils.port_is_open(load_balancer, http_port):
        break

      yield gen.sleep(1)


@gen.coroutine
def wait_for_deploy(operation_id, acc):
  """ Tracks the progress of a deployment.

  Args:
    operation_id: A string specifying the operation ID.
    acc: An AppControllerClient instance.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  start_time = time.time()
  deadline = start_time + constants.MAX_OPERATION_TIME

  http_port = operation.version['appscaleExtensions']['httpPort']
  yield wait_for_port_to_open(http_port, operation_id, deadline)

  url = 'http://{}:{}'.format(options.login_ip, http_port)
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

  start_time = time.time()
  deadline = start_time + constants.MAX_OPERATION_TIME

  finished = 0
  ports = ports_to_close[:]
  while True:
    if time.time() > deadline:
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
    """ Starts the process of deleting a version by calling stop_version on
    the AppController and deleting the version node. Returns the version's
    port that will be closing, the caller should wait for this port to close.

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

    version_key = VERSION_PATH_SEPARATOR.join([project_id, service_id,
                                               version_id])
    try:
      self.acc.stop_version(version_key)
    except AppControllerException as error:
      message = 'Error while stopping version: {}'.format(error)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

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
  def wait_for_delete(self, ports_to_close, project_id):
    """ Tracks the progress of removing version(s).

    Args:
      ports_to_close: A list of integers specifying the ports to wait for.
      project_id: The id of the project we are deleting.
    Raises:
      OperationTimeout if the deadline is exceeded.
    """
    project_path = constants.PROJECT_NODE_TEMPLATE.format(project_id)
    update_project_state(self.zk_client, project_id,
                         LifecycleState.DELETE_IN_PROGRESS)
    start_time = time.time()
    deadline = start_time + constants.MAX_OPERATION_TIME

    finished = 0
    ports = ports_to_close[:]
    while True:
      if time.time() > deadline:
        logger.error('Delete operation took too long (project_id: {}).'
                     .format(project_id))
        raise gen.Return()
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

    # Cleanup the project in zookeeper.
    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      try:
        self.zk_client.delete(project_path, recursive=True)
      except NoNodeError:
        pass
    finally:
      self.version_update_lock.release()

  @gen.coroutine
  def delete(self, project_id):
    """ Deletes a project.

    Args:
      project_id: The id of the project to delete.
    """
    self.authenticate(project_id, self.ua_client)
    project_path = constants.PROJECT_NODE_TEMPLATE.format(project_id)
    update_project_state(self.zk_client, project_id,
                         LifecycleState.DELETE_REQUESTED)
    ports_to_close = []
    # Delete each version of each service of the project.
    for service_id in \
        self.zk_client.get_children("{0}/services".format(project_path)):
      for version_id in self.zk_client.get_children(
          "{0}/services/{1}/versions".format(project_path, service_id)):

        port = yield self.start_delete_version(project_id, service_id,
                                               version_id)
        ports_to_close.append(port)

    IOLoop.current().spawn_callback(self.wait_for_delete,
                                    ports_to_close, project_id)


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

  # A rule for validating version IDs.
  VERSION_ID_RE = re.compile(r'(?!-)[a-z\d\-]{1,100}')

  # Reserved names for version IDs.
  RESERVED_VERSION_IDS = ('^default$', '^latest$', '^ah-.*$')

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
                            message='Invalid version ID')

    if not self.VERSION_ID_RE.match(version['id']):
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid version ID')

    for reserved_id in self.RESERVED_VERSION_IDS:
      if re.match(reserved_id, version['id']):
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                              message='Reserved version ID')

    if 'basicScaling' in version or 'manualScaling' in version:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Only automaticScaling is supported')

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

  def begin_deploy(self, project_id, service_id, version_id):
    """ Triggers the deployment process.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    Raises:
      CustomHTTPError if unable to start the deployment process.
    """
    version_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version_id])

    try:
      self.acc.update([version_key])
    except AppControllerException as error:
      message = 'Error while updating version: {}'.format(error)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

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
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=str(error))

    new_path = utils.rename_source_archive(project_id, service_id, version)
    version['deployment']['zip']['sourceUrl'] = new_path
    yield self.identify_as_hoster(project_id, service_id, version)

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.put_version(project_id, service_id, version)
    except VersionNotChanged as warning:
      logger.info(str(warning))
      self.stop_hosting_revision(project_id, service_id, version)
      return
    finally:
      self.version_update_lock.release()

    self.clean_up_revision_nodes(project_id, service_id, version)
    utils.remove_old_archives(project_id, service_id, version)
    self.begin_deploy(project_id, service_id, version['id'])

    operation = CreateVersionOperation(project_id, service_id, version)
    operations[operation.id] = operation

    pre_wait = REDEPLOY_WAIT if version_exists else 0
    logging.debug(
      'Starting operation {} in {}s'.format(operation.id, pre_wait))
    IOLoop.current().call_later(pre_wait, wait_for_deploy, operation.id,
                                self.acc)

    self.write(json_encode(operation.rest_repr()))


class VersionHandler(BaseVersionHandler):
  """ Manages particular service versions. """

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
    supported_fields = {'appscaleExtensions.httpPort',
                        'appscaleExtensions.httpsPort'}
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

    masked_version = utils.apply_mask_to_version(given_version, desired_fields)

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

  def get(self, project_id, service_id, version_id):
    """ Gets the specified version resource.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate(project_id, self.ua_client)

    version_details = self.get_version(project_id, service_id, version_id)

    # Hide details that aren't needed for the public API.
    version_details.pop('revision', None)
    version_details.get('appscaleExtensions', {}).pop('haproxyPort', None)

    http_port = version_details['appscaleExtensions']['httpPort']
    response = {
      'name': 'apps/{}/services/{}/versions/{}'.format(project_id, service_id,
                                                       version_id),
      'servingStatus': ServingStatus.SERVING,
      'versionUrl': 'http://{}:{}'.format(options.login_ip, http_port)
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

    self.write(json_encode(del_operation))

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
    """Grants users Access Tokens."""

    # Format for error message.
    error_msg = {
      'error': '',
      'error_description': ''
    }

    missing_arguments = []

    grant_type = self.get_argument('grant_type', default=None, strip=True)
    if not grant_type:
      missing_arguments.append('grant_type')

    username = self.get_argument('username', default=None, strip=True)
    if not username:
      missing_arguments.append('username')

    password = self.get_argument('password', default=None, strip=True)
    if not password:
      missing_arguments.append('password')

    scope = self.get_argument('scope', default=None, strip=True)
    if not scope:
      missing_arguments.append('scope')

    if missing_arguments:
      error_msg['error'] = constants.AccessTokenErrors.INVALID_REQUEST
      error_msg['error_description'] = 'Required parameters(s) are missing: {}'\
        .format(missing_arguments)
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error_msg)

    if grant_type != 'password':
      error_msg['error'] = constants.AccessTokenErrors.UNSUPPORTED_GRANT_TYPE
      error_msg['error_description'] = 'Grant type {} not supported.'.format(
          grant_type)
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error_msg)

    if scope != self.AUTH_SCOPE:
      error_msg['error'] = constants.AccessTokenErrors.INVALID_SCOPE
      error_msg['error_description'] = 'Scope {} not supported.'.format(
          grant_type)
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error_msg)

    # Get the user.
    try:
      user_data = self.ua_client.get_user_data(username)
    except UAException:
      error_msg['error'] = constants.AccessTokenErrors.INVALID_GRANT
      error_msg['error_description'] = 'Unable to determine user data for {}'\
        .format(username)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=error_msg)

    # Get the user's stored password.
    server_re = re.search(self.ua_client.USER_DATA_PASSWORD_REGEX, user_data)
    if not server_re:
      error_msg['error'] = constants.AccessTokenErrors.INVALID_GRANT
      error_msg['error_description'] = "Invalid user data for {}".format(
          username)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=error_msg)
    server_pwd = server_re.group(1)

    # Hash the given username and password.
    encrypted_pass = hashlib.sha1("{0}{1}".format(username, password))\
      .hexdigest()
    if server_pwd != encrypted_pass:
      error_msg['error'] = constants.AccessTokenErrors.INVALID_GRANT
      error_msg['error_description'] = "Incorrect password for {}"\
        .format(username)
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=error_msg)

    # If we have gotten here, the user is granted an Access Token,
    # so we create it.
    metadata = {
      'user': username,
      'exp': int(time.time()) + 3600,
      'scope': self.AUTH_SCOPE
    }

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


def main():
  """ Starts the AdminServer. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument('-p', '--port', type=int, default=constants.DEFAULT_PORT,
                      help='The port to listen on')
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()

  if args.verbose:
    logger.setLevel(logging.DEBUG)

  options.define('secret', appscale_info.get_secret())
  options.define('login_ip', appscale_info.get_login_ip())
  options.define('private_ip', appscale_info.get_private_ip())
  options.define('load_balancers', appscale_info.get_load_balancer_ips())

  acc = appscale_info.get_appcontroller_client()
  ua_client = UAClient(appscale_info.get_db_master_ip(), options.secret)
  zk_client = KazooClient(
    hosts=','.join(appscale_info.get_zk_node_ips()),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()
  version_update_lock = zk_client.Lock(constants.VERSION_UPDATE_LOCK_NODE)
  thread_pool = ThreadPoolExecutor(4)
  monit_operator = MonitOperator()
  all_resources = {
    'acc': acc,
    'ua_client': ua_client,
    'zk_client': zk_client,
    'version_update_lock': version_update_lock,
    'thread_pool': thread_pool
  }

  if options.private_ip in appscale_info.get_taskqueue_nodes():
    logger.info('Starting push worker manager')
    GlobalPushWorkerManager(zk_client, monit_operator)

  service_manager = ServiceManager(zk_client)
  service_manager.start()

  app = web.Application([
    ('/oauth/token', OAuthHandler, {'ua_client': ua_client}),
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions', VersionsHandler,
     all_resources),
    ('/v1/projects', ProjectsHandler, all_resources),
    ('/v1/projects/([a-z0-9-]+)', ProjectHandler, all_resources),
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)', ServiceHandler,
     all_resources),
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions/([a-z0-9-]+)',
     VersionHandler, all_resources),
    ('/v1/apps/([a-z0-9-]+)/operations/([a-z0-9-]+)', OperationsHandler,
     {'ua_client': ua_client}),
    ('/api/cron/update', UpdateCronHandler,
     {'acc': acc, 'zk_client': zk_client, 'ua_client': ua_client}),
    ('/api/queue/update', UpdateQueuesHandler,
     {'zk_client': zk_client, 'ua_client': ua_client})
  ])
  logger.info('Starting AdminServer')
  app.listen(args.port)
  io_loop = IOLoop.current()
  io_loop.start()
