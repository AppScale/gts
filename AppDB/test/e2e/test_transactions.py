import sys

import argparse
import os
import random
import uuid
from tornado import gen, ioloop, httpclient

APPSCALE_PYTHON_APPSERVER = os.path.realpath(
  os.path.join(os.path.abspath(__file__), '..', '..', '..', '..', 'AppServer'))
sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import Entity, Key
from google.appengine.datastore import datastore_pb
from google.appengine.ext.remote_api import remote_api_pb

PROJECT_ID = 'guestbook'


class DatastoreError(Exception):
  pass


class Datastore(object):
  SERVICE_NAME = 'datastore_v3'

  def __init__(self, locations):
    self._client = httpclient.AsyncHTTPClient()
    self._locations = locations

  @gen.coroutine
  def begin_transaction(self):
    request = datastore_pb.BeginTransactionRequest()
    request.set_app(PROJECT_ID)
    response = yield self._make_request('BeginTransaction', request.Encode())
    start_response = datastore_pb.Transaction(response)
    raise gen.Return(start_response.handle())

  @gen.coroutine
  def get(self, key, txid=None):
    request = datastore_pb.GetRequest()
    req_key = request.add_key()
    req_key.MergeFrom(key._ToPb())

    if txid is not None:
      req_tx = request.mutable_transaction()
      req_tx.set_app(PROJECT_ID)
      req_tx.set_handle(txid)

    encoded_response = yield self._make_request('Get', request.Encode())
    get_response = datastore_pb.GetResponse(encoded_response)
    response_entity = get_response.entity(0).entity()
    if not response_entity.has_key():
      return

    raise gen.Return(Entity.FromPb(response_entity))

  @gen.coroutine
  def put(self, entity, txid=None):
    request = datastore_pb.PutRequest()
    req_entity = request.add_entity()
    req_entity.MergeFrom(entity.ToPb())

    if txid is not None:
      req_tx = request.mutable_transaction()
      req_tx.set_app(PROJECT_ID)
      req_tx.set_handle(txid)

    yield self._make_request('Put', request.Encode())

  @gen.coroutine
  def commit(self, txid):
    request = datastore_pb.Transaction()
    request.set_app(PROJECT_ID)
    request.set_handle(txid)
    yield self._make_request('Commit', request.Encode())

  @gen.coroutine
  def _make_request(self, method, body):
    request = remote_api_pb.Request()
    request.set_service_name(self.SERVICE_NAME)
    request.set_method(method)
    request.set_request(body)

    location = random.choice(self._locations)
    url = 'http://{}'.format(location)
    headers = {'protocolbuffertype': 'Request', 'appdata': PROJECT_ID}
    response = yield self._client.fetch(
      url, method='POST', body=request.Encode(), headers=headers)
    api_response = remote_api_pb.Response(response.body)

    if api_response.has_application_error():
      raise DatastoreError(api_response.application_error().detail())

    if api_response.has_exception():
      raise DatastoreError(str(api_response.exception()))

    raise gen.Return(api_response.response())


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
  datastore = Datastore(locations)

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
