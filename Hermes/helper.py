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
    The response body on success, a failure message otherwise.
  """

  http_client = tornado.httpclient.HTTPClient()
  try:
    response = http_client.fetch(request)
    result = json.loads(response.body)
  except tornado.httpclient.HTTPError as http_error:
    logging.error("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
    result = {'success': False, 'reason': hermes_constants.HTTPError}
  except Exception as exception:
    logging.exception("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
    result = {'success': False, 'reason': str(exception)}
  http_client.close()
  return result

def urlfetch_async(request, callback=None):
  """ Uses a Tornado Async HTTP client to perform HTTP requests.

  Args:
    request: A tornado.httpclient.HTTPRequest object.
    callback: The callback function.
  Returns:
    The response body on success, a failure message otherwise.
  """

  http_client = tornado.httpclient.AsyncHTTPClient()
  try:
    response = http_client.fetch(request, callback)
    result = json.loads(response.body)
  except tornado.httpclient.HTTPError as http_error:
    logging.error("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
    result = {'success': False, 'reason': hermes_constants.HTTPError}
  except Exception as exception:
    logging.exception("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
    result = {'success': False, 'reason': exception.message}
  http_client.close()
  return result

def get_br_service_url(node):
  """ Constructs the br_service url.

  Args:
    node: A str, the IP for which we want the br_service URL.
  Returns:
    A str, the complete URL of a br_service instance.
  """
  return "https://{0}:{1}{2}".format(node, hermes_constants.BR_SERVICE_PORT,
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
  # Add logic for choosing nodes that will perform a task more intelligently.

  node_info = [{
    'host': get_br_service_url(appscale_info.get_db_master_ip()),
    'role': 'db_master',
    'index': None
  }]

  index = 0
  for node in appscale_info.get_db_slave_ips():
    node_info.append({
      'host': get_br_service_url(node),
      'role': 'db_slave',
      'index': index
    })
    index += 1

  index = 0
  for node in appscale_info.get_zk_node_ips():
    node_info.append({
      'host': get_br_service_url(node),
      'role': 'zk',
      'index': index
    })
    index += 1

  return node_info

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
    data['type'] = 'cassandra_{0}'.format(type)
    data['object_name'] = "gs://{0}{1}".format(bucket_name,
      hermes_constants.DB_MASTER_OBJECT_NAME)
  elif role == 'db_slave':
    data['type'] = 'cassandra_{0}'.format(type)
    data['object_name'] = "gs://{0}{1}".format(bucket_name,
      hermes_constants.DB_SLAVE_OBJECT_NAME.format(index))
  elif role == 'zk':
    data['type'] = 'zookeeper_{0}'.format(type)
    data['object_name'] = "gs://{0}{1}".format(bucket_name,
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
