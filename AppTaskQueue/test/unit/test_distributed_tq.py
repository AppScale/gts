#!/usr/bin/env python

import json
import os
import sys
import unittest

from appscale.taskqueue.distributed_tq import DistributedTaskQueue
from appscale.taskqueue.tq_config import TaskQueueConfig
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io
import monit_app_configuration
import monit_interface

sample_queue_yaml = \
"""
queue:
- name: default
  rate: 5/s
- name: foo
  rate: 10/m
"""

sample_queue_yaml2 = \
"""
queue:
- name: foo
  rate: 10/m
"""


class FakeResponse():
  def __init__(self):
    pass
  def getcode(self):
    return 200
  def read(self):
    return '{"error":false}'


class FakeConnection():
  def __init__(self, url):
    pass
  def add_header(self, header, value):
    pass
  def putrequest(self, arg1, arg2):
    pass
  def endheaders(self):
    pass
  def send(self, values):
    pass
  def urlopen(self, request, values):
    return FakeResponse()


class TestDistributedTaskQueue(unittest.TestCase):
  def test_start_worker(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io).should_receive("read")\
      .and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    flexmock(monit_app_configuration).should_receive('create_config_file')\
      .and_return('')
    flexmock(monit_interface).should_receive('start').and_return(False)
    flexmock(TaskQueueConfig).should_receive("load_queues_from_file")
    flexmock(TaskQueueConfig).should_receive("create_celery_worker_scripts")
    flexmock(TaskQueueConfig).should_receive("create_celery_file")

    db_access = flexmock()
    dtq = DistributedTaskQueue(db_access)

    json_request = {}
    json_request = json.dumps(json_request)
    self.assertEquals(
      dtq.start_worker(json_request),
      json.dumps({'error': True, 'reason': 'Missing app_id tag'}))

    json_request = "fefwoinfwef=fwf23onr2or3"
    json_response = dtq.start_worker(json_request)
    self.assertEquals(
      json_response,
      json.dumps({'error': True, 'reason': 'Badly formed JSON'}))

    json_request = {'app_id':'my-app'}
    json_request = json.dumps(json_request)
    print(dtq.start_worker(json_request))
    assert 'true' in dtq.start_worker(json_request)

    flexmock(monit_interface).should_receive('start').and_return(True)
  
    json_request = {'app_id':'my-app'}
    json_request = json.dumps(json_request)
    print(dtq.start_worker(json_request))
    assert 'false' in dtq.start_worker(json_request)

  def test_stop_worker(self):
    flexmock(os).should_receive("system").and_return(None)
    flexmock(monit_interface).should_receive('stop').and_return(False)
    flexmock(file_io).should_receive("delete").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io).should_receive("read")\
      .and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")

    db_access = flexmock()
    dtq = DistributedTaskQueue(db_access)

    json_request = {'app_id': 'test_app'}
    response = dtq.stop_worker(json.dumps(json_request))
    self.assertTrue(json.loads(response)['error'])

    flexmock(monit_interface).should_receive('stop').and_return(True)
    response = dtq.stop_worker(json.dumps(json_request))
    self.assertFalse(json.loads(response)['error'])

if __name__ == "__main__":
  unittest.main()    
