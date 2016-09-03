#!/usr/bin/env python

import os
import sys
import unittest

from flexmock import flexmock

from appscale.taskqueue.queue import InvalidQueueConfiguration
from appscale.taskqueue.queue import PushQueue
from appscale.taskqueue.tq_config import TaskQueueConfig

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

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
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml)
    flexmock(TaskQueueConfig).should_receive('load_queues_from_file')
    TaskQueueConfig('myapp')

  def test_load_queues_from_file(self):
    self.maxDiff = None

    flexmock(file_io).should_receive("mkdir").and_return(None)
    app_id = 'myapp'

    # Test queue sample.
    flexmock(TaskQueueConfig).should_receive("get_queue_file_location").\
      and_return("/path/to/file")
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml)
    expected_info = [{'name': 'default', 'rate': '5/s'},
                     {'name': 'foo', 'rate': '10/m'}]
    expected_queues = {info['name']: PushQueue(info, app_id)
                       for info in expected_info}
    flexmock(TaskQueueConfig).should_receive('load_queues_from_file').\
      and_return(expected_queues)
    tqc = TaskQueueConfig(app_id)
    self.assertEquals(tqc.queues, expected_queues)

    # Test queue sample 2.
    flexmock(TaskQueueConfig).should_receive("get_queue_file_location").\
      and_return("/path/to/file")
    flexmock(file_io).should_receive("read").and_return(sample_queue_yaml2)
    expected_info = [{'name': 'foo', 'rate': '10/m'},
                     {'name': 'default', 'rate': '5/s'}]
    expected_queues = {info['name']: PushQueue(info, app_id)
                       for info in expected_info}
    flexmock(TaskQueueConfig).should_receive('load_queues_from_file').\
      and_return(expected_queues)
    tqc = TaskQueueConfig(app_id)
    self.assertEquals(tqc.queues, expected_queues)

    # Test without queues.
    flexmock(TaskQueueConfig).should_receive("get_queue_file_location").\
      and_return("")
    flexmock(file_io).should_receive("read").and_raise(IOError)
    expected_info = [{'name': 'default', 'rate': '5/s'}]
    expected_queues = {info['name']: PushQueue(info, app_id)
                       for info in expected_info}
    flexmock(TaskQueueConfig).should_receive('load_queues_from_file').\
      and_return(expected_queues)
    tqc = TaskQueueConfig(app_id)
    self.assertEquals(tqc.queues, expected_queues)

  def test_load_queues_from_xml_file(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)

    app_id = 'myapp'

    flexmock(TaskQueueConfig).should_receive("get_queue_file_location").\
      and_return("/path/to/file")
    flexmock(file_io).should_receive("read").and_return(sample_queue_xml)
    expected_info = [
      {'max_concurrent_requests': '300',
       'rate': '100/s',
       'bucket_size': '100',
       'name': 'default',
       'retry_parameters': {'task_age_limit': '3d'}},
      {'max_concurrent_requests': '100',
       'rate': '100/s',
       'bucket_size': '100',
       'name': 'mapreduce-workers',
       'retry_parameters': {'task_age_limit': '3d'}}
    ]
    expected_queues = {info['name']: PushQueue(info, app_id)
                       for info in expected_info}
    flexmock(TaskQueueConfig).should_receive('load_queues_from_file').\
      and_return(expected_queues)
    tqc = TaskQueueConfig(app_id)
    self.assertEquals(tqc.queues, expected_queues)

  def test_create_celery_file(self):
    flexmock(TaskQueueConfig).should_receive("get_celery_queue_name").\
      and_return("")
    flexmock(file_io).should_receive("write").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)

    tqc = TaskQueueConfig('myapp')

    # making sure it does not throw an exception
    self.assertEquals(tqc.create_celery_file(),
                      TaskQueueConfig.CELERY_CONFIG_DIR + "myapp" + ".py")
 
  def test_create_celery_worker_scripts(self):
    flexmock(TaskQueueConfig).should_receive("get_celery_queue_name").\
      and_return("")
    flexmock(file_io).should_receive("write").and_return(None)
    flexmock(file_io).should_receive("mkdir").and_return(None)

    tqc = TaskQueueConfig('myapp')

    header_template = os.path.join(os.path.dirname(__file__), '../../appscale',
                                   'taskqueue', 'templates', 'header.py')
    with open(header_template) as header_template_file:
      file1 = header_template_file.read()

    task_template = os.path.join(os.path.dirname(__file__), '../../appscale',
                                 'taskqueue', 'templates', 'task.py')
    with open(task_template) as task_template_file:
      file2 = task_template_file.read()

    flexmock(file_io).should_receive('write').and_return(None)
    flexmock(file_io).should_receive("read").and_return(file1).\
      and_return(file2)
    self.assertEquals(tqc.create_celery_worker_scripts(),
                      TaskQueueConfig.CELERY_WORKER_DIR + 'app___myapp.py')

  def test_queue_name_validation(self):
    app_id = 'guestbook'
    valid_names = ['hello', 'hello-hello', 'HELLO-world-1']
    invalid_names = ['hello_hello5354', 'hello$hello', 'hello@hello',
                     'hello&hello', 'hello*hello', 'a'*101]
    for name in valid_names:
      PushQueue({'name': name}, app_id)

    for name in invalid_names:
      self.assertRaises(
        InvalidQueueConfiguration, PushQueue, {'name': name}, app_id)
