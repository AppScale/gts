#!/usr/bin/env python
"""
Backs up data and provides a REST interface for controlling and fetching data.
"""
import json
import logging
import os
import random
import re
import sys

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

from base_handler import BaseHandler
from common import constants
import settings
from utils import BackupValidationException
from utils import get_pretty_bytes
from utils import format_thousands
from utils import MAPREDUCE_DEFAULT_SHARDS
from utils import MAPREDUCE_MIN_SHARDS
from utils import MAPREDUCE_MAX_SHARDS
from utils import parse_gs_handle
from utils import start_map
from utils import validate_gs_bucket_name

from mapreduce import datastore_range_iterators as db_iters
from mapreduce import output_writers
from mapreduce import input_readers

sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer"))
from google.appengine.api import files
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext.db import stats
from google.appengine.runtime import apiproxy_errors

# A temporary file name prefix.
TEST_WRITE_FILENAME_PREFIX = 'datastore_backup_write_test'

# The max number of keys on a list when testing buckets.
MAX_KEYS_LIST_SIZE = 100

# The max number of tries when testing a bucket.
MAX_TEST_FILENAME_TRIES = 10

# Backup handler called when done.
BACKUP_COMPLETE_HANDLER = __name__ +  '.BackupCompleteHandler'

# The mapper handler of the backup job.
BACKUP_HANDLER = __name__ + '.BackupEntity.map'

# The input reader and output writer for the MapReduce job.
INPUT_READER = __name__ + '.DatastoreEntityProtoInputReader'
OUTPUT_WRITER = output_writers.__name__ + '.FileRecordsOutputWriter'

# The namespace used for caching kind stats.
MEMCACHE_NAMESPACE = '_ah-datastore_admin'

# The key for memcache to store kind/size information.
KINDS_AND_SIZES_VAR = 'kinds_and_sizes'

class DatastoreEntityProtoInputReader(input_readers.RawDatastoreInputReader):
  """ An input reader which yields datastore entity proto for a kind. """

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeEntityProtoIterator

def _PresentatableKindStats(kind_ent):
  """ Generate dict of presentable values for template. """
  count = kind_ent.count
  entity_bytes = kind_ent.entity_bytes
  total_bytes = kind_ent.bytes
  average_bytes = entity_bytes / count
  return {'kind_name': kind_ent.kind_name,
          'count': format_thousands(kind_ent.count),
          'entity_bytes_str': get_pretty_bytes(entity_bytes),
          'entity_bytes': entity_bytes,
          'total_bytes_str': get_pretty_bytes(total_bytes),
          'total_bytes': total_bytes,
          'average_bytes_str': get_pretty_bytes(average_bytes),
         }

def _kinds_list_to_tuple(kinds_list):
  """ Build default tuple when no datastore statistics are available. """
  return '', [{'kind_name': kind} for kind in sorted(kinds_list)]

