""" Helper functions for Hermes operations. """

import json
import logging
import os
import sys
import tornado.httpclient

import hermes_constants
from custom_exceptions import MissingRequestArgs

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

class JSONTags(object):
  """ A class containing all JSON tags used for Hermes functionality. """
  BUCKET_NAME = 'bucket_name'
  DEPLOYMENT_ID = 'deployment_id'
  OBJECT_NAME = 'object_name'
  STATUS = 'status'
  SUCCESS = 'success'
  TASK_ID = 'task_id'
  TYPE = 'type'
  REASON = 'reason'

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
    validate_cert=False)

def urlfetch(request):
  """ Uses a Tornado HTTP client to perform HTTP requests.

  Args:
    request: A tornado.httpclient.HTTPRequest object.
  Returns:
    True on success, a failure message otherwise.
  """
  http_client = tornado.httpclient.HTTPClient()
  try:
    http_client.fetch(request)
    result = {JSONTags.SUCCESS : True}
  except tornado.httpclient.HTTPError as http_error:
    logging.error("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
    result = {JSONTags.SUCCESS: False, JSONTags.REASON: hermes_constants.HTTPError}
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
    result = {JSONTags.SUCCESS: False, JSONTags.REASON: hermes_constants.HTTPError}
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
    AppScale Portal.
  """
  # TODO
  return 'secret'

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

def create_br_json_data(role, type, bucket_name, index):
  """ Creates a JSON object with the given parameters in the format that is
  supported by the backup_recovery_service.

  Args:
    role: A str, the role of the node that the data is for.
    type: A str, the type of the task to be executed.
    bucket_name: A str, the name of the bucket to use.
    index: An int, the numeric value assigned to a db slave or zookeeper node
      to distinguish it from the rest of its peers.
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
  return json.dumps(data)

def send_remote_request(request, result_queue):
  """ Sends out a task request to the appropriate host and stores the
  response in the designated queue.

  Args:
    request: A tornado.httpclient.HTTPRequest to be sent.
    result_queue: A threadsafe Queue for putting the result in.
  """
  logging.info('Sending remote request: {0}'.format(request.body))
  result_queue.put(urlfetch(request))
