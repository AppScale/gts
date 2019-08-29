"""
storage module implements import source and export targets.
At the moment there's only S3 backend is available, though
Cloud Storage or filesystem backend can be implemented later.

Expected data structure is approximately following:
  STORAGE:
  - backup-2019-07-04:
    - project-F/namespace-L/index-M:
      - backup-page-1
      - backup-page-2
        ...
      - backup-page-N
      ...
    + project-K/namespace-L/index-M
    ...
  + backup-2019-07-11

Every backup page contains serialized ProtocolBuffer message of type
search_pb2.IndexDocument. It contains multiple documents which can be
easily indexed to Search Service.
"""

import boto3
from botocore import exceptions

from appscale.search.protocols import search_pb2


class S3Source(object):
  """ Import source implementation based on S3 backend """

  def __init__(self, endpoint_url, bucket_name, access_key_id, secret_key):
    """
    Args:
      endpoint_url: a str - S3 endpoint URL.
      bucket_name: a str - S3 bucket name to import from.
      access_key_id: a str - S3 access key ID.
      secret_key: a str - S3 secret key.
    """
    self._endpoint_url = endpoint_url
    self._s3 = boto3.resource('s3', endpoint_url=endpoint_url,
                              aws_access_key_id=access_key_id,
                              aws_secret_access_key=secret_key)
    self._bucket = self._s3.Bucket(bucket_name)
    self._iterator = None

  def iter_indexes(self):
    """ Generates full index name tuples present in the bucket:
    (<PROJECT_ID>, <NAMESPACE>, <INDEX>).
    """
    indexes_set = {
      tuple(object_summary.key.split('/')[:3])
      for object_summary in self._bucket.objects.all()
    }
    for project_id, namespace, index in indexes_set:
      if namespace == '__default__':
        namespace = None
      yield project_id, namespace, index

  def iter_object_keys(self, project_id, namespace, index):
    """ Generates S3 object keys corresponding to specified search index.

    Args:
      project_id: a str - GAE project ID.
      namespace: a str - namespace name.
      index: a str - search index name.
    """
    if not namespace:
      namespace = '__default__'
    key_prefix = '{}/{}/{}/'.format(project_id, namespace, index)
    for object_summary in self._bucket.objects.filter(Prefix=key_prefix):
      yield object_summary.key

  def get_index_documents_pb(self, key):
    """ Fetches object body from S3 amd prepares
    search_pb2.IndexDocumentRequest.

    Args:
      key: a str: S3 object key.
    Returns:
      an instance of search_pb2.IndexDocumentRequest.
    """
    object_body = self._bucket.Object(key).get()['Body'].read()
    index_documents_pb = search_pb2.IndexDocumentRequest()
    index_documents_pb.ParseFromString(object_body)
    return index_documents_pb


class S3Target(object):
  """ Export target implementation based on S3 backend """

  def __init__(self, endpoint_url, bucket_name, access_key_id, secret_key):
    """
    Args:
      endpoint_url: a str - S3 endpoint URL.
      bucket_name: a str - S3 bucket name to import from.
      access_key_id: a str - S3 access key ID.
      secret_key: a str - S3 secret key.
    """
    self._endpoint_url = endpoint_url
    self._s3 = boto3.resource('s3', endpoint_url=endpoint_url,
                              aws_access_key_id=access_key_id,
                              aws_secret_access_key=secret_key)
    self._bucket = self._s3.Bucket(bucket_name)
    try:
      self._bucket.create()
    except exceptions.ClientError as err:
      if err.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
        raise

  def save(self, project_id, namespace, index_name, index_documents_pb):
    """ Saves search_pb2.IndexDocumentRequest to S3 storage.

    Args:
      project_id: a str - GAE project ID.
      namespace: a str - namespace name.
      index_name: a str - search index name.
      index_documents_pb: a search_pb2.IndexDocumentRequest.
    """
    if not namespace:
      namespace = '__default__'
    first_doc_id = index_documents_pb.params.document[0].id
    key = '{}/{}/{}/{}...'.format(
      project_id, namespace, index_name, first_doc_id
    )
    body = index_documents_pb.SerializeToString()
    self._bucket.put_object(Key=key, Body=body)
