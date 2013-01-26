#!/usr/local/Python-2.7.3/python
# Programmer: Navraj Chohan <raj@appscale.com>
# See LICENSE file
""" 
A tornado web service for handling TaskQueue request from application servers.
"""
import tornado.httpserver
import tornado.ioloop
import tornado.web

import distributed_tq

from google.appengine.api.taskqueue import taskqueue_service_pb

from google.appengine.ext.remote_api import remote_api_pb

# Default port this service runs on
SERVER_PORT = 64839

class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receieves different 
  types of HTTP requests.
  """
  def initialize(self, task_queue):
    """ Initialization of database and celery. 
 
    Args:
      task_queue = DistributedTaskQueue object.
    """ 
    self._task_queue = task_queue

  def unknown_request(self, app_id, http_request_data, pb_type):
    """ Function which handles unknown protocol buffers.
   
    Args:
      app_id: Name of the application.
      http_request_data: The encoded protocol buffer from the AppServer.
    Raise:
      NotImplementedError: This unknown type is not implemented.
    """
    raise NotImplementedError("Unknown request of operation %s" % pb_type)

  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is 
        the request from the AppServer in an encoded protocol buffer 
        format.
    """
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data  = app_data.split(':')
    app_id = app_data[0]
 
    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)

    self.finish()

  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
        up in json.
    """
    self.write("{'status':'up'}")
    self.finish()

  def remote_request(self, app_id, http_request_data):
    """ Receives a remote request to which it should give the correct 
        response. The http_request_data holds an encoded protocol buffer
        of a certain type. Each type has a particular response type. 
    
    Args:
      app_id: The application ID that is sending this request.
      http_request_data: Encoded protocol buffer.
    """
    apirequest = remote_api_pb.Request()
    apirequest.ParseFromString(http_request_data)
    apiresponse = remote_api_pb.Response()
    response = None
    errcode = 0
    errdetail = ""
    apperror_pb = None
    if not apirequest.has_method():
      errcode = taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Method was not set in request"
      apirequest.set_method("NOT_FOUND")
    if not apirequest.has_request():
      errcode = taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST
      errdetail = "Request missing in call"
      apirequest.set_method("NOT_FOUND")
      apirequest.clear_request()

    method = apirequest.method()
    http_request_data = apirequest.request()

    if method == "FetchQueueStats":
      response, errcode, errdetail = self._task_queue.fetch_queue_stats(app_id,
                                                 http_request_data)
    elif method == "PurgeQueue":
      response, errcode, errdetail = self._task_queue.purge_queue(app_id,
                                                 http_request_data)
    elif method == "Delete":
      response, errcode, errdetail = self._task_queue.delete(app_id,
                                                 http_request_data)
    elif method == "QueryAndOwnTasks":
      response, errcode, errdetail = self._task_queue.query_and_own_tasks(
                                                 app_id,
                                                 http_request_data)
    elif method == "Add":
      response, errcode, errdetail = self._task_queue.add(app_id,
                                                 http_request_data)
    elif method == "BulkAdd":
      response, errcode, errdetail = self._task_queue.bulk_add(app_id,
                                                 http_request_data)
    elif method == "ModifyTaskLease":
      response, errcode, errdetail = self._task_queue.modify_task_lease(app_id,
                                                 http_request_data)
    elif method == "UpdateQueue":
      response, errcode, errdetail = self._task_queue.update_queue(app_id,
                                                 http_request_data)
    elif method == "FetchQueues":
      response, errcode, errdetail = self._task_queue.fetch_queue(app_id,
                                                 http_request_data)
    elif method == "QueryTasks":
      response, errcode, errdetail = self._task_queue.query_tasks(app_id,
                                                 http_request_data)
    elif method == "FetchTask":
      response, errcode, errdetail = self._task_queue.fetch_task(app_id,
                                                 http_request_data)
    elif method == "ForceRun":
      response, errcode, errdetail = self._task_queue.force_run(app_id,
                                                 http_request_data)
    elif method == "DeleteQueue":
      response, errcode, errdetail = self._task_queue.delete_queue(app_id,
                                                 http_request_data)
    elif method == "PauseQueue":
      response, errcode, errdetail = self._task_queue.pause_queue(app_id,
                                                 http_request_data)
    elif method == "DeleteGroup":
      response, errcode, errdetail = self._task_queue.delete_group(app_id,
                                                 http_request_data)
    elif method == "UpdateStorageLimit":
      response, errcode, errdetail = self._task_queue.update_storage_limit(
                                                 app_id,
                                                 http_request_data)
   
   
    apiresponse.set_response(response)
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    self.write(apiresponse.Encode())

def main():
  """ Main function which initializes and starts the tornado server. """
  task_queue = distributed_tq.DistributedTaskQueue()
  tq_application = tornado.web.Application([
    (r"/*", MainHandler, dict(task_queue=task_queue))
  ])

  server = tornado.httpserver.HTTPServer(tq_application)
  server.listen(SERVER_PORT)

  while 1:
    try:
      tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
      print "Server interrupted by user, terminating..."
      exit(1)

if __name__ == '__main__':
  main()
