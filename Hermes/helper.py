""" Helper functions for Hermes operations. """

import logging
import tornado.httpclient

import constants
from custom_exceptions import MissingRequestArgs

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
    The response object on success, None on failure.
  """

  http_client = tornado.httpclient.HTTPClient()
  try:
    response = http_client.fetch(request)
    return response
  except tornado.httpclient.HTTPError as http_error:
    logging.info("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
  except Exception as exception:
    logging.info("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
  http_client.close()
  return None

def urlfetch_async(request, callback=None):
  """ Uses a Tornado Async HTTP client to perform HTTP requests.

  Args:
    request: A tornado.httpclient.HTTPRequest object.
    callback: The callback function.
  Returns:
    The response object on success, None on failure.
  """

  http_client = tornado.httpclient.AsyncHTTPClient()
  try:
    response = http_client.fetch(request, callback)
    return response
  except tornado.httpclient.HTTPError as http_error:
    logging.info("Error while trying to fetch '{0}': {1}".format(request.url,
      str(http_error)))
  except Exception as exception:
    logging.info("Exception while trying to fetch '{0}': {1}".format(
      request.url, str(exception)))
  http_client.close()
  return None

def get_br_service_url(node):
  """ Constructs the br_service url.

  Args:
    node: A str, the IP for which we want the br_service URL.
  Returns:
    A str, the complete URL of a br_service instance.
  """
  return "https://{0}:{1}".format(node, constants.BR_SERVICE_PORT,
    constants.BR_SERVICE_PATH)

def get_deployment_id():
  """ Retrieves the deployment ID for this AppScale deployment.

  Returns:
    A str, the secret key used for registering this deployment with the
    AppScale Portal.
  """
  # TODO
  return 'secret'
