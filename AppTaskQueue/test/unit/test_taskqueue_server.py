#!/usr/bin/env python
import unittest
from unittest.mock import MagicMock, patch

from appscale.common import file_io

from appscale.taskqueue import distributed_tq


class TestDistributedTaskQueue(unittest.TestCase):
  """
  A set of test cases for the distributed taskqueue module
  """

  @staticmethod
  def test_distributed_tq_initialization():
    zk_client = MagicMock()
    lb_ips_patcher = patch(
      'appscale.common.appscale_info.get_load_balancer_ips',
      return_value=['192.168.0.1']
    )
    db_proxy_patcher = patch(
      'appscale.common.appscale_info.get_db_proxy',
      return_value=['192.168.0.1']
    )
    with lb_ips_patcher:
      with db_proxy_patcher:
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
