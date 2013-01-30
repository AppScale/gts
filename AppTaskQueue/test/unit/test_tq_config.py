#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest

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


class TestTaskQueueConfig(unittest.TestCase):
  """
  A set of test cases for the taskqueue configuration module.
  """
  def test_constructor(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')

  def test_load_queues_from_file(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('/some/path')
    self.assertEquals(queue_info, {'queue':[{'name': 'default',
                                             'rate': '5/s'},
                                            {'name': 'foo',
                                              'rate': '10/m'}]})

    flexmock(file_io) \
       .should_receive("read").and_return('blah').and_raise(IOError)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('/some/path')
    self.assertEquals(queue_info, {'queue':[{'name': 'default',
                                             'rate': '5/s'}]})

    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('/some/path')
    self.assertEquals(queue_info, {'queue':[{'name': 'foo',
                                             'rate': '10/m'},
                                            {'name': 'default',
                                             'rate': '5/s'},
                                            ]})

  def test_load_queues_from_db(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
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
    flexmock(datastore).should_receive("Put").\
         and_return()
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    try:
      queue_info = tqc.save_queues_to_db()
      raise
    except ValueError:
      pass
    queue_info = tqc.load_queues_from_file('/some/path')
    queue_info = tqc.save_queues_to_db()
  
  def test_create_celery_file(self):
    flexmock(file_io) \
       .should_receive("read").and_return(sample_queue_yaml2)
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    flexmock(datastore).should_receive("Get").\
         and_return({TaskQueueConfig.QUEUE_INFO: '{"queue":[{"name": "foo", "rate": "10/m"}]}'})
    tqc = TaskQueueConfig(TaskQueueConfig.RABBITMQ, 
                          'myapp')
    queue_info = tqc.load_queues_from_file('/some/path')
    queue_info = tqc.load_queues_from_db()

   
if __name__ == "__main__":
  unittest.main()    
