from mock import MagicMock, patch
from tornado import gen, testing

from appscale.hermes.producers import cassandra_stats


def future(value):
  future = gen.Future()
  future.set_result(value)
  return future


MULTINODE_STATUS = """Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address    Load       Tokens       Owns (effective)  Host ID                               Rack
UN  10.0.2.15  67.94 GiB  1            99.8%             a341df86-71e2-4054-83d6-c2d92dc75afc  rack1
UN  10.0.2.16  65.99 GiB  1            0.2%              2ceb81a6-4c49-456d-a38b-23667ee60ff9  rack1

"""

SINGLENODE_STATUS = """Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address    Load       Owns (effective)  Host ID                               Token                                    Rack
UN  10.0.2.15  337.07 MiB  100.0%            38fd1ac1-85f9-4b19-8f8f-19ef5a00d65d  bf5f65abbfab7ac2dd87145d0cde8435         rack1

"""


class TestCurrentCassandraStats(testing.AsyncTestCase):

  @patch.object(cassandra_stats.process, 'Subprocess')
  @patch.object(cassandra_stats.appscale_info, 'get_db_ips')
  @testing.gen_test
  def test_multinode(self, mock_get_db_ips, mock_subprocess):
    subprocess = MagicMock()

    # Mocking `get_db_ips` and Subprocess
    mock_get_db_ips.return_value = ['10.0.2.15', '10.0.2.16']
    mock_subprocess.return_value = subprocess
    subprocess.stdout.read_until_close.return_value = future(MULTINODE_STATUS)
    subprocess.stderr.read_until_close.return_value = future('')

    # Calling method under test
    stats = yield cassandra_stats.CassandraStatsSource.get_current()

    # Asserting expectations
    self.assertEqual(stats.missing_nodes, [])
    self.assertEqual(stats.unknown_nodes, [])
    self.assertIsInstance(stats.utc_timestamp, int)
    self.assertEqual(len(stats.nodes), 2)

    first = stats.nodes[0]
    self.assertEqual(first.address, '10.0.2.15')
    self.assertEqual(first.status, 'Up')
    self.assertEqual(first.state, 'Normal')
    self.assertEqual(first.load, int(67.94 * 1024**3))
    self.assertEqual(first.owns_pct, 99.8)
    self.assertEqual(first.tokens_num, 1)
    self.assertEqual(first.host_id, 'a341df86-71e2-4054-83d6-c2d92dc75afc')
    self.assertEqual(first.rack, 'rack1')

    second = stats.nodes[1]
    self.assertEqual(second.address, '10.0.2.16')
    self.assertEqual(second.status, 'Up')
    self.assertEqual(second.state, 'Normal')
    self.assertEqual(second.load, int(65.99 * 1024**3))
    self.assertEqual(second.owns_pct, 0.2)
    self.assertEqual(second.tokens_num, 1)
    self.assertEqual(second.host_id, '2ceb81a6-4c49-456d-a38b-23667ee60ff9')
    self.assertEqual(second.rack, 'rack1')

  @patch.object(cassandra_stats.process, 'Subprocess')
  @patch.object(cassandra_stats.appscale_info, 'get_db_ips')
  @testing.gen_test
  def test_singlenode(self, mock_get_db_ips, mock_subprocess):
    subprocess = MagicMock()

    # Mocking `get_db_ips` and Subprocess
    mock_get_db_ips.return_value = ['10.0.2.15']
    mock_subprocess.return_value = subprocess
    subprocess.stdout.read_until_close.return_value = future(SINGLENODE_STATUS)
    subprocess.stderr.read_until_close.return_value = future('')

    # Calling method under test
    stats = yield cassandra_stats.CassandraStatsSource.get_current()

    # Asserting expectations
    self.assertEqual(stats.missing_nodes, [])
    self.assertEqual(stats.unknown_nodes, [])
    self.assertIsInstance(stats.utc_timestamp, int)
    self.assertEqual(len(stats.nodes), 1)

    first = stats.nodes[0]
    self.assertEqual(first.address, '10.0.2.15')
    self.assertEqual(first.status, 'Up')
    self.assertEqual(first.state, 'Normal')
    self.assertEqual(first.load, int(337.07 * 1024**2))
    self.assertEqual(first.owns_pct, 100.0)
    self.assertEqual(first.tokens_num, 1)
    self.assertEqual(first.host_id, '38fd1ac1-85f9-4b19-8f8f-19ef5a00d65d')
    self.assertEqual(first.rack, 'rack1')

  @patch.object(cassandra_stats.process, 'Subprocess')
  @patch.object(cassandra_stats.appscale_info, 'get_db_ips')
  @testing.gen_test
  def test_missing_and_unknown(self, mock_get_db_ips, mock_subprocess):
    subprocess = MagicMock()

    # Mocking `get_db_ips` and Subprocess
    mock_get_db_ips.return_value = ['10.0.2.15', '10.0.2.missing']
    mock_subprocess.return_value = subprocess
    subprocess.stdout.read_until_close.return_value = future(MULTINODE_STATUS)
    subprocess.stderr.read_until_close.return_value = future('')

    # Calling method under test
    stats = yield cassandra_stats.CassandraStatsSource.get_current()

    # Asserting expectations
    self.assertEqual(stats.missing_nodes, ['10.0.2.missing'])
    self.assertEqual(stats.unknown_nodes, ['10.0.2.16'])
    self.assertIsInstance(stats.utc_timestamp, int)
    self.assertEqual(len(stats.nodes), 2)

    first = stats.nodes[0]
    self.assertEqual(first.address, '10.0.2.15')
    self.assertEqual(first.status, 'Up')
    self.assertEqual(first.state, 'Normal')
    self.assertEqual(first.load, int(67.94 * 1024**3))
    self.assertEqual(first.owns_pct, 99.8)
    self.assertEqual(first.tokens_num, 1)
    self.assertEqual(first.host_id, 'a341df86-71e2-4054-83d6-c2d92dc75afc')
    self.assertEqual(first.rack, 'rack1')

    second = stats.nodes[1]
    self.assertEqual(second.address, '10.0.2.16')
    self.assertEqual(second.status, 'Up')
    self.assertEqual(second.state, 'Normal')
    self.assertEqual(second.load, int(65.99 * 1024**3))
    self.assertEqual(second.owns_pct, 0.2)
    self.assertEqual(second.tokens_num, 1)
    self.assertEqual(second.host_id, '2ceb81a6-4c49-456d-a38b-23667ee60ff9')
    self.assertEqual(second.rack, 'rack1')
