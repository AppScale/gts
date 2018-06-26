""" Performs TaskQueue service enqueue requests. """

import sys

from socket import error as socket_error
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPError

from appscale.common.constants import TASKQUEUE_SERVICE_PORT
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.ext.remote_api import remote_api_pb


class EnqueueError(Exception):
  """ Indicates that the tasks could not be enqueued. """
  pass


class TaskQueueClient(object):
  """ Performs TaskQueue service enqueue requests. """
  def __init__(self, locations):
    """ Creates a new TaskQueueClient.

    Args:
      locations: A list of IP addresses specifying TaskQueue service locations.
    """
    self._client = AsyncHTTPClient()
    self._locations = [':'.join([ip, str(TASKQUEUE_SERVICE_PORT)])
                       for ip in locations]

  @gen.coroutine
  def add_tasks(self, project_id, service_id, version_id, add_requests):
    """ Makes a call to the TaskQueue service to enqueue tasks.

    Args:
      project_id: A string specifying the project ID.
      service_id: A string specifying the service ID.
      version_id: A string specifying the version ID.
      add_requests: A list of TaskQueueAddRequest messages.
    Raises:
      EnqueueError if unable to enqueue tasks.
    """
    request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    for add_request in add_requests:
      request.add_add_request().MergeFrom(add_request)

    api_request = remote_api_pb.Request()
    api_request.set_method('BulkAdd')
    api_request.set_service_name('taskqueue')
    api_request.set_request(request.Encode())

    encoded_api_request = api_request.Encode()
    headers = {'ProtocolBufferType': 'Request',
               'AppData': project_id,
               'Module': service_id,
               'Version': version_id}
    api_response = None
    for location in self._locations:
      url = 'http://{}'.format(location)
      try:
        response = yield self._client.fetch(
          url, method='POST', body=encoded_api_request, headers=headers)
      except socket_error:
        # Try a different location if the load balancer is not available.
        continue
      except HTTPError as error:
        raise EnqueueError(str(error))

      api_response = remote_api_pb.Response(response.body)
      break

    if api_response is None:
      raise EnqueueError('Unable to connect to any load balancers')

    if api_response.has_application_error():
      error_pb = api_response.application_error()
      raise EnqueueError(error_pb.detail())

    if api_response.has_exception():
      raise EnqueueError(api_response.exception())

    bulk_response = taskqueue_service_pb.TaskQueueBulkAddResponse(
      api_response.response())

    if bulk_response.taskresult_size() != len(add_requests):
      raise EnqueueError('Unexpected number of task results')

    for task_result in bulk_response.taskresult_list():
      if task_result.result() != taskqueue_service_pb.TaskQueueServiceError.OK:
        raise EnqueueError('Unable to enqueue task: {}'.format(task_result))
