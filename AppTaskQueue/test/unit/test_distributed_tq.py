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

class TestDistributedTaskQueue(unittest.TestCase):
  """
  A set of test cases for the distributed taskqueue module
  """
  def test_fetch_queue_stats(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete(self):   
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_purge_queue(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_query_and_own_tasks(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_bulk_add(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_modify_task_lease(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_update_queue(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_fetch_queue(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_query_tasks(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_fetch_task(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_force_run(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete_queue(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_pause_queue(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_delete_group(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

  def test_update_storage_limit(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

    dtq = DistributedTaskQueue()

if __name__ == "__main__":
  unittest.main()    
