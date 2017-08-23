""" A server that handles application deployments. """

import argparse
import json
import logging
import re
import sys
import time

from appscale.common import appscale_info
from appscale.common.constants import (
  HTTPCodes,
  LOG_FORMAT,
  ZK_PERSISTENT_RECONNECTS
)
from appscale.common.monit_interface import MonitOperator
from appscale.common.appscale_utils import get_md5
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
from .appengine_api import UpdateQueuesHandler
from .base_handler import BaseHandler
from .constants import (
  CustomHTTPError,
  OperationTimeout,
  REDEPLOY_WAIT,
  VALID_RUNTIMES,
  VERSION_PATH_SEPARATOR
)
from .operation import (
  CreateVersionOperation,
  DeleteVersionOperation,
  UpdateVersionOperation
)
from .operations_cache import OperationsCache
from .push_worker_manager import GlobalPushWorkerManager

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
      self.acc.update([project_id])
    except AppControllerException as error:
      message = 'Error while updating application: {}'.format(error)
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

    # Remove old revision nodes.
    version_prefix = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version['id']])
    old_revisions = [node for node in self.zk_client.get_children('/apps')
                     if node.startswith(version_prefix)
                     and node < revision_key]
    for node in old_revisions:
      logging.info('Removing hosting entries for {}'.format(node))
      self.zk_client.delete('/apps/{}'.format(node), recursive=True)

  @gen.coroutine
  def post(self, project_id, service_id):
    """ Creates or updates a version.
    
    Args:
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """
    self.authenticate()
    version = self.version_from_payload()

    if service_id != constants.DEFAULT_SERVICE:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Invalid service')

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
    utils.remove_old_archives(project_id, service_id, version)

    yield self.thread_pool.submit(self.version_update_lock.acquire)
    try:
      version = self.put_version(project_id, service_id, version)
    finally:
      self.version_update_lock.release()

    self.begin_deploy(project_id)

    operation = CreateVersionOperation(project_id, service_id, version)
    operations[operation.id] = operation

    pre_wait = REDEPLOY_WAIT if version_exists else 0
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
      new_http_port = extensions.get('httpPort')
      new_https_port = extensions.get('httpsPort')
      version = yield self.relocate_version(
        project_id, service_id, version_id, new_http_port, new_https_port)

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
    logging.info('Starting push worker manager')
    GlobalPushWorkerManager(zk_client, monit_operator)

  app = web.Application([
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions', VersionsHandler,
     all_resources),
    ('/v1/apps/([a-z0-9-]+)/services/([a-z0-9-]+)/versions/([a-z0-9-]+)',
     VersionHandler, all_resources),
    ('/v1/apps/([a-z0-9-]+)/operations/([a-z0-9-]+)', OperationsHandler),
    ('/api/queue/update', UpdateQueuesHandler, {'zk_client': zk_client})
  ])
  logging.info('Starting AdminServer')
  app.listen(args.port)
  io_loop = IOLoop.current()
  io_loop.start()
