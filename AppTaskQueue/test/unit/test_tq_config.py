#!/usr/bin/env python

import os
import sys
import unittest
import urllib2

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from tq_config import TaskQueueConfig

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.api import api_base_pb
from google.appengine.api import datastore

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

sample_queue_xml = \
"""<?xml version="1.0" encoding="utf-8"?>
<queue-entries>
  <total-storage-limit>1000M</total-storage-limit>
  <queue>
    <name>default</name>
    <rate>100/s</rate>
    <bucket-size>100</bucket-size>
    <retry-parameters>
      <task-age-limit>3d</task-age-limit>
    </retry-parameters>
    <max-concurrent-requests>
      300
    </max-concurrent-requests>
  </queue>
  <queue>
    <name>mapreduce-workers</name>
    <rate>100/s</rate>
    <bucket-size>100</bucket-size>
    <retry-parameters>
      <task-age-limit>3d</task-age-limit>
    </retry-parameters>
    <max-concurrent-requests>
      100
    </max-concurrent-requests>
  </queue>
</queue-entries>
"""

class FakeConnection():
  def __init__(self):
    pass
  def add_header(self, arg1, arg2):
    pass
class FakeResponse():
  def __init__(self):
    pass
  def read(self):
    return "{}" 

class TestTaskQueueConfig(unittest.TestCase):
  """
  A set of test cases for the taskqueue configuration module.
  """
  def test_constructor(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')

  def test_load_queues_from_file(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml)
    flexmock(file_io) \
       .should_receive("exists").and_return(True)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('app_id')
    self.assertEquals(queue_info, {'queue':[{'name': 'default',
                                             'rate': '5/s'},
                                            {'name': 'foo',
                                              'rate': '10/m'}]})

    flexmock(file_io) \
       .should_receive("read").and_return('blah').and_raise(IOError)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('app_id')
    self.assertEquals(queue_info, {'queue':[{'name': 'default',
                                             'rate': '5/s'}]})

    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('app_id')
    self.assertEquals(queue_info, {'queue':[{'name': 'foo',
                                             'rate': '10/m'},
                                            {'name': 'default',
                                             'rate': '5/s'},
                                            ]})

  def test_load_queues_from_xml_file(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_xml)
    flexmock(file_io) \
       .should_receive("exists").and_return(False).and_return(True)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('app_id')
    self.assertEquals(queue_info, {'queue': [{'max_concurrent_requests': '300', 'rate': '100/s', 'bucket_size': '100', 'name': 'default', 'retry_parameters': {'task_age_limit': '3d'}}, {'max_concurrent_requests': '100', 'rate': '100/s', 'bucket_size': '100', 'name': 'mapreduce-workers', 'retry_parameters': {'task_age_limit': '3d'}}]})

  def test_load_queues_from_db(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_db()
    self.assertEquals(queue_info, {'queue':[{'name': 'foo',
                                             'rate': '10/m'},
                                            ]})

  def test_save_queues_to_db(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive('exists').and_return(True)
    flexmock(datastore).should_receive("Put").\
         and_return()
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    try:
      queue_info = tqc.save_queues_to_db()
      raise
    except ValueError:
      pass
    queue_info = tqc.load_queues_from_file('app_id')
    queue_info = tqc.save_queues_to_db()
  
  def test_load_queues(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("exists").and_return(True)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('app_id')
    queue_info = tqc.load_queues_from_db()

  def test_create_celery_file(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("exists").and_return(True)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(file_io) \
       .should_receive("mkdir").and_return(None)
    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml2)
    queue_info = tqc.load_queues_from_file('app_id')
    queue_info = tqc.load_queues_from_db()

    # making sure it does not throw an exception
    self.assertEquals(tqc.create_celery_file(TaskQueueConfig.QUEUE_INFO_DB),
                      TaskQueueConfig.CELERY_CONFIG_DIR + "myapp" + ".py")
    self.assertEquals(tqc.create_celery_file(TaskQueueConfig.QUEUE_INFO_FILE),
                      TaskQueueConfig.CELERY_CONFIG_DIR + "myapp" + ".py")
 
  def test_create_celery_worker_scripts(self):
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io).should_receive("write").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)

    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    flexmock(file_io) \
       .should_receive("exists").and_return(True)
    queue_info = tqc.load_queues_from_file('app_id')
    queue_info = tqc.load_queues_from_db()
    FILE1 = open(os.path.dirname(os.path.realpath(__file__)) + '/../../templates/header.py', 'r')
    file1 = FILE1.read()
    FILE1.close()
    FILE2 = open(os.path.dirname(os.path.realpath(__file__)) + '/../../templates/task.py', 'r')
    file2 = FILE2.read()
    FILE2.close()

    flexmock(file_io).should_receive('write').and_return(None)
    flexmock(file_io).should_receive("read").and_return(file1).and_return(file2)
    self.assertEquals(tqc.create_celery_worker_scripts(TaskQueueConfig.QUEUE_INFO_DB), TaskQueueConfig.CELERY_WORKER_DIR + 'app___myapp.py')
    self.assertEquals(tqc.create_celery_worker_scripts(TaskQueueConfig.QUEUE_INFO_FILE), TaskQueueConfig.CELERY_WORKER_DIR + 'app___myapp.py')

  def test_validate_queue_name(self):
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io).should_receive("write").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)

    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    tqc.validate_queue_name("hello")
    tqc.validate_queue_name("hello_hello5354")
    try:
      tqc.validate_queue_name("hello-hello")
      raise
    except NameError:
      pass
    try:
      tqc.validate_queue_name("hello$hello")
      raise
    except NameError:
      pass
    try:
      tqc.validate_queue_name("hello@hello")
      raise
    except NameError:
      pass
    try:
      tqc.validate_queue_name("hello&hello")
      raise
    except NameError:
      pass
    try:
      tqc.validate_queue_name("hello*hello")
      raise
    except NameError:
      pass
if __name__ == "__main__":
  unittest.main()    
