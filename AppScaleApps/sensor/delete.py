#!/usr/bin/env python

""" Deletes data and provides a REST interface. """

import json
import os
import sys
# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

from base_handler import BaseHandler
from backup import get_datastore_stats
from backup import get_shard_count
from common import constants
import settings
from utils import *

from mapreduce import control
from mapreduce import model
from mapreduce import operation

sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer"))
from google.appengine.api import memcache

# Job name prefix for testing writability.
TEST_WRITE_FILENAME_PREFIX = 'datastore_backup_write_test'

# MapReduce delete handlers.
DELETE_COMPLETE_HANDLER = __name__ +  '.DeleteCompleteHandler'
DELETE_HANDLER = __name__ + '.delete_entity'

# Input reader for MapReduce job.
INPUT_READER = ('mapreduce.input_readers.DatastoreKeyInputReader')

# Memcache key for caching kinds and sizes.
MEMCACHE_NAMESPACE = '_ah-datastore_admin'
KINDS_AND_SIZES_VAR = 'kinds_and_sizes'

# MapReduce objects used for the MR job.
MAPREDUCE_OBJECTS = [model.MapreduceState.kind(),
                     model.ShardState.kind()]


def cache_stats(formatted_results):
  """ Cache last retrieved kind size values in memcache.

  Args:
    formatted_results: list of dictionaries of the form returned by
      main._presentable_kind_stats.
  """
  kinds_and_sizes = dict((kind['kind_name'], kind['total_bytes'])
                         for kind in formatted_results)

  memcache.set(KINDS_AND_SIZES_VAR,
               kinds_and_sizes,
               namespace=MEMCACHE_NAMESPACE)

def delete_entity(key):
  """ Delete function which deletes all processed entities.

  Args:
    key: Key of the entity to delete.

  Yields:
    A delete operation if the entity is not an active mapreduce or
    DatastoreAdminOperation object.
  """
  if key.kind() in MAPREDUCE_OBJECTS:
    entity = datastore.Get(key)
    if entity and not entity["active"]:
      yield operation.db.Delete(key)
  else:
    yield operation.db.Delete(key)

def perform_delete(kinds,
  selected_namespace,
  gs_bucket_name,
  backup,
  queue,
  mapper_params):
  """ Triggers backup mapper jobs.

  Args:
    kinds: A sequence of kind names.
    selected_namespace: The selected namespace or None for all.
    gs_bucket_name: The GS file system bucket in which to store the backup
      when using the GS file system, and otherwise ignored.
    backup: A string, the backup name.
    queue: The task queue for the backup task.
    mapper_params: The mapper parameters.

  Returns:
    The job or task ids.

  Raises:
    DeleteValidationException: On validation error.
    Exception: On any other error.
  """
  logging.info("Kinds: {0}".format(kinds))
  queue = queue or os.environ.get('HTTP_X_APPENGINE_QUEUENAME', 'default')
  if queue[0] == '_':
    queue = 'default'

  job_name = 'appscale_datastore_delete_%s_%%(kind)s' % re.sub(r'[^\w]', '_',
    backup)
  try:
    mapreduce_params = {
        'done_callback_handler': DELETE_COMPLETE_HANDLER,
        'force_ops_writes': True,
    }
    mapper_params = dict(mapper_params)
    return [('job', job) for job in _run_map_jobs(
          kinds, job_name,
          DELETE_HANDLER, INPUT_READER, None,
          mapper_params, mapreduce_params, queue)]
  except Exception, exception:
    logging.exception('Failed to start a datastore backup job[s] for "%s".',
      backup)
    raise Exception(exception)

def _run_map_jobs(kinds,
  job_name,
  backup_handler,
  input_reader,
  output_writer,
  mapper_params,
  mapreduce_params,
  queue):
  """ Creates backup/restore MR jobs for the given operation.

  Args:
    kinds: A list of kinds to run the M/R for.
    job_name: The M/R job name prefix.
    backup_handler: M/R job completion handler.
    input_reader: M/R input reader.
    output_writer: M/R output writer.
    mapper_params: Custom parameters to pass to mapper.
    mapreduce_params: Dictionary parameters relevant to the whole job.
    queue: The name of the queue that will be used by the M/R.

  Returns:
    IDs of all started mapper jobs as list of strings.
  """
  jobs = run_map_for_kinds(
      kinds,
      job_name,
      backup_handler,
      input_reader,
      output_writer,
      mapper_params,
      mapreduce_params,
      queue_name=queue)
  return jobs

