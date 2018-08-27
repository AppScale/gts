import sys

import argparse
import os
import uuid
from tornado import gen, ioloop

from .client import Datastore, DatastoreError

APPSCALE_PYTHON_APPSERVER = os.path.realpath(
  os.path.join(os.path.abspath(__file__), '..', '..', '..', '..', 'AppServer'))
sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import Entity, Key

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
def test_concurrent_counter(locations):
  datastore = Datastore(locations, PROJECT_ID)

  counter_id = uuid.uuid4().hex
  expected_count = 20
  yield [increment_counter(datastore, counter_id, expected_count)
         for _ in range(expected_count)]
  count = yield get_count(datastore, counter_id)
  if count != expected_count:
    raise Exception('{} != {}'.format(count, expected_count))


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--locations', nargs='+')
  args = parser.parse_args()

  io_loop = ioloop.IOLoop.current()
  io_loop.run_sync(lambda: test_concurrent_counter(args.locations))
