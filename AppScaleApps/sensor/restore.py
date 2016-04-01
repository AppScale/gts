#!/usr/bin/env python

""" Restores data and provides a REST interface. """

import json
import logging
import os
import re
import sys

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

from base_handler import BaseHandler
from common import constants
import settings
from utils import MAPREDUCE_MIN_SHARDS
from utils import MAPREDUCE_MAX_SHARDS
from utils import parse_gs_handle
from utils import start_map
from utils import validate_gs_bucket_name

import cloudstorage
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer"))
from google.appengine.api import datastore
from google.appengine.api import urlfetch
from google.appengine.datastore import entity_pb
from mapreduce import context
from mapreduce import input_readers
from mapreduce import operation as op
from mapreduce import output_writers

# MapReduce Handlers for restoring.
RESTORE_COMPLETE_HANDLER = __name__ +  '.RestoreCompleteHandler'
RESTORE_HANDLER = __name__ + '.RestoreEntity.map'

# Input reader and output writer for MapReduce jobs.
INPUT_READER = input_readers.__name__ + '.RecordsReader'
OUTPUT_WRITER = output_writers.__name__ + '.FileRecordsOutputWriter'

def fix_keys(entity_proto, app_id):
  """ Go over keys in the given entity and update the application ID.

  Args:
    entity_proto: An EntityProto to be fixed up. All identifiable keys in the
      proto will have the 'app' field reset to match app_id.
    app_id: The desired application ID, typically os.getenv('APPLICATION_ID').
  """

  def fix_key(mutable_key):
    """ Sets the app_id for a mutable key. """
    mutable_key.set_app(app_id)
    logging.debug("Mutable key: {0}".format(mutable_key))

  def fix_property_list(property_list):
    """ Fixes the property list and fixes keys with the right app ID. """
    for prop in property_list:
      prop_value = prop.mutable_value()
      if prop_value.has_referencevalue():
        fix_key(prop_value.mutable_referencevalue())
      elif prop.meaning() == entity_pb.Property.ENTITY_PROTO:
        embedded_entity_proto = entity_pb.EntityProto()
        try:
          embedded_entity_proto.ParsePartialFromString(prop_value.stringvalue())
        except Exception:
          logging.exception('Failed to fix-keys for property %s of %s',
            prop.name(), entity_proto.key())
        else:
          fix_keys(embedded_entity_proto, app_id)
          prop_value.set_stringvalue(
            embedded_entity_proto.SerializePartialToString())

  if entity_proto.has_key() and entity_proto.key().path().element_size():
    fix_key(entity_proto.mutable_key())

  fix_property_list(entity_proto.property_list())
  fix_property_list(entity_proto.raw_property_list())

def get_backup_files(bucket_name):
  """ Gets a list of files to restore.

  Args:
    bucket_name: The bucket name.

  Returns:
    A list of strings.
  """
  all_files = []
  file_list = cloudstorage.listbucket(bucket_name)
  for ii in file_list:
    all_files.append("/gs{1}".format(bucket_name, ii.filename))
  logging.debug("File names: {0}".format(all_files))
  return all_files

def perform_restore(gs_bucket_name,
                    restore,
                    queue,
                    mapper_params):
  """ Triggers restore mapper jobs.

  Args:
    gs_bucket_name: The GS file system bucket in which to store the restore
      when using the GS file system, and otherwise ignored.
    restore: A string, the restore name.
    queue: The task queue for the restore task.
    mapper_params: The mapper parameters.

  Returns:
    The job or task IDs.
  """
  queue = queue or os.environ.get('HTTP_X_APPENGINE_QUEUENAME', 'default')
  if queue[0] == '_':
    queue = 'default'

  bucket_name, path = parse_gs_handle(gs_bucket_name, 'restore')
  gs_bucket_name = ('%s/%s' % (bucket_name, path)).rstrip('/')
  validate_gs_bucket_name(bucket_name)
  logging.info("Will restore from bucket '{0}'".format(gs_bucket_name))

  job_name = 'appscale_datastore_restore_%s_%%(kind)s' % re.sub(r'[^\w]', '_',
    restore)

  # Need to get a list of files from GCS.
  mapper_params = {
    'done_callback_handler': RESTORE_COMPLETE_HANDLER,
    'namespace': "",
    'force_ops_writes': True,
    'gs_bucket_name': bucket_name
  }
  mapper_params['files'] = get_backup_files("/{0}".format(bucket_name))
  shard_count = min(max(MAPREDUCE_MIN_SHARDS, len(mapper_params[
    'files'])), MAPREDUCE_MAX_SHARDS)
  job = start_map(job_name, RESTORE_HANDLER, INPUT_READER, None,
    mapper_params, RestoreCompleteHandler.PATH, mapreduce_params=None,
    queue_name=queue, shard_count=shard_count)
  return [job]

