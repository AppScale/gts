#!/usr/bin/env python

import json
import os
import socket
import sys
import unittest
import urllib2

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api.taskqueue  import taskqueue_service_pb
from google.appengine.ext.remote_api import remote_api_pb
# AppScale must already be running with RabbitMQ
class TestTaskAddTask(unittest.TestCase):
  def test_bulkadd(self):
    app_id = 'test_app'
    bulk_add_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    item = bulk_add_request.add_add_request()
    item.set_app_id(app_id)
    item.set_queue_name('default') 
    item.set_task_name('babaganoose')
    item.set_eta_usec(0)
    item.set_method(taskqueue_service_pb.TaskQueueAddRequest.GET)
    item.set_mode(taskqueue_service_pb.TaskQueueMode.PUSH)
    retry = item.mutable_retry_parameters()
    retry.set_retry_limit(5)
    retry.set_max_doublings(3)
    retry.set_max_backoff_sec(2)
    retry.set_min_backoff_sec(1)
    host = socket.gethostbyname(socket.gethostname())
    item.set_url('http://' + host + ':64839/doesnotexist_retry') 
    host = socket.gethostbyname(socket.gethostname())
    req = urllib2.Request('http://' + host + ':64839')
    api_request = remote_api_pb.Request()
    api_request.set_method("BulkAdd")
    api_request.set_service_name("taskqueue")
    api_request.set_request(bulk_add_request.Encode())
    remote_request = api_request.Encode()
    req.add_header('Content-Length', str(len(remote_request)))
    req.add_header('protocolbuffertype', 'Request') 
    req.add_header('appdata', app_id) 
    response = urllib2.urlopen(req, remote_request)
    api_response = response.read()
    api_response = remote_api_pb.Response(api_response) 
    bulk_add_response = taskqueue_service_pb.TaskQueueBulkAddResponse(api_response.response())
    print bulk_add_response
    self.assertEquals(response.getcode(), 200)
             
if __name__ == "__main__":
  unittest.main()
