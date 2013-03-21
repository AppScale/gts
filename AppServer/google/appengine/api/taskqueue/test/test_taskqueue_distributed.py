import os
import sys
import unittest
from flexmock import flexmock

taskqueue = "{0}/../../../../..".format(os.path.dirname(__file__))
sys.path.append(taskqueue)
from google.appengine.api.taskqueue import taskqueue_distributed
from google.appengine.api.taskqueue import taskqueue_service_pb


class FakeAddResponse():
  def __init__(self):
    pass
  def set_chosen_task_name(self, name):
    return


class FakeAddRequest():
  def __init__(self):
    pass
  def app_id(self):
    return "appid"
  def set_task_name(self, name):
    return 
  def set_url(self, url):
    return
  def set_app_id(self, url):
    return
  def url(self):
    return "url"
  def has_transaction(self):
    return False
  def has_queue_name(self):
    return True
  def queue_name(self):
    return "queue_name"
  def has_task_name(self): 
    return False
  def CopyFrom(self, request):
    return

class FakeBulkAddResponse():
  def __init__(self):
    pass
  def taskresult_size(self):
    return 1
  def set_url(self, url):
    return
  def set_app_id(self, url):
    return
  def url(self):
    return "url"
  def CopyFrom(self, request):
    return
  def add_taskresult(self):
    return FakeTaskResult()
  def add_add_request(self):
    return FakeAddRequest()
  def taskresult_list(self):
    return [FakeTaskResult()]
  def taskresult(self, index):
    return FakeTaskResult()


class FakeTaskResult():
  def __init__(self):
    pass
  def set_result(self, result):
    return
  def set_chosen_task_name(self, name):
    return
  def result(self):
    return taskqueue_service_pb.TaskQueueServiceError.OK
  def has_chosen_task_name(self):
    return True
  def chosen_task_name(self):
    return 'name'

class FakeBulkAddRequest():
  def __init__(self):
    pass
  def add_request_size(self):
    return 1
  def add_request_list(self):
    return [FakeAddRequest()]
  def add_add_request(self):
    return FakeAddRequest()
  def add_request(self, index):
    return FakeAddRequest()
  def CopyFrom(self, request):
    return

class TestTaskqueueDistributed(unittest.TestCase):
  def test_taskqueue_service_stub(self):
    """ Test the constructor. """
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)

  def test_dynamic_add(self):
    flexmock(taskqueue_service_pb)
    taskqueue_service_pb.should_receive("TaskQueueBulkAddRequest").\
      and_return(FakeBulkAddRequest())
    taskqueue_service_pb.should_receive("TaskQueueBulkAddResponse").\
      and_return(FakeBulkAddResponse())
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    tqd.should_receive("_RemoteSend").and_return()
    tqd.should_receive("_Dynamic_BulkAdd").and_return()

    tqd = taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)
    self.assertEquals(None, tqd._Dynamic_Add(FakeAddRequest(), FakeAddResponse()))

  def test_dynamic_bulkadd(self):
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    flexmock(taskqueue_service_pb) 
    taskqueue_service_pb.should_receive("TaskQueueBulkAddRequest").\
      and_return(FakeBulkAddRequest())
    taskqueue_service_pb.should_receive("TaskQueueBulkAddResponse").\
      and_return(FakeBulkAddResponse())
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    tqd.should_receive("_RemoteSend").and_return()
    tqd = taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)
     
    self.assertEquals(None, tqd._Dynamic_BulkAdd(FakeBulkAddRequest(), None))

  def test_add_transactional_bulk_task(self):
    tqd = flexmock(taskqueue_distributed.TaskQueueServiceStub)
    tqd.should_receive("__GetTQLocation").and_return("some_location")
    tqd.should_receive("_RemoteSend").and_return()
    tqd = taskqueue_distributed.TaskQueueServiceStub("app_id", "hostname", 12345)
    response = FakeBulkAddResponse() 
    self.assertEquals(response, tqd._AddTransactionalBulkTask(FakeBulkAddRequest(),
      response))

    

if __name__ == "__main__":
  unittest.main()
