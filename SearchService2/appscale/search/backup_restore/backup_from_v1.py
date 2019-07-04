import argparse
import calendar
import json
import logging
import socket
from datetime import datetime

from tornado import gen, httpclient, ioloop
from tornado.httputil import url_concat
from appscale.common.constants import LOG_FORMAT
from appscale.search.backup_restore import storage

from appscale.search.protocols import search_pb2

logger = logging.getLogger(__name__)


class Solr4FieldTypes(object):
  TEXT = "text_ws"
  TEXT_FR = "text_fr"
  TEXT_ = "text_"
  HTML = "html"
  ATOM = "atom"
  GEO = "geo"
  DATE = "date"
  NUMBER = "number"


class TransientSolrError(Exception):
  pass


class Exporter(object):

  page_size = 100

  def __init__(self, io_loop, solr_location, target):
    self.target = target
    self.solr_location = solr_location
    self.ioloop = io_loop
    self.start_time = None
    self.status = 'Not started'
    self.finish_time = None
    self.schema = self._get_schema_fields()
    self.docs_exported = 0

  async def export(self):
    self.start_time = self.ioloop.time()
    self.status = 'In progress'
    next_cursor = '*'
    while True:
      try:
        next_cursor = await self._export_page(next_cursor)
        if not next_cursor:
          self.status = 'Done'
          break
      except TransientSolrError as err:
        logger.error('Failed to export documents page ({}). Retrying...'
                     .format(err))
        await gen.sleep(5)
      except Exception as err:
        self.status = 'Failed'
        logger.exception('Unexpected error during export ({}). '
                         'Stopping export job.'.format(err))
        break
    self.finish_time = self.ioloop.time()
    logger.info('Export job has been finished and took {:.1}s'
                .format(self.finish_time - self.start_time))
    logger.info('{} of total {} documents have been successfully imported'
                .format(self.docs_exported, self.total))

  async def _export_page(self, next_cursor):
    start = self.ioloop.time()
    docs, total, next_cursor = await self._retrieve_solr_documents(next_cursor)
    elapsed = int((self.ioloop.time() - start) * 1000)
    logger.info('Retrieved {} docs ({} found) in {}ms. Next cursor: {}'
                .format(len(docs), total, elapsed, next_cursor))
    per_index_pb_messages = self._from_solr_documents(docs)
    logger.info(per_index_pb_messages)
    for index_fullname, index_documents_pb in per_index_pb_messages.items():
      project_id, namespace, index_name = index_fullname
      self.target.save(project_id, namespace, index_name, index_documents_pb)
    self.docs_exported += len(docs)
    self.total = total
    if docs:
      return next_cursor

  async def _retrieve_solr_documents(self, next_cursor):
    params = {
      'q': '*:*',
      'wt': 'json',
      'cursorMark': next_cursor,
      'sort': 'id asc',
      'rows': self.page_size
    }
    solr_url = url_concat('{}/solr/query'.format(self.solr_location), params)
    headers = {'Content-Type': 'application/json'}
    async_client = httpclient.AsyncHTTPClient()
    try:
      response = await async_client.fetch(
        solr_url, headers=headers, raise_error=True
      )
    except httpclient.HTTPError as err:
      if err.response.code >= 500:
        msg = 'HTTPError {}: {}'.format(err.response.code, err.response.reason)
        raise TransientSolrError(msg)
      raise
    except socket.error as err:
      raise TransientSolrError('SocketError: {}'.format(err))

    json_response = json.loads(response.body.decode('utf-8'))
    return (
      json_response['response']['docs'],
      json_response['response']['numFound'],
      json_response.get('nextCursorMark')
    )

  def _get_schema_fields(self):
    solr_url = '{}/solr/schema/fields'.format(self.solr_location)
    headers = {'Content-Type': 'application/json'}
    client = httpclient.HTTPClient()
    response = client.fetch(solr_url, headers=headers, raise_error=True)
    json_response = json.loads(response.body.decode('utf-8'))
    return {field['name']: field for field in json_response['fields']}

  def _from_solr_documents(self, solr_documents):
    per_index_pb_messages = {}
    for doc in solr_documents:
      index_fullname_field = doc.get('_gaeindex_name')
      if not index_fullname_field:
        logger.warning('Unrecognized document with ID "{}"'.format(doc['id']))
        continue
      index_fullname = index_fullname_field[0]
      index_fullname_tuple = tuple(index_fullname.split('_'))
      project_id, namespace, index_name = index_fullname_tuple

      if index_fullname_tuple not in per_index_pb_messages:
        index_docs_pb = search_pb2.IndexDocumentRequest()
        index_docs_pb.app_id = project_id.encode()
        index_docs_pb.params.index_spec.name = index_name
        index_docs_pb.params.index_spec.namespace = namespace
        per_index_pb_messages[index_fullname_tuple] = index_docs_pb
      else:
        index_docs_pb = per_index_pb_messages[index_fullname_tuple]

      document_pb = index_docs_pb.params.document.add()
      document_pb.id = doc['id']
      if '_gaeindex_locale' in doc:
        document_pb.language = doc['_gaeindex_locale'][0]
      for field_name, value in doc.items():
        field_name_prefix = '{}_'.format(index_fullname)
        if not field_name.startswith(field_name_prefix):
          continue
        field_info = self.schema[field_name]
        field_pb = document_pb.field.add()
        field_pb.name = field_name.split(field_name_prefix)[1]
        field_type = field_info['type']

        if field_type == Solr4FieldTypes.DATE:
          value = calendar.timegm(datetime.strptime(
            value[:-1], "%Y-%m-%dT%H:%M:%S").timetuple())
          field_pb.value.string_value = str(int(value * 1000))
          field_pb.value.type = search_pb2.FieldValue.DATE
        elif field_type == Solr4FieldTypes.TEXT:
          field_pb.value.string_value = value
          field_pb.value.type = search_pb2.FieldValue.TEXT
        elif field_type == Solr4FieldTypes.HTML:
          field_pb.value.string_value = value
          field_pb.value.type = search_pb2.FieldValue.HTML
        elif field_type == Solr4FieldTypes.ATOM:
          field_pb.value.string_value = value
          field_pb.value.type = search_pb2.FieldValue.ATOM
        elif field_type == Solr4FieldTypes.NUMBER:
          field_pb.value.string_value = str(value)
          field_pb.value.type = search_pb2.FieldValue.NUMBER
        elif field_type == Solr4FieldTypes.GEO:
          lat, lng = value.split(',')
          field_pb.value.geo.lat = float(lat)
          field_pb.value.geo.lng = float(lng)
          field_pb.value.type = search_pb2.FieldValue.GEO
        elif field_type.startswith(Solr4FieldTypes.TEXT_):
          field_pb.value.string_value = value
          field_pb.value.type = search_pb2.FieldValue.TEXT
        else:
          logger.warning(
            'Document with ID "{}" has field of unknown type "{}". '
            'Skipping..'.format(document_pb.id, field_type)
          )

    return per_index_pb_messages


def main():
  """ Start Backup process. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--solr-location', help='Host and port Solr is listening on.')
  parser.add_argument(
    '--s3-location', help='Host and port S3 is listening on.')
  parser.add_argument(
    '--s3-access-key-id', help='S3 access key ID.')
  parser.add_argument(
    '--s3-secret-key', help='S3 secret key.')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  io_loop = ioloop.IOLoop(make_current=False)
  bucket_name = 'search-backup.{:%Y-%m-%d.%H-%M-%S}'.format(datetime.now())
  export_target = storage.S3Target(
    endpoint_url=args.s3_location,
    bucket_name=bucket_name,
    access_key_id=args.s3_access_key_id,
    secret_key=args.s3_secret_key
  )
  exporter = Exporter(io_loop, args.solr_location, export_target)

  try:
    io_loop.run_sync(exporter.export)
    logger.info('Backup bucket name: {}'.format(bucket_name))
  finally:
    io_loop.close()
