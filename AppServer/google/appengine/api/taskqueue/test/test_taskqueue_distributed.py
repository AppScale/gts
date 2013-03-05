import os
import sys
import unittest
from flexmock import flexmock

sys.path.append("../../../../..")
from google.appengine.api.taskqueue import taskqueue_distributed

class FakeAddRequest():
  def __init__(self):
    pass
  def set_url(self, url):
    return
  def set_app_id(self, url):
    return
  def url(self):
    return "url"

class FakeBulkAddRequest():
  def __init__(self):
    pass
  def add_request_size(self):
    return 1
  def add_request_list(self):
    return [FakeAddRequest()]

class TestTaskqueueDistributed(unittest.TestCase):
  def test_taskqueue_service_stub(self):
    """ Test the constructor. """
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)

  def test_dynamic_add(self):
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    tqd.should_receive("_RemoteSend").and_return()
    tqd = taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)
     
    self.assertEquals(None, tqd._Dynamic_Add(FakeAddRequest(), None))

  def test_dynamic_bulkadd(self):
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    tqd.should_receive("_RemoteSend").and_return()
    tqd = taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)
     
    self.assertEquals(None, tqd._Dynamic_BulkAdd(FakeBulkAddRequest(), None))


if __name__ == "__main__":
  unittest.main()
