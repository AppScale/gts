""" Helper functions for Hermes operations. """

import json
import logging
import os
import SOAPpy
import sys
import threading
import tornado.httpclient
import urllib

from socket import error as socket_error

import hermes_constants
from custom_hermes_exceptions import MissingRequestArgs

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppDB/backup/"))
from backup_recovery_constants import StorageTypes
import backup_recovery_helper as BR

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppServer'))
from google.appengine.api.appcontroller_client import AppControllerException

# The number of retries we should do to report the status of a completed task
# to the AppScale Portal.
REPORT_RETRIES = 5

# Structure for keeping status of tasks.
TASK_STATUS = {}

# Lock for accessing TASK_STATUS.
TASK_STATUS_LOCK = threading.Lock()

# A list of tasks that we report status for.
REPORT_TASKS = ['backup', 'restore']

class JSONTags(object):
  """ A class containing all JSON tags used for Hermes functionality. """
  ALL_STATS = 'all_stats'
  BUCKET_NAME = 'bucket_name'
  BODY = 'body'
  DEPLOYMENT_ID = 'deployment_id'
  ERROR = 'error'
  OBJECT_NAME = 'object_name'
  REASON = 'reason'
  STATUS = 'status'
  STORAGE = 'storage'
  SUCCESS = 'success'
  TASK_ID = 'task_id'
  TIMESTAMP = 'timestamp'
  TYPE = 'type'
  UNREACHABLE = 'unreachable'

class NodeInfoTags(object):
  """ A class containing all the dict keys for node information on this
  AppScale deployment.
  """
  HOST = 'host'
  INDEX = 'index'
  NUM_NODES = 'num_nodes'
  ROLE = 'role'

def create_request(url=None, method=None, body=None):
  """ Creates a tornado.httpclient.HTTPRequest with the given parameters.

  Args:
    url: A str, the URL to call.
    method: A str, one of GET, POST.
    body: A JSON object, the encoded dictionary that will be posted as payload.
  Returns:
    A tornado.httpclient.HTTPRequest object.
  Raises:
    MissingRequestArgs exception if one or more of the arguments is not set.
  """
  if not url or not method:
    raise MissingRequestArgs
  return tornado.httpclient.HTTPRequest(url=url, method=method, body=body,
    validate_cert=False, request_timeout=hermes_constants.REQUEST_TIMEOUT)

