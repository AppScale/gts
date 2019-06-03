import os
import random
import sys

from tornado import gen, httpclient


APPSCALE_PYTHON_APPSERVER = os.path.realpath(
  os.path.join(os.path.abspath(__file__), '..', '..', '..', '..', 'AppServer'))
sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import Entity
from google.appengine.datastore import datastore_pb
from google.appengine.ext.remote_api import remote_api_pb


class DatastoreError(Exception):
  pass


class BadRequest(DatastoreError):
  pass


class Datastore(object):
  SERVICE_NAME = 'datastore_v3'
  REQUEST_TIMEOUT = 60

  def __init__(self, locations, project_id):
    self.project_id = project_id
    self._client = httpclient.AsyncHTTPClient()
    self._locations = locations

  @gen.coroutine
  def begin_transaction(self):
    request = datastore_pb.BeginTransactionRequest()
    request.set_app(self.project_id)
    response = yield self._make_request('BeginTransaction', request.Encode())
    start_response = datastore_pb.Transaction(response)
    raise gen.Return(start_response.handle())

  @gen.coroutine
  def delete(self, keys):
    request = datastore_pb.DeleteRequest()
    for key in keys:
      key_pb = request.add_key()
      key_pb.MergeFrom(key._ToPb())

    yield self._make_request('Delete', request.Encode())

  @gen.coroutine
  def get(self, key, txid=None):
    request = datastore_pb.GetRequest()
    req_key = request.add_key()
    req_key.MergeFrom(key._ToPb())

    if txid is not None:
      req_tx = request.mutable_transaction()
      req_tx.set_app(self.project_id)
      req_tx.set_handle(txid)

    encoded_response = yield self._make_request('Get', request.Encode())
    get_response = datastore_pb.GetResponse(encoded_response)
    response_entity = get_response.entity(0).entity()
    if not response_entity.has_key():
      return

    raise gen.Return(Entity.FromPb(response_entity))

  @gen.coroutine
  def run_query(self, query):
    query_pb = query._ToPb()
    encoded_response = yield self._make_request('RunQuery', query_pb.Encode())
    results_pb = datastore_pb.QueryResult(encoded_response)
    raise gen.Return(
      [Entity.FromPb(entity) for entity in results_pb.result_list()])

  @gen.coroutine
  def put(self, entity, txid=None):
    request = datastore_pb.PutRequest()
    req_entity = request.add_entity()
    req_entity.MergeFrom(entity.ToPb())

    if txid is not None:
      req_tx = request.mutable_transaction()
      req_tx.set_app(self.project_id)
      req_tx.set_handle(txid)

    yield self._make_request('Put', request.Encode())

  @gen.coroutine
  def put_multi(self, entities, txid=None):
    request = datastore_pb.PutRequest()
    for entity in entities:
      req_entity = request.add_entity()
      req_entity.MergeFrom(entity.ToPb())

    if txid is not None:
      req_tx = request.mutable_transaction()
      req_tx.set_app(self.project_id)
      req_tx.set_handle(txid)

    yield self._make_request('Put', request.Encode())

  @gen.coroutine
  def commit(self, txid):
    request = datastore_pb.Transaction()
    request.set_app(self.project_id)
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
    headers = {'protocolbuffertype': 'Request', 'appdata': self.project_id}
    response = yield self._client.fetch(
      url, method='POST', body=request.Encode(), headers=headers,
      request_timeout=self.REQUEST_TIMEOUT)
    api_response = remote_api_pb.Response(response.body)

    if api_response.has_application_error():
      error = api_response.application_error()
      if error.code() == datastore_pb.Error.BAD_REQUEST:
        raise BadRequest(error.detail())

      raise DatastoreError(error.detail())

    if api_response.has_exception():
      raise DatastoreError(str(api_response.exception()))

    raise gen.Return(api_response.response())
