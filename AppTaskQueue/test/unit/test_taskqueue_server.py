#!/usr/bin/env python
import unittest

from mock import MagicMock, patch
from appscale.common import file_io

from appscale.taskqueue import distributed_tq


class TestDistributedTaskQueue(unittest.TestCase):
  """
  A set of test cases for the distributed taskqueue module
  """
  def setUp(self):
    self._read_patcher = patch.object(
      file_io, 'read', return_value='192.168.0.1')
    self.read_mock = self._read_patcher.start()

  def tearDown(self):
    self._read_patcher.stop()

  @staticmethod
  def test_distributed_tq_initialization():
    zk_client = MagicMock()
    distributed_tq.DistributedTaskQueue(zk_client)

  # TODO:
  # def test_fetch_queue_stats(self):
  # def test_delete(self):
  # def test_purge_queue(self):
  # def test_query_and_own_tasks(self):
  # def test_bulk_add(self):
  # def test_modify_task_lease(self):
  # def test_update_queue(self):
  # def test_fetch_queue(self):
  # def test_query_tasks(self):
  # def test_fetch_task(self):
  # def test_force_run(self):
  # def test_delete_queue(self):
  # def test_pause_queue(self):
  # def test_delete_group(self):
  # def test_update_storage_limit(self):


if __name__ == "__main__":
  unittest.main()
