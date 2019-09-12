import datetime
import os
import sys

from tornado.testing import AsyncTestCase, gen_test

from .client import BadRequest, Datastore

APPSCALE_PYTHON_APPSERVER = os.path.realpath(
  os.path.join(os.path.abspath(__file__), '..', '..', '..', '..', 'AppServer'))
sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import Entity, Query

PROJECT_ID = 'guestbook'


class TestMergeJoinQueries(AsyncTestCase):
  def setUp(self):
    super(TestMergeJoinQueries, self).setUp()
    locations = os.environ['DATASTORE_LOCATIONS'].split()
    self.datastore = Datastore(locations, PROJECT_ID)

  def tearDown(self):
    self.tear_down_helper()
    super(TestMergeJoinQueries, self).tearDown()

  @gen_test
  def tear_down_helper(self):
    query = Query('Greeting', _app=PROJECT_ID)
    results = yield self.datastore.run_query(query)
    yield self.datastore.delete([entity.key() for entity in results])

  @gen_test
  def test_merge_query_with_null(self):
    entity = Entity('Greeting', _app=PROJECT_ID)
    create_time = datetime.datetime.now()
    entity['content'] = None
    entity['create_time'] = create_time
    yield self.datastore.put(entity)

    entity = Entity('Greeting', _app=PROJECT_ID)
    entity['content'] = 'hi'
    entity['create_time'] = create_time
    yield self.datastore.put(entity)

    query = Query('Greeting', {'content =': None, 'create_time =': create_time},
                  _app=PROJECT_ID)
    response = yield self.datastore.run_query(query)
    self.assertEqual(len(response), 1)

    entity = response[0]
    self.assertEqual(entity['content'], None)
    self.assertEqual(entity['create_time'], create_time)

  @gen_test
  def test_separator_in_name(self):
    entity = Entity('Greeting', name='Test:1', _app=PROJECT_ID)
    create_time = datetime.datetime.utcnow()
    entity['color'] = 'red'
    entity['create_time'] = create_time
    yield self.datastore.put(entity)

    query = Query('Greeting', {'color =': 'red', 'create_time =': create_time},
                  _app=PROJECT_ID)
    response = yield self.datastore.run_query(query)

    self.assertEqual(len(response), 1)

    entity = response[0]
    self.assertEqual(entity['color'], 'red')
    self.assertEqual(entity['create_time'], create_time)

  @gen_test
  def test_separator_in_kind(self):
    # The Cloud Datastore API allows these key names, but AppScale forbids them
    # because ':' is used to separate kind names and key names when encoding a
    # path.
    entity = Entity('Invalid:Kind', _app=PROJECT_ID)
    try:
      yield self.datastore.put(entity)
    except BadRequest:
      pass
    else:
      raise Exception('Expected BadRequest. No error was thrown.')


class TestQueryLimit(AsyncTestCase):
  CASSANDRA_PAGE_SIZE = 5000
  BATCH_SIZE = 20

  def setUp(self):
    super(TestQueryLimit, self).setUp()
    locations = os.environ['DATASTORE_LOCATIONS'].split()
    self.datastore = Datastore(locations, PROJECT_ID)

  def tearDown(self):
    self.tear_down_helper()
    super(TestQueryLimit, self).tearDown()

  @gen_test
  def tear_down_helper(self):
    query = Query('Greeting', _app=PROJECT_ID)
    results = yield self.datastore.run_query(query)
    batch = []
    for entity in results:
      batch.append(entity.key())
      if len(batch) == self.BATCH_SIZE:
        yield self.datastore.delete(batch)
        batch = []
    yield self.datastore.delete(batch)

  @gen_test
  def test_cassandra_page_size(self):
    entity_count = self.CASSANDRA_PAGE_SIZE + 1
    batch = []
    for _ in range(entity_count):
      entity = Entity('Greeting', _app=PROJECT_ID)
      batch.append(entity)
      if len(batch) == self.BATCH_SIZE:
        yield self.datastore.put_multi(batch)
        batch = []
    yield self.datastore.put_multi(batch)

    query = Query('Greeting', _app=PROJECT_ID)
    results = yield self.datastore.run_query(query)
    self.assertEqual(len(results), entity_count)
