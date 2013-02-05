#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import json
import os
import sys
import unittest
import urllib2

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from distributed_tq import DistributedTaskQueue
from tq_config import TaskQueueConfig

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io
import god_app_interface
import god_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.api import api_base_pb

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
  """
  A set of test cases for the distributed taskqueue module
  """
  def test_setup_queues(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("").\
       and_return(sample_queue_yaml)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(TaskQueueConfig)\
       .should_receive("create_celery_file").and_return("/some/file")
    flexmock(TaskQueueConfig)\
       .should_receive("create_celery_worker_scripts").and_return("/some/file")
    flexmock(DistributedTaskQueue)\
       .should_receive("start_workers").and_return({})
 
    dtq = DistributedTaskQueue()
    response = json.loads(dtq.setup_queues('{}'))
    self.assertEquals(response['error'], True)
    self.assertEquals(response['reason'], 'Missing queue_yaml tag')

    response = json.loads(dtq.setup_queues('{"app_id":"hey"}'))
    self.assertEquals(response['error'], True)
    self.assertEquals(response['reason'], 'Missing queue_yaml tag')

    response = json.loads(dtq.setup_queues('{"queue_yaml":"hey"}'))
    self.assertEquals(response['error'], True)
    self.assertEquals(response['reason'], 'Missing app_id tag')
  
    response = json.loads(dtq.setup_queues('{"app'))
    self.assertEquals(response['error'], True)
    self.assertEquals(response['reason'], 'Badly formed JSON')

    response = json.loads(dtq.setup_queues('{"app_id":"hey", "queue_yaml":"/var/log/appscale/guestbook/app/queue.yaml"}'))
    self.assertEquals(response['error'], True)
    self.assertEquals(response['reason'], 'Missing command tag')

    response = json.loads(dtq.setup_queues('{"app_id":"hey", "queue_yaml":"/var/log/appscale/guestbook/app/queue.yaml", "command":"update"}'))
 
  def test_start_workers(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(TaskQueueConfig)\
       .should_receive("create_celery_file").and_return("/some/file")
    flexmock(TaskQueueConfig)\
       .should_receive("create_celery_worker_scripts").and_return("/some/file")
 
    dtq = DistributedTaskQueue()
    dtq.start_workers("hi", {})
    flexmock(urllib2)\
       .should_receive("Request").and_return(FakeConnection('/some/url'))
    
    results =  {'192.168.0.1':{}, '129.168.0.2':{}, '184.46.65.89':{}}
    self.assertEqual(dtq.start_workers("hi", results), results)
 
  def test_fetch_queue_stats(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete(self):   
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_purge_queue(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_query_and_own_tasks(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_modify_task_lease(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_update_queue(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_fetch_queue(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_query_tasks(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_fetch_task(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_force_run(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete_queue(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_pause_queue(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete_group(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_update_storage_limit(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_get_taskqueue_nodes(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    dtq = DistributedTaskQueue() 
    self.assertEquals(dtq.get_taskqueue_nodes(), 
                     ["192.168.0.1","129.168.0.2","184.48.65.89"])

    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89\n")
    dtq = DistributedTaskQueue() 
    self.assertEquals(dtq.get_taskqueue_nodes(), 
                     ["192.168.0.1","129.168.0.2","184.48.65.89"])

    flexmock(file_io) \
       .should_receive("read").and_return("")
    dtq = DistributedTaskQueue() 
    self.assertEquals(dtq.get_taskqueue_nodes(), [])

  def test_setup_workers(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    flexmock(god_app_interface).should_receive('create_config_file').and_return('')
    flexmock(god_interface).should_receive('start') \
       .and_return(False)
   
    dtq = DistributedTaskQueue() 
    json_request = {'worker_script':'/some/path', 'queue': [{'name':'queue-name', 'rate': '5/s'}]}
    json_request = json.dumps(json_request)
    self.assertEquals(dtq.setup_workers(json_request), 
                 json.dumps({'error': True, 'reason': 'Missing app_id tag'}))

    json_request = {'worker_script':'/some/path',
                    'queue': [{'name':'queue-name', 'rate': '5/s'}]}
    json_request = json.dumps(json_request)

    self.assertEquals(dtq.setup_workers(json_request), 
                 json.dumps({'error': True, 'reason': 'Missing app_id tag'}))

    json_request = "fefwoinfwef=fwf23onr2or3"
    json_response = dtq.setup_workers(json_request)
    self.assertEquals(json_response, json.dumps({'error': True, 'reason': 'Badly formed JSON'}))

    json_request = {'worker_script':'/some/path',
                    'app_id':'my-app',
                    'queue': [{'name':'queue-name', 'rate': '5/s'}]}
    json_request = json.dumps(json_request)
    assert 'true' in dtq.setup_workers(json_request)

    flexmock(god_interface).should_receive('start') \
       .and_return(True)
  
    json_request = {'worker_script':'/some/path',
                    'app_id':'my-app',
                    'queue': [{'name':'queue-name', 'rate': '5/s'}]}
    json_request = json.dumps(json_request)
    assert 'false' in dtq.setup_workers(json_request)

  def test_stop_workers(self):
    flexmock(god_interface).should_receive('stop') \
       .and_return(False)
    flexmock(file_io).should_receive("delete").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    dtq = DistributedTaskQueue() 
    json_request = {'app_id':'test_app'}
    self.assertEquals(json.loads(dtq.stop_workers(json.dumps(json_request)))['error'],
                      True)
    flexmock(god_interface).should_receive('stop') \
       .and_return(True)
    self.assertEquals(json.loads(dtq.stop_workers(json.dumps(json_request)))['error'],
                      False)
   
 
if __name__ == "__main__":
  unittest.main()    