def start_restore(gcs_bucket):
  """ Top level function to start a restore.
 
  Args:
    gcs_bucket: The GCS bucket to restore from.

  Returns:
    A list of job IDs for the restore process.
  """
  return perform_restore(gcs_bucket, "latest", "default", {'namespace': None})

class Restore(BaseHandler):
  """ The handler to start a restore process. """

  def post(self):
    """ POST method to restore entities to datastore. """
    remote_api_key = self.request.get(constants.ApiTags.API_KEY)
    logging.debug("API key: {0}".format(remote_api_key))
    if remote_api_key != settings.API_KEY:
      self.error_out("Request with bad API key")
      return

    gcs_bucket = self.request.get('bucket')
    logging.debug("GCS bucket: {0}".format(gcs_bucket))
    if not gcs_bucket:
      self.error_out("No GCS bucket specified")
      return

    try:
      jobs = start_restore(gcs_bucket)
      json_result = {"success": True, "jobs": jobs}
    except Exception, exception:
      logging.exception("Exception while starting restore from bucket: "
        "{0}".format(gcs_bucket))
      logging.exception(exception.message)
      json_result = {"success": False}
    self.response.write(json.dumps(json_result))

class RestoreEntity(object):
  """A class which restores the entity to datastore."""

  def __init__(self):
    """ Constructor. """
    self.initialized = False
    self.app_id = None

  def initialize(self):
    """ Initializes the class variables. """
    if self.initialized:
      return
    mapper_params = context.get().mapreduce_spec.mapper.params
    original_app = mapper_params.get('original_app')
    if original_app and os.getenv('APPLICATION_ID') != original_app:
      self.app_id = os.getenv('APPLICATION_ID')
    self.initialized = True

  def map(self, record):
    """ Restore entity map handler.

    Args:
      record: A serialized entity_pb.EntityProto.

    Yields:
      A operation.db.Put for the mapped entity.
    """
    self.initialize()
    protobuf = entity_pb.EntityProto(contents=record)
    if self.app_id:
      fix_keys(protobuf, self.app_id)
    entity = datastore.Entity.FromPb(protobuf)
    yield op.db.Put(entity)

class RestoreCompleteHandler(BaseHandler):
  """ Callback handler for MapReduce restore handler. """

  # The path to this handler.
  PATH = '/restorecomplete/'

  # The path to the callback handler.
  CALLBACK_PATH = '/restore_callback'

  def post(self):
    """ POST method for restore complete handler. """
    bucket = self.request.get("gs_bucket_name")
    mapreduce_id = self.request.get('mapreduce_id')
    result = self.request.get('result')

    logging.info("Restore complete for MR job '{0}' and bucket '{1}'.".format(
      mapreduce_id, bucket))

    # Callback to the server.
    url = "https://{0}{1}".format(constants.APPSCALE_LOCATION,
      self.CALLBACK_PATH)
    try:
      payload = json.dumps({"mapreduce_id": mapreduce_id, "bucket": bucket,
        "app_id": os.environ['APPLICATION_ID'][2:], "result": result})

      result = urlfetch.fetch(url=url,
        payload=payload,
        method=urlfetch.POST,
        headers={'Content-Type': 'application/json'},
        validate_certificate=False)
      status_code = result.status_code
    except urlfetch.DownloadError, download_error:
      logging.error("Unable to send '{0}' request to {1}".
        format(self.CALLBACK_PATH, url))
      logging.error("Error: {0}".format(download_error.message))
      self.response.set_status(constants.HTTP_ERROR)
      return

    if status_code != constants.HTTP_OK:
      logging.error("Error during restore callback to '{0}'. "
        "Error code: {1}".format(url, status_code))
      self.response.set_status(status_code)

APP = webapp2.WSGIApplication([
  (r'/restore/', Restore),
  (r'/restorecomplete/', RestoreCompleteHandler),
], debug=constants.DEBUG_MODE)

logging.getLogger().setLevel(logging.DEBUG)
