import unittest

from flexmock import flexmock
from mock import mock
from tornado import testing, gen
from tornado.concurrent import Future

from appscale.common import file_io
from appscale.datastore import dbconstants
from appscale.datastore.cassandra_env import cassandra_interface


class TestCassandra(testing.AsyncTestCase):

  def setUp(self, *args, **kwargs):
    super(TestCassandra, self).setUp(*args, **kwargs)
    # Prepare patchers
    self.read_patcher = mock.patch.object(file_io, 'read')
    self.execute_patcher = mock.patch.object(
      cassandra_interface.TornadoCassandra, 'execute')
    self.cluster_class_patcher = mock.patch.object(
      cassandra_interface, 'Cluster')

    # Start patches
    self.read_mock = self.read_patcher.start()
    self.execute_mock = self.execute_patcher.start()
    self.cluster_class_mock = self.cluster_class_patcher.start()

    # Configure mocks
    self.read_mock.return_value = '127.0.0.1'
    self.session_mock = mock.MagicMock()
    self.connect_mock = mock.MagicMock(return_value=self.session_mock)
    self.cluster_mock = mock.MagicMock(connect=self.connect_mock)
    self.cluster_class_mock.return_value = self.cluster_mock

    # Instantiate Datastore proxy
    self.db = cassandra_interface.DatastoreProxy()

  def tearDown(self, *args, **kwargs):
    super(TestCassandra, self).tearDown(*args, **kwargs)
    self.read_patcher.stop()
    self.execute_patcher.stop()
    self.cluster_class_patcher.stop()

  @testing.gen_test
  def test_get(self):
    # Mock cassandra response
    async_response = Future()
    async_response.set_result([
      ('a', 'c1', '1'), ('a', 'c2', '2'), ('a', 'c3', '3'),
      ('b', 'c1', '4'), ('b', 'c2', '5'), ('b', 'c3', '6'),
      ('c', 'c1', '7'), ('c', 'c2', '8'), ('c', 'c3', '9'),
    ])
    self.execute_mock.return_value = async_response

    # Call function under test
    keys = ['a', 'b', 'c']
    columns = ['c1', 'c2', 'c3']
    result = yield self.db.batch_get_entity('table', keys, columns)

    # Make sure cassandra interface prepared good query
    query = self.execute_mock.call_args[0][0]
    parameters = self.execute_mock.call_args[1]["parameters"]
    self.assertEqual(
      query.query_string,
      'SELECT * FROM "table" WHERE key IN %s and column1 IN %s')
    self.assertEqual(parameters, ([b'a', b'b', b'c'], ['c1', 'c2', 'c3']) )
    # And result matches expectation
    self.assertEqual(result, {
      'a': {'c1': '1', 'c2': '2', 'c3': '3'},
      'b': {'c1': '4', 'c2': '5', 'c3': '6'},
      'c': {'c1': '7', 'c2': '8', 'c3': '9'}
    })

  @testing.gen_test
  def test_put(self):
    # Mock execute function response
    async_response = Future()
    async_response.set_result(None)
    self.execute_mock.return_value = async_response
    # Mock prepare method of session
    self.session_mock.prepare = mock.MagicMock(
      side_effect=lambda query_str: mock.MagicMock(argument=query_str))

    # Call function under test
    keys = ['a', 'b', 'c']
    columns = ['c1', 'c2', 'c3']
    cell_values = {
      'a': {'c1': '1', 'c2': '2', 'c3': '3'},
      'b': {'c1': '4', 'c2': '5', 'c3': '6'},
      'c': {'c1': '7', 'c2': '8', 'c3': '9'}
    }
    result = yield self.db.batch_put_entity('tableX', keys, columns, cell_values)

    # Make sure cassandra interface prepared good queries
    self.assertEqual(len(self.execute_mock.call_args_list), 9)
    calls_iterator = iter(self.execute_mock.call_args_list)
    expected_params_iterator = iter([
      ('a', 'c1', '1'), ('a', 'c2', '2'), ('a', 'c3', '3'),
      ('b', 'c1', '4'), ('b', 'c2', '5'), ('b', 'c3', '6'),
      ('c', 'c1', '7'), ('c', 'c2', '8'), ('c', 'c3', '9')
    ])
    for expected_params in expected_params_iterator:
      call = next(calls_iterator)
      prepare_argument = call[0][0]
      parameters = call[1]["parameters"]
      self.assertEqual(
        prepare_argument.argument,
        'INSERT INTO "tableX" (key, column1, value) VALUES (?, ?, ?)'
      )
      self.assertEqual(parameters, expected_params)
    # And result matches expectation
    self.assertEqual(result, None)

  @testing.gen_test
  def test_delete_table(self):
    # Mock cassandra response
    async_response = Future()
    async_response.set_result(None)
    self.execute_mock.return_value = async_response

    # Call function under test
    result = yield self.db.delete_table('tableY')

    # Make sure cassandra interface prepared good query
    query = self.execute_mock.call_args[0][0]
    self.assertEqual(query.query_string, 'DROP TABLE IF EXISTS "tableY"')
    self.assertEqual(len(self.execute_mock.call_args[0]), 1)  # 1 positional arg
    self.assertEqual(self.execute_mock.call_args[1], {})  # no kwargs
    # And result matches expectation
    self.assertEqual(result, None)

  @testing.gen_test
  def test_range_query(self):
    # Mock cassandra response
    async_response = Future()
    async_response.set_result([
      ('keyA', 'c1', '1'), ('keyA', 'c2', '2'),
      ('keyB', 'c1', '4'), ('keyB', 'c2', '5'),
      ('keyC', 'c1', '7'), ('keyC', 'c2', '8')
    ])
    self.execute_mock.return_value = async_response

    # Call function under test
    columns = ['c1', 'c2']
    result = yield self.db.range_query("tableZ", columns, "keyA", "keyC", 5)

    # Make sure cassandra interface prepared good query
    query = self.execute_mock.call_args[0][0]
    parameters = self.execute_mock.call_args[1]["parameters"]
    self.assertEqual(
      query.query_string,
      'SELECT * FROM "tableZ" WHERE '
      'token(key) >= %s AND '
      'token(key) <= %s AND '
      'column1 IN %s '
      'LIMIT 10 '    # 5 * number of columns
      'ALLOW FILTERING')
    self.assertEqual(parameters, (b'keyA', b'keyC', ['c1', 'c2']) )
    # And result matches expectation
    self.assertEqual(result, [
      {'keyA': {'c1': '1', 'c2': '2'}},
      {'keyB': {'c1': '4', 'c2': '5'}},
      {'keyC': {'c1': '7', 'c2': '8'}}
    ])

  @testing.gen_test
  def test_batch_mutate(self):
    app_id = 'guestbook'
    transaction = 1
    # Mock cassandra response
    async_response = Future()
    async_response.set_result(None)
    self.execute_mock.return_value = async_response

    # Call function under test making sure it doesn't through exception
    result = yield self.db.batch_mutate(app_id, [], [], transaction)

    # Simple check for now
    self.assertEqual(result, None)


if __name__ == "__main__":
  unittest.main()