def get_shard_count(kind, max_shard_count=None):
  """ Retrieves the number of shards a MapReduce job should use.

  Args:
    kind: The kind name.
    max_shard_count: The maximum number of shards.

  Returns:
    An int, the max shard count.
  """
  stat = stats.KindStat.all().filter('kind_name =', kind).get()
  if stat:
    shard_count = min(
      max(MAPREDUCE_MIN_SHARDS, stat.bytes // (32 * 1024 * 1024)),
      MAPREDUCE_MAX_SHARDS)
    if max_shard_count and max_shard_count < shard_count:
      shard_count = max_shard_count
    return shard_count

  return MAPREDUCE_DEFAULT_SHARDS

def run_map_for_kinds(
  kinds,
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
    job_name_template: Template for naming individual mapper jobs. Can
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
    BaseException if a job fails to start.
  """
  jobs = []
  try:
    for kind in kinds:
      logging.debug("Creating job for kind '{0}'".format(kind))
      mapper_params['entity_kind'] = kind
      job_name = job_name_template % \
        {'kind': kind, 'namespace': mapper_params.get('namespace', '')}
      shard_count = get_shard_count(kind, max_shard_count)
      jobs.append(start_map(
        job_name, handler_spec, reader_spec, writer_spec, mapper_params,
        BackupCompleteHandler.PATH, mapreduce_params,
        queue_name=queue_name, shard_count=shard_count))
    return jobs
  except BaseException:
    raise

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
  logging.debug("Jobs to run: {0}".format(jobs))
  return jobs

def verify_bucket_writable(bucket_name):
  """ Verify the application can write to the specified bucket.

  Args:
    bucket_name: The bucket to verify.

  Raises:
    BackupValidationException: If the bucket is not writable.
  """
  path = '/gs/%s' % bucket_name
  logging.debug("Verifying bucket '{0}' is writable (path: {1})".format(
    bucket_name, path))

  try:
    file_names = files.gs.listdir(path,
      {
        'prefix': TEST_WRITE_FILENAME_PREFIX,
        'max_keys': MAX_KEYS_LIST_SIZE
      })
  except (files.InvalidParameterError, files.PermissionDeniedError):
    raise BackupValidationException('Bucket "%s" not accessible' % bucket_name)
  except files.InvalidFileNameError:
    raise BackupValidationException('Bucket "%s" does not exist' % bucket_name)

  file_name = '%s/%s.tmp' % (path, TEST_WRITE_FILENAME_PREFIX)
  file_name_try = 0

  while True:
    if file_name_try >= MAX_TEST_FILENAME_TRIES:
      raise BackupValidationException('Bucket "%s" not accessible' %
        bucket_name)
    if file_name not in file_names:
      break
    gen = random.randint(0, 9999)
    file_name = '%s/%s_%s.tmp' % (path, TEST_WRITE_FILENAME_PREFIX, gen)
    file_name_try += 1

  try:
    test_file = files.open(files.gs.create(file_name), 'a', exclusive_lock=True)
    try:
      test_file.write('test')
    finally:
      test_file.close(finalize=True)
  except files.PermissionDeniedError:
    raise BackupValidationException('Bucket "%s" is not writable' % bucket_name)

  try:
    files.delete(file_name)
  except (files.InvalidArgumentError, files.InvalidFileNameError, IOError):
    logging.warn('Failed to delete test file %s', file_name)


def perform_backup(kinds, gcs_bucket, backup, queue, mapper_params):
  """ Triggers backup mapper jobs.

  Args:
    kinds: A sequence of kind names.
    gcs_bucket: The GS file system bucket in which to store the backup
      when using the GS file system, and otherwise ignored.
    backup: A string, the backup name.
    queue: The task queue for the backup task.
    mapper_params: The mapper parameters.

  Returns:
    The job or task IDs.

  Raises:
    BackupValidationException: On validation error.
    Exception: On any other error.
  """
  queue = queue or os.environ.get('HTTP_X_APPENGINE_QUEUENAME', 'default')
  if queue[0] == '_':
    queue = 'default'
  logging.debug("Using queue '{0}' for the backup task.".format(queue))

  bucket_name, path = parse_gs_handle(gcs_bucket, 'backup')
  gcs_bucket = ('%s/%s' % (bucket_name, path)).rstrip('/')
  validate_gs_bucket_name(bucket_name)
  verify_bucket_writable(bucket_name)

  job_name = 'appscale_datastore_backup_%s_%%(kind)s' % re.sub(r'[^\w]', '_',
    backup)
  try:
    mapreduce_params = {
      'done_callback_handler': BACKUP_COMPLETE_HANDLER,
      'force_ops_writes': True,
    }
    mapper_params = dict(mapper_params)
    mapper_params['filesystem'] = files.GS_FILESYSTEM
    mapper_params['gs_bucket_name'] = gcs_bucket
    logging.debug("Starting job '{0}' with mapper_params {1}".format(
      job_name, mapper_params))
    return [job for job in _run_map_jobs(
          kinds, job_name,
          BACKUP_HANDLER, INPUT_READER, OUTPUT_WRITER,
          mapper_params, mapreduce_params, queue)]
  except Exception, exception:
    logging.exception("Failed to start a datastore backup job[s] for "
      "{0}. Exception: {1}".format(backup, exception))
    raise Exception(exception)

def start_backup(kinds, gcs_bucket):
  """ Top level function to start a backup.

  Args:
    kinds: A list of kind names to back up.
    gcs_bucket: The GCS bucket to store the backup in.

  Returns:
    A list of job IDs for the backup process.
  """
  return perform_backup(kinds, gcs_bucket, "latest", "default",
    {'namespace': None})

def cache_stats(formatted_results):
  """ Cache last retrieved kind size values in memcache.

  Args:
    formatted_results: list of dictionaries of the form returnned by
      main._presentable_kind_stats.
  """
  kinds_and_sizes = dict((kind['kind_name'], kind['total_bytes'])
    for kind in formatted_results)

  memcache.set(KINDS_AND_SIZES_VAR, kinds_and_sizes,
    namespace=MEMCACHE_NAMESPACE)

def get_datastore_stats(kinds_list, use_stats_kinds=False):
  """ Retrieves stats for kinds.

  Args:
    kinds_list: List of known kinds.
    use_stats_kinds: If stats are available, kinds_list will be ignored and
      all kinds found in stats will be used instead.

  Returns:
    timestamp: Record's time that statistics were last updated.
    global_size: Total size of all known kinds.
    kind_dict: Dictionary of kind objects with the following members:
    - kind_name: The name of this kind.
    - count: Number of known entities of this type.
    - total_bytes_str: Total bytes for this kind as a string.
    - average_bytes_str: Average bytes per entity as a string.
  """
  global_stat = stats.GlobalStat.all().fetch(1)
  if not global_stat:
    return _kinds_list_to_tuple(kinds_list)

  global_ts = global_stat[0].timestamp

  kind_stats = stats.KindStat.all().filter('timestamp =', global_ts).fetch(1000)
  if not kind_stats:
    return _kinds_list_to_tuple(kinds_list)

  results = {}
  for kind_ent in kind_stats:
    if (not kind_ent.kind_name.startswith('__')
        and (use_stats_kinds or kind_ent.kind_name in kinds_list)
        and kind_ent.count > 0):
      results[kind_ent.kind_name] = _PresentatableKindStats(kind_ent)

  cache_stats(results.values())
  for kind_str in kinds_list or []:
    if kind_str not in results:
      results[kind_str] = {'kind_name': kind_str}

  return (global_ts, sorted(results.values(), key=lambda x: x['kind_name']))

class Backup(BaseHandler):
  """ The handler to start a backup process. """

  def post(self):
    """ A POST method to start a backup. """
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
      _, kind_stats = get_datastore_stats([],
        use_stats_kinds=True)
      all_kinds = [kind['kind_name'] for kind in kind_stats]
      kinds = []
      for kind in all_kinds:
        # TODO Do not include things with "_". Is this okay?
        # TODO Will we not backup all the user data?
        if not kind.startswith("_"):
          kinds.append(kind)
      logging.debug("Kinds to back up: {0}".format(kinds))
    except apiproxy_errors.OverQuotaError, overquota_error:
      logging.error("Quota exceeded while getting datastore stats. Error: "
        "{0}".format(overquota_error.message))
      json_result = {"success": False, "reason": "Quota limit exceeded."}
      self.response.write(json.dumps(json_result))
      return

    try:
      jobs = start_backup(kinds, gcs_bucket)
      json_result = {"success": True, "jobs": jobs}
    except Exception, exception:
      logging.exception("Exception while starting backup to bucket: "
        "{0}".format(gcs_bucket))
      logging.exception(exception.message)
      json_result = {"success": False}

    self.response.write(json.dumps(json_result))

class BackupEntity(object):
  """ A class which dumps the entity to the writer."""

  def map(self, entity_proto):
    """ Backup entity map handler.

    Args:
      entity_proto: An instance of entity_pb.EntityProto.

    Yields:
      A serialized entity_pb.EntityProto as a string.
    """
    yield entity_proto.SerializeToString()

class BackupCompleteHandler(BaseHandler):
  """ Callback handler for completed backups. """

  # The path to this handler.
  PATH = '/backupcomplete/'

  # The path to the callback handler.
  CALLBACK_PATH = '/backup_callback'

  def post(self):
    """ POST method for backup complete handler. """
    bucket = self.request.get("gs_bucket_name")
    mapreduce_id = self.request.get('mapreduce_id')
    result = self.request.get('result')

    logging.info("Backup complete for MR job '{0}' and bucket '{1}'.".format(
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
      logging.error("Error during backup callback to '{0}'. "
        "Error code: {1}".format(url, status_code))
      self.response.set_status(status_code)

APP = webapp2.WSGIApplication([
  (r'/backup/', Backup),
  (r'/backupcomplete/', BackupCompleteHandler),
], debug=constants.DEBUG_MODE)

logging.getLogger().setLevel(logging.DEBUG)
