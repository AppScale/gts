""" A server that handles application deployments. """

import argparse
import json
import logging
import os
import sys
import time

from appscale.common import appscale_info
from appscale.common.constants import (
  CONFIG_DIR,
  HTTPCodes,
  LOG_FORMAT,
  ZK_PERSISTENT_RECONNECTS
)
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from concurrent.futures import ThreadPoolExecutor
from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError
from kazoo.exceptions import NoNodeError
from tornado import gen
from tornado.options import options
from tornado import web
from tornado.escape import json_decode
from tornado.escape import json_encode
from tornado.ioloop import IOLoop
from . import utils
from . import constants
from .constants import (
  CustomHTTPError,
  OperationTimeout,
  REDEPLOY_WAIT,
  VALID_RUNTIMES
)
from .operation import (
  CreateVersionOperation,
  DeleteVersionOperation,
  UpdateVersionOperation
)
from .operations_cache import OperationsCache

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.appcontroller_client import AppControllerException


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
  logging.debug('Waiting for {} to open'.format(http_port))
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

  logging.info('Finished operation {}'.format(operation_id))


@gen.coroutine
def wait_for_delete(operation_id, http_port):
  """ Tracks the progress of removing a version.

  Args:
    operation_id: A string specifying the operation ID.
    http_port: An integer specifying the version's port.
  Raises:
    OperationTimeout if the deadline is exceeded.
  """
  try:
    operation = operations[operation_id]
  except KeyError:
    raise OperationTimeout('Operation no longer in cache')

  start_time = time.time()
  deadline = start_time + constants.MAX_OPERATION_TIME

  while True:
    if time.time() > deadline:
      message = 'Delete operation took too long.'
      operation.set_error(message)
      raise OperationTimeout(message)

    if not utils.port_is_open(options.login_ip, http_port):
      break

    yield gen.sleep(1)

  operation.finish()


class BaseHandler(web.RequestHandler):
  """ A handler with helper functions that other handlers can extend. """
  def authenticate(self):
    """ Ensures requests are authenticated.

    Raises:
      CustomHTTPError if the secret is invalid.
    """
    if 'AppScale-Secret' not in self.request.headers:
      message = 'A required header is missing: AppScale-Secret'
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=message)

    if self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

  def write_error(self, status_code, **kwargs):
    """ Writes a custom JSON-based error message.

    Args:
      status_code: An integer specifying the HTTP error code.
    """
    details = {'code': status_code}
    if 'exc_info' in kwargs:
      error = kwargs['exc_info'][1]
      try:
        details.update(error.kwargs)
      except AttributeError:
        pass

    self.finish(json_encode({'error': details}))


class VersionsHandler(BaseHandler):
  """ Manages service versions. """
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
      logging.exception(message)
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

    if version['id'] != constants.DEFAULT_VERSION:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid version ID')

    if 'basicScaling' in version or 'manualScaling' in version:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Only automaticScaling is supported')

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

  def project_exists(self, project_id):
    """ Checks if a project exists.
    
    Args:
      project_id: A string specifying a project ID.
    Raises:
      CustomHTTPError if unable to determine if project exists.
    """
    try:
      return self.ua_client.does_app_exist(project_id)
    except UAException:
      message = 'Unable to check if project exists: {}'.format(project_id)
      logging.exception(message)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

  def create_project(self, project_id, user, runtime):
    """ Creates a new project.
    
    Args:
      project_id: A string specifying a project ID.
      user: A string specifying a user's email address.
      runtime: A string specifying the project's runtime.
    Raises:
      CustomHTTPError if unable to create new project.
    """
    logging.info('Creating project: {}'.format(project_id))
    try:
      self.ua_client.commit_new_app(project_id, user, runtime)
    except UAException:
      message = 'Unable to ensure project exists: {}'.format(project_id)
      logging.exception(message)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

  def ensure_user_is_owner(self, project_id, user):
    """ Ensures a user is the owner of a project.
    
    Args:
      project_id: A string specifying a project ID.
      user: A string specifying a user's email address.
    Raises:
      CustomHTTPError if the user is not the owner.
    """
    # Immutable projects do not have owners.
    if project_id in constants.IMMUTABLE_PROJECTS:
      return

    try:
      project_metadata = self.ua_client.get_app_data(project_id)
    except UAException:
      message = 'Unable to retrieve project metadata'
      logging.exception(message)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    if 'owner' not in project_metadata:
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
                            message='Project owner not defined')

    if project_metadata['owner'] != user:
      message = 'User is not project owner: {}'.format(user)
      raise CustomHTTPError(HTTPCodes.FORBIDDEN, message=message)

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

    try:
      self.zk_client.create(version_node, json.dumps(new_version),
                            makepath=True)
    except NodeExistsError:
      if project_id in constants.IMMUTABLE_PROJECTS:
        message = '{} cannot be modified'.format(project_id)
        raise CustomHTTPError(HTTPCodes.FORBIDDEN, message=message)

      self.zk_client.set(version_node, json.dumps(new_version))

    return new_version

  def begin_deploy(self, project_id):
    """ Triggers the deployment process.
    
    Args:
      project_id: A string specifying a project ID.
    Raises:
      CustomHTTPError if unable to start the deployment process.
    """
    try:
      self.ua_client.enable_app(project_id)
    except UAException:
      message = 'Unable to enable project'
      logging.exception(message)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    try:
      self.acc.update([project_id])
    except AppControllerException as error:
      message = 'Error while updating application: {}'.format(error)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

  def identify_as_hoster(self, project_id, source_location):
    """ Marks this machine as having a version's source code.

    Args:
      project_id: A string specifying a project ID.
      source_location: A string specifying the location of the version's
        source archive.
    """
    private_ip = appscale_info.get_private_ip()
    hoster_node = '/apps/{}/{}'.format(project_id, private_ip)

    try:
      self.zk_client.create(hoster_node, str(source_location), ephemeral=True,
                            makepath=True)
    except NodeExistsError:
      self.zk_client.set(hoster_node, str(source_location))

    # Remove other hosters that have old code.
    hosters = self.zk_client.get_children('/apps/{}'.format(project_id))
    old_hosters = [hoster for hoster in hosters if hoster != private_ip]
    for hoster in old_hosters:
      self.zk_client.delete('/apps/{}/{}'.format(project_id, hoster))

  @gen.coroutine
  def post(self, project_id, service_id):
    """ Creates or updates a version.
    
    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """
    self.authenticate()
    user = self.get_current_user()
    version = self.version_from_payload()

    project_exists = self.project_exists(project_id)
    if not project_exists:
      self.create_project(project_id, user, version['runtime'])

    if service_id != constants.DEFAULT_SERVICE:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid service')

    self.ensure_user_is_owner(project_id, user)

    source_path = version['deployment']['zip']['sourceUrl']

    try:
      utils.extract_source(version, project_id)
    except IOError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} does not exist'.format(source_path))

    self.identify_as_hoster(project_id, source_path)

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.put_version(project_id, service_id, version)
    finally:
      self.version_update_lock.release()

    self.begin_deploy(project_id)

    operation = CreateVersionOperation(project_id, service_id, version)
    operations[operation.id] = operation

    pre_wait = REDEPLOY_WAIT if project_exists else 0
    logging.debug(
      'Starting operation {} in {}s'.format(operation.id, pre_wait))
    IOLoop.current().call_later(pre_wait, wait_for_deploy, operation.id,
                                self.acc)

    self.write(json_encode(operation.rest_repr()))


