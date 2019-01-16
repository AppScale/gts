import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from mock import patch, MagicMock

from appscale.common import appscale_info, file_io


class TestAppScaleInfo(unittest.TestCase):

  def test_get_num_cpus(self):
    self.assertNotEqual(0, appscale_info.get_num_cpus())

  @patch.object(file_io, 'read')
  def test_get_db_info(self, read_mock):
    read_mock.return_value = '''---
:keyname: appscale
:replication: '1'
:table: cassandra
'''
    db_info = appscale_info.get_db_info()
    self.assertIsInstance(db_info, dict)
    self.assertEqual(db_info[':table'], 'cassandra')
    self.assertEqual(db_info[':replication'], '1')
    self.assertEqual(db_info[':keyname'], 'appscale')
    read_mock.assert_called_once_with('/etc/appscale/database_info.yaml')

  @patch.object(file_io, 'read')
  def test_get_all_ips(self, read_mock):
    read_mock.return_value = '192.168.0.1\n129.168.0.2\n184.48.65.89'
    self.assertEquals(
      appscale_info.get_all_ips(),
      ['192.168.0.1', '129.168.0.2', '184.48.65.89'],
    )
    read_mock.assert_called_once_with('/etc/appscale/all_ips')

  @patch.object(file_io, 'read')
  def test_get_taskqueue_nodes(self, read_mock):
    # Not empty
    read_mock.return_value = '192.168.0.1\n129.168.0.2\n184.48.65.89'
    self.assertEquals(
      appscale_info.get_taskqueue_nodes(),
      ['192.168.0.1','129.168.0.2','184.48.65.89'],
    )
    read_mock.assert_called_once_with('/etc/appscale/taskqueue_nodes')
    # Empty
    read_mock.return_value = ''
    self.assertEquals(appscale_info.get_taskqueue_nodes(), [])

  @patch.object(file_io, 'read')
  def test_get_db_proxy(self, read_mock):
    read_mock.return_value = '192.168.0.1\n129.168.0.2\n184.48.65.89'
    self.assertEquals(appscale_info.get_db_proxy(), '192.168.0.1')
    read_mock.assert_called_once_with('/etc/appscale/load_balancer_ips')

  @patch.object(file_io, 'read')
  def test_get_tq_proxy(self, read_mock):
    read_mock.return_value = '192.168.0.1\n129.168.0.2\n184.48.65.89'
    self.assertEquals(appscale_info.get_db_proxy(), '192.168.0.1')
    read_mock.assert_called_once_with('/etc/appscale/load_balancer_ips')

  def test_get_zk_node_ips(self):
    # File exists
    open_mock = MagicMock()
    open_mock.return_value.__enter__.return_value = StringIO('ip1\nip2')
    with patch.object(appscale_info, 'open', open_mock):
      self.assertEquals(appscale_info.get_zk_node_ips(), [u'ip1', u'ip2'])
      open_mock.assert_called_once_with('/etc/appscale/zookeeper_locations')

    # IO Error
    open_mock = MagicMock()
    open_mock.return_value.__enter__.side_effect = IOError('Boom')
    with patch.object(appscale_info, 'open', open_mock):
      self.assertEquals(appscale_info.get_zk_node_ips(), [])
      open_mock.assert_called_once_with('/etc/appscale/zookeeper_locations')

  @patch.object(file_io, 'read')
  def test_get_search_location(self, read_mock):
    # File exists
    read_mock.return_value = 'private_ip:port'
    self.assertEquals(appscale_info.get_search_location(), 'private_ip:port')
    # IO Error
    read_mock.side_effect = IOError('Boom')
    self.assertEquals(appscale_info.get_search_location(), '')

if __name__ == '__main__':
  unittest.main()