def urlfetch(request):
  """ Uses a Tornado HTTP client to perform HTTP requests.

  Args:
    request: A tornado.httpclient.HTTPRequest object.
  Returns:
    True on success, a failure message otherwise.
  """
  http_client = tornado.httpclient.HTTPClient()

  try:
    response = http_client.fetch(request)
    result = {JSONTags.SUCCESS: True, JSONTags.BODY: response.body}
  except tornado.httpclient.HTTPError as http_error:
    logging.error("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
    result = {JSONTags.SUCCESS: False,
      JSONTags.REASON: hermes_constants.HTTPError}
  except Exception as exception:
    logging.exception("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
    result = {JSONTags.SUCCESS: False, JSONTags.REASON: str(exception)}

  http_client.close()
  return result

def urlfetch_async(request, callback=None):
  """ Uses a Tornado Async HTTP client to perform HTTP requests.

  Args:
    request: A tornado.httpclient.HTTPRequest object.
    callback: The callback function.
  Returns:
    True on success, a failure message otherwise.
  """
  http_client = tornado.httpclient.AsyncHTTPClient()

  try:
    http_client.fetch(request, callback)
    result = {JSONTags.SUCCESS: True}
  except tornado.httpclient.HTTPError as http_error:
    logging.error("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
    result = {JSONTags.SUCCESS: False,
      JSONTags.REASON: hermes_constants.HTTPError}
  except Exception as exception:
    logging.exception("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
    result = {JSONTags.SUCCESS: False, JSONTags.REASON: exception.message}

  http_client.close()
  return result

def get_br_service_url(node):
  """ Constructs the br_service url.

  Args:
    node: A str, the IP for which we want the br_service URL.
  Returns:
    A str, the complete URL of a br_service instance.
  """
  return "http://{0}:{1}{2}".format(node, hermes_constants.BR_SERVICE_PORT,
    hermes_constants.BR_SERVICE_PATH)

def get_deployment_id():
  """ Retrieves the deployment ID for this AppScale deployment.

  Returns:
    A str, the secret key used for registering this deployment with the
    AppScale Portal. None if the deployment is not registered.
  """
  try:
    acc = appscale_info.get_appcontroller_client()
    if acc.deployment_id_exists():
      return acc.get_deployment_id()
  except AppControllerException:
    logging.exception("AppControllerException while querying for deployment "
      "ID.")
    return None

def get_node_info():
  """ Creates a list of JSON objects that contain node information and are
  needed to perform a backup/restore task on the current AppScale deployment.
  """

  # TODO
  # Add logic for choosing minimal set of nodes that need to perform a task.
  # e.g. Only the node that owns the entire keyspace.

  nodes = [{
    NodeInfoTags.HOST: get_br_service_url(appscale_info.get_db_master_ip()),
    NodeInfoTags.ROLE: 'db_master',
    NodeInfoTags.INDEX: None
  }]

  index = 0
  for node in appscale_info.get_db_slave_ips():
    host = get_br_service_url(node)
    # Make sure we don't send the same request on DB roles that reside on the
    # same node.
    if host not in nodes[0].values():
      nodes.append({
        NodeInfoTags.HOST: host,
        NodeInfoTags.ROLE: 'db_slave',
        NodeInfoTags.INDEX: index
      })
      index += 1

  index = 0
  for node in appscale_info.get_zk_node_ips():
    nodes.append({
      NodeInfoTags.HOST: get_br_service_url(node),
      NodeInfoTags.ROLE: 'zk',
      NodeInfoTags.INDEX: index
    })
    index += 1

  return nodes

def create_br_json_data(role, type, bucket_name, index, storage):
  """ Creates a JSON object with the given parameters in the format that is
  supported by the backup_recovery_service.

  Args:
    role: A str, the role of the node that the data is for.
    type: A str, the type of the task to be executed.
    bucket_name: A str, the name of the bucket to use.
    index: An int, the numeric value assigned to a db slave or zookeeper node
      to distinguish it from the rest of its peers.
    storage: A str, the type of backend storage to use for a backup/recovery op.
  Returns:
    A JSON object on success, None otherwise.
  """

  data = {}
  if role == 'db_master':
    data[JSONTags.TYPE] = 'cassandra_{0}'.format(type)
    data[JSONTags.OBJECT_NAME] = "gs://{0}{1}".format(bucket_name,
      hermes_constants.DB_MASTER_OBJECT_NAME)
  elif role == 'db_slave':
    data[JSONTags.TYPE] = 'cassandra_{0}'.format(type)
    data[JSONTags.OBJECT_NAME] = "gs://{0}{1}".format(bucket_name,
      hermes_constants.DB_SLAVE_OBJECT_NAME.format(index))
  elif role == 'zk':
    data[JSONTags.TYPE] = 'zookeeper_{0}'.format(type)
    data[JSONTags.OBJECT_NAME] = "gs://{0}{1}".format(bucket_name,
      hermes_constants.ZK_OBJECT_NAME.format(index))
  else:
    return None

  data[JSONTags.STORAGE] = storage
  return json.dumps(data)

def delete_task_from_mem(task_id):
  """ Deletes a task and its status from memory.

  Args:
    task_id: A str, the task ID we're deleting from memory.
  """
  logging.info("Deleting task '{0}' from memory.".format(task_id))
  TASK_STATUS_LOCK.acquire(True)
  if task_id in TASK_STATUS.keys():
    del TASK_STATUS[task_id]
  TASK_STATUS_LOCK.release()

def get_all_stats():
  """ Collects platform stats from all deployment nodes.

  Returns:
    A dictionary containing all the monitoring stats, if all nodes are
    accessible. {"success": False, "error": message} otherwise.
  """
  all_stats = {}

  secret = appscale_info.get_secret()
  logging.debug("Retrieved deployment secret: {}".format(secret))
  for ip in appscale_info.get_all_ips():
    appcontroller_endpoint = "https://{}:{}".format(ip,
      hermes_constants.APPCONTROLLER_PORT)
    logging.debug("Connecting to AC at: {}".format(appcontroller_endpoint))
    # Do a SOAP call to the AppController on that IP to get stats.
    server = SOAPpy.SOAPProxy(appcontroller_endpoint)
    try:
      all_stats[ip] = json.loads(server.get_all_stats(secret))
    except SOAPpy.SOAPException as soap_exception:
      logging.exception("Exception while performing SOAP call to "
        "{}".format(appcontroller_endpoint))
      logging.exception(soap_exception)
      all_stats[ip] = {JSONTags.ERROR: JSONTags.UNREACHABLE}
    except socket_error as serr:
      logging.error("Socket error while performing SOAP call to "
        "{}".format(appcontroller_endpoint))
      logging.error(serr)
      all_stats[ip] = {JSONTags.ERROR: JSONTags.UNREACHABLE}

  return all_stats

def report_status(task, task_id, status):
  """ Sends a status report for the given task to the AppScale Portal.
  Upon success, it calls a function to delete the task from memory.
  On error, it adds a callback to retry.

  Args:
    task_id: A str, the task ID we're sending a status report for.
    status: A str, the status for the given task.
  """
  if task in REPORT_TASKS:
    logging.debug("Sending task status to the AppScale Portal. Task: {0}, "
      "Status: {1}".format(task, status))
    url = '{0}{1}'.format(hermes_constants.PORTAL_URL,
      hermes_constants.PORTAL_STATUS_PATH)
    data = urllib.urlencode({
      JSONTags.TASK_ID: task_id,
      JSONTags.DEPLOYMENT_ID: get_deployment_id(),
      JSONTags.STATUS: status
    })
    request = create_request(url=url, method='POST', body=data)

    for _ in range(REPORT_RETRIES):
      result = urlfetch(request)

      # Delete task upon success. Retry otherwise.
      if result[JSONTags.SUCCESS]:
        delete_task_from_mem(task_id)
        return

    # Finally, just delete the task from memory. AppScale Portal will do
    # rollback for failed tasks.
    delete_task_from_mem(task_id)

def send_remote_request(request, result_queue):
  """ Sends out a task request to the appropriate host and stores the
  response in the designated queue.

  Args:
    request: A tornado.httpclient.HTTPRequest to be sent.
    result_queue: A threadsafe Queue for putting the result in.
  """
  logging.debug('Sending remote request: {0}'.format(request.body))
  result_queue.put(urlfetch(request))

def backup_apps(storage, bucket):
  """ Triggers a backup of the source code of deployed apps.

  Args:
    storage: A str, one of the StorageTypes class members.
    bucket: A str, the name of the remote bucket where the backups will be
      stored.
  Returns:
    True on success, False otherwise.
  """
  full_bucket_name = ''
  if storage == StorageTypes.GCS:
    full_bucket_name = 'gs://{0}'.format(bucket)
  return BR.app_backup(storage, full_bucket_name=full_bucket_name)

def restore_apps(storage, bucket):
  """ Triggers a restore of apps for the current deployment. Retrieves the
  source code from the backup location on the filesystem.

  Args:
    storage: A str, one of the StorageTypes class members.
    bucket: A str, the name of the remote bucket where the backups are stored.
  Returns:
    True on success, False otherwise.
  """
  return BR.app_restore(storage, bucket_name=bucket)
