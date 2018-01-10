import unittest

from mock import ANY
from mock import call
from mock import MagicMock

from appscale.datastore.zkappscale.transaction_manager import (
  ProjectTransactionManager)


class TestDatastoreServer(unittest.TestCase):
  def test_create_transaction_id(self):
    project_id = 'guestbook'
    project_node = '/appscale/apps/{}'.format(project_id)

    zk_client = MagicMock()
    tx_manager = ProjectTransactionManager(project_id, zk_client)

    # Ensure the first created node is ignored.
    created_nodes = ['{}/txids/tx0000000000'.format(project_node),
                     '{}/txids/tx0000000001'.format(project_node)]
    zk_client.create = MagicMock(side_effect=created_nodes)
    self.assertEqual(tx_manager.create_transaction_id(xg=False), 1)
    calls = [
      call('{}/txids/tx'.format(project_node), value=ANY, sequence=True),
      call('{}/txids/tx'.format(project_node), value=ANY, sequence=True)]
    zk_client.create.assert_has_calls(calls)

    # Ensure the manual offset works.
    tx_manager._txid_manual_offset = 10
    created_nodes = ['{}/txids/tx0000000015'.format(project_node)]
    zk_client.create = MagicMock(side_effect=created_nodes)
    self.assertEqual(tx_manager.create_transaction_id(xg=False), 25)
    calls = [
      call('{}/txids/tx'.format(project_node), value=ANY, sequence=True)]
    zk_client.create.assert_has_calls(calls)
    tx_manager._txid_manual_offset = 0

    # Ensure the automatic rollover works.
    created_nodes = ['{}/txids/tx-2147483647'.format(project_node),
                     '{}/txids2'.format(project_node),
                     '{}/txids2/tx0000000000'.format(project_node)]
    zk_client.create = MagicMock(side_effect=created_nodes)
    zk_client.get_children = MagicMock(return_value=['txids', 'txids2'])
    self.assertEqual(tx_manager.create_transaction_id(xg=False), 2147483648)
    calls = [
      call('{}/txids/tx'.format(project_node), value=ANY, sequence=True),
      call('{}/txids2'.format(project_node)),
      call('{}/txids2/tx'.format(project_node), value=ANY, sequence=True)]
    zk_client.create.assert_has_calls(calls)

  def test_delete_transaction_id(self):
    project_id = 'guestbook'
    project_node = '/appscale/apps/{}'.format(project_id)

    zk_client = MagicMock()
    tx_manager = ProjectTransactionManager(project_id, zk_client)

    # A small transaction ID should be located in the first bucket.
    tx_manager._delete_counter = MagicMock()
    tx_manager.delete_transaction_id(5)
    tx_manager._delete_counter.assert_called_with(
      '{}/txids/tx0000000005'.format(project_node))

    # Transactions above the max counter value should be in a different bucket.
    tx_manager._delete_counter = MagicMock()
    tx_manager.delete_transaction_id(2147483649)
    tx_manager._delete_counter.assert_called_with(
      '{}/txids2/tx0000000001'.format(project_node))

    # Offset transactions should be corrected.
    tx_manager._txid_manual_offset = 2 ** 31
    tx_manager._delete_counter = MagicMock()
    tx_manager.delete_transaction_id(2 ** 31 * 2)
    tx_manager._delete_counter.assert_called_with(
      '{}/txids2/tx0000000000'.format(project_node))
    tx_manager._txid_manual_offset = 0

  def test_get_open_transactions(self):
    project_id = 'guestbook'
    project_node = '/appscale/apps/{}'.format(project_id)

    zk_client = MagicMock()
    tx_manager = ProjectTransactionManager(project_id, zk_client)

    # Counters in multiple active buckets should be used.
    active_buckets = ('{}/txids'.format(project_node),
                      '{}/txids2'.format(project_node))
    tx_manager._active_containers = MagicMock(return_value=active_buckets)
    zk_responses = [['{}/txids/tx2147483646'.format(project_node),
                     '{}/txids/tx2147483647'.format(project_node)],
                    ['{}/txids2/tx0000000000'.format(project_node),
                     '{}/txids2/tx0000000001'.format(project_node)]]
    zk_client.get_children = MagicMock(side_effect=zk_responses)
    open_txids = [2147483646, 2147483647, 2147483648, 2147483649]
    self.assertListEqual(tx_manager.get_open_transactions(), open_txids)

    # A manual offset should affect the list of open transactions.
    tx_manager._txid_manual_offset = 10
    active_buckets = ('{}/txids'.format(project_node),)
    tx_manager._active_containers = MagicMock(return_value=active_buckets)
    zk_response = ['{}/txids/tx0000000001'.format(project_node),
                   '{}/txids/tx0000000002'.format(project_node)]
    zk_client.get_children = MagicMock(return_value=zk_response)
    open_txids = [11, 12]
    self.assertListEqual(tx_manager.get_open_transactions(), open_txids)
    tx_manager._txid_manual_offset = 0
