import argparse
import datetime
import os
import sys

from tornado import gen, ioloop

from .client import BadRequest, Datastore, DatastoreError

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


@gen.coroutine
def test_merge_query_with_null(locations):
  datastore = Datastore(locations, PROJECT_ID)

  query = Query('Greeting', _app=PROJECT_ID)
  results = yield datastore.run_query(query)
  for entity in results:
    yield datastore.delete([entity.key()])

  entity = Entity('Greeting', _app=PROJECT_ID)
  create_time = datetime.datetime.now()
  entity['content'] = None
  entity['create_time'] = create_time
  yield datastore.put(entity)

  entity = Entity('Greeting', _app=PROJECT_ID)
  entity['content'] = 'hi'
  entity['create_time'] = create_time
  yield datastore.put(entity)

  entity = Entity('Greeting', _app=PROJECT_ID)
  entity['create_time'] = None
  yield datastore.put(entity)

  query = Query('Greeting', {'content =': None, 'create_time =': create_time},
                _app=PROJECT_ID)
  response = yield datastore.run_query(query)
  if len(response) != 1:
    raise Exception('Expected 1 result. Received: {}'.format(response))

  entity = response[0]
  if entity['content'] is not None or entity['create_time'] != create_time:
    raise Exception('Unexpected entity: {}'.format(entity))

  query = Query('Greeting', _app=PROJECT_ID)
  results = yield datastore.run_query(query)
  for entity in results:
    yield datastore.delete([entity.key()])


@gen.coroutine
def test_separator_in_name(locations):
  datastore = Datastore(locations, PROJECT_ID)

  entity = Entity('Greeting', name='Test:1', _app=PROJECT_ID)
  create_time = datetime.datetime.utcnow()
  entity['color'] = 'red'
  entity['create_time'] = create_time
  yield datastore.put(entity)

  query = Query('Greeting', {'color =': 'red', 'create_time =': create_time},
                _app=PROJECT_ID)
  response = yield datastore.run_query(query)
  if len(response) != 1:
    raise Exception('Expected 1 result. Received: {}'.format(response))

  entity = response[0]
  if entity['color'] != 'red' or entity['create_time'] != create_time:
    raise Exception('Unexpected entity: {}'.format(entity))


@gen.coroutine
def test_separator_in_kind(locations):
  datastore = Datastore(locations, PROJECT_ID)

  # The Cloud Datastore API allows these key names, but AppScale forbids them
  # because ':' is used to separate kind names and key names when encoding a
  # path.
  entity = Entity('Invalid:Kind', _app=PROJECT_ID)
  try:
    yield datastore.put(entity)
  except BadRequest:
    pass
  else:
    raise Exception('Expected BadRequest. No error was thrown.')


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--locations', nargs='+')
  args = parser.parse_args()

  io_loop = ioloop.IOLoop.current()
  io_loop.run_sync(lambda: test_separator_in_kind(args.locations))
  io_loop.run_sync(lambda: test_separator_in_name(args.locations))
  io_loop.run_sync(lambda: test_merge_query_with_null(args.locations))
