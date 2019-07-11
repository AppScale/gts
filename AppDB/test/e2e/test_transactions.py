import sys

import os
import uuid
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test

from .client import Datastore, DatastoreError

APPSCALE_PYTHON_APPSERVER = os.path.realpath(
  os.path.join(os.path.abspath(__file__), '..', '..', '..', '..', 'AppServer'))
sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import Entity, Key, Query

PROJECT_ID = 'guestbook'


@gen.coroutine
def increment_counter(datastore, counter_id, retries):
  txid = yield datastore.begin_transaction()
  key = Key.from_path('Counter', counter_id, _app=PROJECT_ID)
  entity = yield datastore.get(key, txid=txid)
  if entity is None:
    entity = Entity('Counter', name=counter_id, _app=PROJECT_ID)

  if 'count' not in entity:
    entity['count'] = 0

  entity['count'] += 1
  yield datastore.put(entity, txid=txid)
  try:
    yield datastore.commit(txid)
  except DatastoreError:
    if retries < 1:
      raise

    yield increment_counter(datastore, counter_id, retries - 1)


@gen.coroutine
def get_count(datastore, counter_id):
  key = Key.from_path('Counter', counter_id, _app=PROJECT_ID)
  entity = yield datastore.get(key)
  if entity is None:
    raise gen.Return(0)

  raise gen.Return(entity.get('count', 0))


class TestConcurrentCounter(AsyncTestCase):
  def setUp(self):
    super(TestConcurrentCounter, self).setUp()
    locations = os.environ['DATASTORE_LOCATIONS'].split()
    self.datastore = Datastore(locations, PROJECT_ID)

  def tearDown(self):
    self.tear_down_helper()
    super(TestConcurrentCounter, self).tearDown()

  @gen_test
  def tear_down_helper(self):
    query = Query('Counter', _app=PROJECT_ID)
    results = yield self.datastore.run_query(query)
    yield self.datastore.delete([entity.key() for entity in results])

  @gen_test
  def test_concurrent_counter(self):
    counter_id = uuid.uuid4().hex
    expected_count = 20
    yield [increment_counter(self.datastore, counter_id, expected_count)
           for _ in range(expected_count)]
    count = yield get_count(self.datastore, counter_id)
    self.assertEqual(count, expected_count)