class VersionHandler(BaseHandler):
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
    if update_mask is None:
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
  def relocate_version(self, project_id, service_id, version_id, new_fields):
    """ Assigns new ports to a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      new_fields: A dictionary containing version details.
    Returns:
      A dictionary containing completed version details.
    """
    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.update_version(project_id, service_id, version_id,
                                    new_fields)
    finally:
      self.version_update_lock.release()

    http_port = version['appscaleExtensions']['httpPort']
    https_port = version['appscaleExtensions']['httpsPort']
    port_file_location = os.path.join(
      CONFIG_DIR, 'port-{}.txt'.format(project_id))
    with open(port_file_location, 'w') as port_file:
      port_file.write(str(http_port))

    try:
      self.ua_client.add_instance(project_id, options.login_ip, http_port,
                                  https_port)
    except UAException:
      logging.warning('Failed to notify UAServer about updated ports')

    raise gen.Return(version)

  @gen.coroutine
  def delete(self, project_id, service_id, version_id):
    """ Deletes a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate()

    if project_id in constants.IMMUTABLE_PROJECTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} cannot be deleted'.format(project_id))

    if service_id != constants.DEFAULT_SERVICE:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid service')

    if version_id != constants.DEFAULT_VERSION:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid version')

    version = self.get_version(project_id, service_id, version_id)
    try:
      http_port = version['appscaleExtensions']['httpPort']
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

    try:
      self.acc.stop_app(project_id)
    except AppControllerException as error:
      message = 'Error while stopping application: {}'.format(error)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    version = {'id': version_id}
    operation = DeleteVersionOperation(project_id, service_id, version)
    operations[operation.id] = operation

    IOLoop.current().spawn_callback(wait_for_delete, operation.id, http_port)

    self.write(json_encode(operation.rest_repr()))

  @gen.coroutine
  def patch(self, project_id, service_id, version_id):
    """ Updates a version.

    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self.authenticate()

    if project_id in constants.IMMUTABLE_PROJECTS:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} cannot be updated'.format(project_id))

    version = self.version_from_payload()

    extensions = version.get('appscaleExtensions', {})
    if 'httpPort' in extensions or 'httpsPort' in extensions:
      version = yield self.relocate_version(
        project_id, service_id, version_id, version)

    operation = UpdateVersionOperation(project_id, service_id, version)
    self.write(json_encode(operation.rest_repr()))


class OperationsHandler(BaseHandler):
  """ Retrieves operations. """
  def get(self, project_id, operation_id):
    """ Retrieves operation status.
    
    Args:
      project_id: A string specifying a project ID.
      operation_id: A string specifying an operation ID.
    """
    self.authenticate()

    try:
      operation = operations[operation_id]
    except KeyError:
      raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                            message='Operation not found.')

    self.write(json_encode(operation.rest_repr()))


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
    logging.getLogger().setLevel(logging.DEBUG)

  options.define('secret', appscale_info.get_secret())
  options.define('login_ip', appscale_info.get_login_ip())

  acc = appscale_info.get_appcontroller_client()
  ua_client = UAClient(appscale_info.get_db_master_ip(), options.secret)
  zk_client = KazooClient(
    hosts=','.join(appscale_info.get_zk_node_ips()),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()
  version_update_lock = zk_client.Lock(constants.VERSION_UPDATE_LOCK_NODE)
  thread_pool = ThreadPoolExecutor(4)
  all_resources = {
    'acc': acc,
    'ua_client': ua_client,
    'zk_client': zk_client,
    'version_update_lock': version_update_lock,
    'thread_pool': thread_pool
  }

  app = web.Application([
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions', VersionsHandler,
     all_resources),
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions/([a-z0-9-]+)',
     VersionHandler, all_resources),
    ('/v1/apps/([a-z0-9-]+)/operations/([a-z0-9-]+)', OperationsHandler),
  ])
  logging.info('Starting AdminServer')
  app.listen(args.port)
  io_loop = IOLoop.current()
  io_loop.start()
