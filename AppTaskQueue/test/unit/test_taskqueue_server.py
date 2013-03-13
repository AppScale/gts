#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from distributed_tq import DistributedTaskQueue

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))  
from google.appengine.api import api_base_pb

def mock_file_io():
  flexmock(file_io).should_receive("mkdir").and_return(None)
  flexmock(file_io) \
     .should_receive("read").and_return("192.168.0.1")
  flexmock(file_io) \
     .should_receive("write").and_return(None)


class TestDistributedTaskQueue(unittest.TestCase):
  """
  A set of test cases for the distributed taskqueue module
  """
  def test_fetch_queue_stats(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_delete(self):   
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_purge_queue(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_query_and_own_tasks(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_modify_task_lease(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_update_queue(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_fetch_queue(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_query_tasks(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_fetch_task(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_force_run(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_delete_queue(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_pause_queue(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_delete_group(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

  def test_update_storage_limit(self):
    mock_file_io()
    dtq = DistributedTaskQueue()

if __name__ == "__main__":
  unittest.main()    