def start_map(job_name,
  handler_spec,
  reader_spec,
  writer_spec,
  mapper_params,
  mapreduce_params=None,
  start_transaction=True,
  queue_name=None,
  shard_count=MAPREDUCE_DEFAULT_SHARDS):
  """ Start map as part of datastore admin operation.

  Will increase number of active jobs inside the operation and start new map.

  Args:
    job_name: Map job name.
    handler_spec: Map handler specification.
    reader_spec: Input reader specification.
    writer_spec: Output writer specification.
    mapper_params: Custom mapper parameters.
    mapreduce_params: Custom mapreduce parameters.
    start_transaction: Specify if a new transaction should be started.
    queue_name: The name of the queue that will be used by the M/R.
    shard_count: The number of shards the M/R will try to use.

  Returns:
    Resulting map job ID as string.
  """
  if not mapreduce_params:
    mapreduce_params = {}
  mapreduce_params['done_callback'] = DELETE_COMPLETE_HANDLER.PATH
  if queue_name is not None:
    mapreduce_params['done_callback_queue'] = queue_name
  mapreduce_params['force_writes'] = 'True'
  job_id = control.start_map(
    job_name, handler_spec, reader_spec,
    mapper_params,
    output_writer_spec=writer_spec,
    mapreduce_parameters=mapreduce_params,
    shard_count=shard_count,
    queue_name=queue_name)
  return job_id

def run_map_for_kinds(kinds,
  job_name_template,
  handler_spec,
  reader_spec,
  writer_spec,
  mapper_params,
  mapreduce_params=None,
  queue_name=None,
  max_shard_count=None):
  """ Run mapper job for all entities in specified kinds.

  Args:
    kinds: List of entity kinds as strings.
    job_name_template: Ttemplate for naming individual mapper jobs. Can
      reference %(kind)s and %(namespace)s formatting variables.
    handler_spec: Mapper handler specification.
    reader_spec: Reader specification.
    writer_spec: Writer specification.
    mapper_params: Custom parameters to pass to mapper.
    mapreduce_params: Dictionary parameters relevant to the whole job.
    queue_name: The name of the queue that will be used by the M/R.
    max_shard_count: Maximum value for shards count.

  Returns:
    IDs of all started mapper jobs as list of strings.

  Raises:
    BaseException: On error.
  """
  jobs = []
  try:
    for kind in kinds:
      mapper_params['entity_kind'] = kind
      job_name = job_name_template % {'kind': kind, 'namespace':
                                      mapper_params.get('namespace', '')}
      shard_count = get_shard_count(kind, max_shard_count)
      jobs.append(start_map(job_name, handler_spec, reader_spec,
                           writer_spec, mapper_params, mapreduce_params,
                           queue_name=queue_name, shard_count=shard_count))
    return jobs

  except BaseException, ex:
    raise BaseException(ex)

def start_delete(kinds, bucket):
  """ Top level function to start a backup.
 
  Args:
    kinds: A list of kind names.
    bucket: A str, the bucket to delete data from.

  Returns:
    True if the was started, False otherwise.
  """
  perform_delete(kinds, None,
    bucket, "latest", "default", {'namespace': None})
  return True, ""

class Delete(BaseHandler):
  """ Handler for deleting entities. """

  def post(self):
    """ POST method for deleting entities. """
    remote_api_key = self.request.get(constants.ApiTags.API_KEY)
    if remote_api_key != settings.API_KEY:
      self.error_out("Request with bad API key")
      return

    gcs_bucket = self.request.get("bucket")
    if not gcs_bucket:
      self.error_out("No bucket specified")
      return

    last_stats_update, kind_stats = get_datastore_stats([],
      use_stats_kinds=True)
    old_kinds = [kind['kind_name'] for kind in kind_stats]
    kinds = []
    for kind in old_kinds:
      # TODO currently ignoring kinds with prefix "_".
      if not kind.startswith("_"):
        kinds.append(kind)
    logging.debug("Kinds: {0}".format(kinds))

    success, reason = start_delete(kinds, gcs_bucket)
    json_result = {"success": success, "reason": reason}
    self.response.write(json.dumps(json_result))

class DeleteCompleteHandler(BaseHandler):
  """ Callback handler for MapReduce delete handler. """

  PATH = '/deletecomplete/'

  def post(self):
    """ POST method for deletion complete handler. """
    logging.info("Deletion complete")


APP = webapp2.WSGIApplication([
  (r'/delete/', Delete),
  (r'/deletecomplete/', DeleteCompleteHandler),
], debug=constants.DEBUG_MODE)
