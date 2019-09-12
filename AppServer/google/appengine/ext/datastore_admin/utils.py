#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Used render templates for datastore admin."""



import base64
import datetime
import json
import logging
import os
import random
import time

# AppScale: Use bundled mapreduce library.
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import control
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation as mr_operation
from google.appengine.ext.mapreduce import util

from google.appengine.api import app_identity
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.datastore import datastore_rpc
from google.appengine.datastore import entity_pb
from google.appengine.ext import db
import webapp2 as webapp
from google.appengine.ext.datastore_admin import config
from google.appengine.ext.db import metadata
from google.appengine.ext.db import stats
from google.appengine.ext.webapp import _template
from google.appengine.runtime import apiproxy_errors


MEMCACHE_NAMESPACE = '_ah-datastore_admin'
XSRF_VALIDITY_TIME = 600
KINDS_AND_SIZES_VAR = 'kinds_and_sizes'
MAPREDUCE_MIN_SHARDS = 8
MAPREDUCE_DEFAULT_SHARDS = 32
MAPREDUCE_MAX_SHARDS = 256
RESERVE_KEY_POOL_MAX_SIZE = 1000

DATASTORE_ADMIN_OPERATION_KIND = '_AE_DatastoreAdmin_Operation'
BACKUP_INFORMATION_KIND = '_AE_Backup_Information'
BACKUP_INFORMATION_FILES_KIND = '_AE_Backup_Information_Kind_Files'
BACKUP_INFORMATION_KIND_TYPE_INFO = '_AE_Backup_Information_Kind_Type_Info'
DATASTORE_ADMIN_KINDS = (DATASTORE_ADMIN_OPERATION_KIND,
                         BACKUP_INFORMATION_KIND,
                         BACKUP_INFORMATION_FILES_KIND,
                         BACKUP_INFORMATION_KIND_TYPE_INFO)


MAX_RPCS = 10


def IsKindNameVisible(kind_name):
  return not (kind_name.startswith('__') or
              kind_name in DATASTORE_ADMIN_KINDS or
              kind_name in model._MAP_REDUCE_KINDS)


def RenderToResponse(handler, template_file, template_params):
  """Render the given template_file using template_vals and write to response.

  Args:
    handler: the handler whose response we should render to
    template_file: the file name only of the template file we are using
    template_params: the parameters used to render the given template
  """
  template_params = _GetDefaultParams(template_params)








  handler.response.headers['X-FRAME-OPTIONS'] = ('ALLOW-FROM %s' %
                                                 config.ADMIN_CONSOLE_URL)
  template_params['admin_console_url'] = config.ADMIN_CONSOLE_URL

  rendered = _template.render(_GetTemplatePath(template_file), template_params)
  handler.response.out.write(rendered)


def _GetTemplatePath(template_file):
  """Return the expected path for the template to render.

  Args:
    template_file: simple file name of template to render.

  Returns:
    path of template to render.
  """
  return os.path.join(
      os.path.dirname(__file__), 'templates', template_file)


def _GetDefaultParams(template_params):
  """Update template_params to always contain necessary paths and never None."""
  if not template_params:
    template_params = {}
  template_params.update({
      'base_path': config.BASE_PATH,
      'mapreduce_path': config.MAPREDUCE_PATH,
  })
  return template_params


def CreateXsrfToken(action):
  """Generate a token to be passed with a form for XSRF protection.

  Args:
    action: action to restrict token to

  Returns:
    suitably random token which is only valid for ten minutes and, if the user
    is authenticated, is only valid for the user that generated it.
  """
  user_str = _MakeUserStr()

  token = base64.b64encode(
      ''.join(chr(int(random.random()*255)) for _ in range(0, 64)))

  memcache.set(token,
               (user_str, action),
               time=XSRF_VALIDITY_TIME,
               namespace=MEMCACHE_NAMESPACE)

  return token


def ValidateXsrfToken(token, action):
  """Validate a given XSRF token by retrieving it from memcache.

  If the token has not been evicted from memcache (past ten minutes) and the
  user strings are equal, then this is a valid token.

  Args:
    token: token to validate from memcache.
    action: action that token should correspond to

  Returns:
    True if the token exists in memcache and the user strings are equal,
    False otherwise.
  """
  user_str = _MakeUserStr()
  token_obj = memcache.get(token, namespace=MEMCACHE_NAMESPACE)

  if not token_obj:
    return False

  token_str, token_action = token_obj
  if user_str != token_str or action != token_action:
    return False

  return True


def CacheStats(formatted_results):
  """Cache last retrieved kind size values in memcache.

  Args:
    formatted_results: list of dictionaries of the form returnned by
      main._PresentableKindStats.
  """
  kinds_and_sizes = dict((kind['kind_name'], kind['total_bytes'])
                         for kind in formatted_results)

  memcache.set(KINDS_AND_SIZES_VAR,
               kinds_and_sizes,
               namespace=MEMCACHE_NAMESPACE)


def RetrieveCachedStats():
  """Retrieve cached kind sizes from last datastore stats call.

  Returns:
    Dictionary mapping kind names to total bytes.
  """
  return memcache.get(KINDS_AND_SIZES_VAR, namespace=MEMCACHE_NAMESPACE)


def _MakeUserStr():
  """Make a user string to use to represent the user.  'noauth' by default."""
  user = users.get_current_user()
  return user.nickname() if user else 'noauth'


def GetPrettyBytes(bytes_num, significant_digits=0):
  """Get a pretty print view of the given number of bytes.

  This will give a string like 'X MBytes'.

  Args:
    bytes_num: the original number of bytes to pretty print.
    significant_digits: number of digits to display after the decimal point.

  Returns:
    A string that has the pretty print version of the given bytes.
    If bytes_num is to big the string 'Alot' will be returned.
  """
  byte_prefixes = ['', 'K', 'M', 'G', 'T', 'P', 'E']
  for i in range(0, 7):
    exp = i * 10
    if bytes_num < 1<<(exp + 10):
      if i == 0:
        formatted_bytes = str(bytes_num)
      else:
        formatted_bytes = '%.*f' % (significant_digits,
                                    (bytes_num * 1.0 / (1<<exp)))
      if formatted_bytes != '1':
        plural = 's'
      else:
        plural = ''
      return '%s %sByte%s' % (formatted_bytes, byte_prefixes[i], plural)

  logging.error('Number too high to convert: %d', bytes_num)
  return 'Alot'


def FormatThousands(value):
  """Format a numerical value, inserting commas as thousands separators.

  Args:
    value: An integer, float, or string representation thereof.
      If the argument is a float, it is converted to a string using '%.2f'.

  Returns:
    A string with groups of 3 digits before the decimal point (if any)
    separated by commas.

  NOTE: We don't deal with whitespace, and we don't insert
  commas into long strings of digits after the decimal point.
  """
  if isinstance(value, float):
    value = '%.2f' % value
  else:
    value = str(value)
  if '.' in value:
    head, tail = value.split('.', 1)
    tail = '.' + tail
  elif 'e' in value:
    head, tail = value.split('e', 1)
    tail = 'e' + tail
  else:
    head = value
    tail = ''
  sign = ''
  if head.startswith('-'):
    sign = '-'
    head = head[1:]
  while len(head) > 3:
    tail = ',' + head[-3:] + tail
    head = head[:-3]
  return sign + head + tail


def TruncDelta(delta):
  """Strips microseconds from a timedelta."""
  return datetime.timedelta(days=delta.days, seconds=delta.seconds)


def GetPrintableStrs(namespace, kinds):
  """Returns tuples describing affected kinds and namespace.

  Args:
    namespace: namespace being targeted.
    kinds: list of kinds being targeted.

  Returns:
    (namespace_str, kind_str) tuple used for display to user.
  """
  namespace_str = namespace or ''
  if kinds:
    kind_str = 'all %s entities' % ', '.join(kinds)
  else:
    kind_str = ''
  return (namespace_str, kind_str)


def ParseKindsAndSizes(kinds):
  """Parses kind|size list and returns template parameters.

  Args:
    kinds: list of kinds to process.

  Returns:
    sizes_known: whether or not all kind objects have known sizes.
    size_total: total size of objects with known sizes.
    len(kinds) - 2: for template rendering of greater than 3 kinds.
  """
  sizes_known = True
  size_total = 0
  kinds_and_sizes = RetrieveCachedStats()

  if kinds_and_sizes:
    for kind in kinds:
      if kind in kinds_and_sizes:
        size_total += kinds_and_sizes[kind]
      else:
        sizes_known = False
  else:
    sizes_known = False

  if size_total:
    size_total = GetPrettyBytes(size_total)

  return sizes_known, size_total, len(kinds) - 2


def _CreateDatastoreConfig():
  """Create datastore config for use during datastore operations."""
  return datastore_rpc.Configuration(force_writes=True, deadline=60)


def GenerateHomeUrl(unused_request):
  """Generates a link to the Datastore Admin main page.

  Primarily intended to be used for cancel buttons or links on error pages. To
  avoid any XSS security vulnerabilities the URL should not use any
  user-defined strings (unless proper precautions are taken).

  Args:
    unused_request: the webapp.Request object (to determine if certain query
      parameters need to be used).

  Returns:
    domain-relative URL for the main Datastore Admin page.
  """
  return config.BASE_PATH


class MapreduceDoneHandler(webapp.RequestHandler):
  """Handler to delete data associated with successful MapReduce jobs."""

  SUFFIX = 'mapreduce_done'

  def post(self):
    """Mapreduce done callback to delete job data if it was successful."""
    if 'Mapreduce-Id' in self.request.headers:
      mapreduce_id = self.request.headers['Mapreduce-Id']
      mapreduce_state = model.MapreduceState.get_by_job_id(mapreduce_id)
      if not mapreduce_state:
        logging.error('Done callback for no longer valid Mapreduce Id: %s',
                      mapreduce_id)
        return

      mapreduce_params = mapreduce_state.mapreduce_spec.params

      db_config = _CreateDatastoreConfig()
      if mapreduce_state.result_status == model.MapreduceState.RESULT_SUCCESS:
        operation_key = mapreduce_params.get(
            DatastoreAdminOperation.PARAM_DATASTORE_ADMIN_OPERATION)
        if operation_key is None:
          logging.error('Done callback for job %s without operation key.',
                        mapreduce_id)
        else:

          def tx():
            operation = DatastoreAdminOperation.get(operation_key)
            if mapreduce_id in operation.active_job_ids:
              operation.active_jobs -= 1
              operation.completed_jobs += 1
              operation.active_job_ids.remove(mapreduce_id)
            if not operation.active_jobs:
              if operation.status == DatastoreAdminOperation.STATUS_ACTIVE:
                operation.status = DatastoreAdminOperation.STATUS_COMPLETED
              db.delete(DatastoreAdminOperationJob.all().ancestor(operation),
                        config=db_config)
            operation.put(config=db_config)
            if 'done_callback_handler' in mapreduce_params:
              done_callback_handler = util.for_name(
                  mapreduce_params['done_callback_handler'])
              if done_callback_handler:
                done_callback_handler(operation, mapreduce_id, mapreduce_state)
              else:
                logging.error('done_callbackup_handler %s was not found',
                              mapreduce_params['done_callback_handler'])
          db.run_in_transaction(tx)
        if config.CLEANUP_MAPREDUCE_STATE:
          keys = []
          keys = model.ShardState.calculate_keys_by_mapreduce_state(
              mapreduce_state)

          keys.append(model.MapreduceControl.get_key_by_job_id(mapreduce_id))
          db.delete(keys, config=db_config)
          db.delete(mapreduce_state, config=db_config)
          logging.info('State for successful job %s was deleted.', mapreduce_id)
      else:
        logging.info('Job %s was not successful so no state was deleted.',
                     mapreduce_id)
    else:
      logging.error('Done callback called without Mapreduce Id.')


class Error(Exception):
  """Base DatastoreAdmin error type."""



class DatastoreAdminOperation(db.Model):
  """An entity to keep progress and status of datastore admin operation."""
  STATUS_CREATED = 'Created'
  STATUS_ACTIVE = 'Active'
  STATUS_COMPLETED = 'Completed'
  STATUS_FAILED = 'Failed'
  STATUS_ABORTED = 'Aborted'


  PARAM_DATASTORE_ADMIN_OPERATION = 'datastore_admin_operation'
  DEFAULT_LAST_UPDATED_VALUE = datetime.datetime(1970, 1, 1)

  description = db.TextProperty()
  status = db.StringProperty(default=STATUS_CREATED)
  active_jobs = db.IntegerProperty(default=0)
  active_job_ids = db.StringListProperty()
  completed_jobs = db.IntegerProperty(default=0)
  last_updated = db.DateTimeProperty(default=DEFAULT_LAST_UPDATED_VALUE,
                                     auto_now=True)
  status_info = db.StringProperty(default='', indexed=False)
  service_job_id = db.StringProperty()

  @classmethod
  def kind(cls):
    return DATASTORE_ADMIN_OPERATION_KIND


class DatastoreAdminOperationJob(db.Model):
  """An entity to keep track of started jobs to ensure idempotency.

  This entity can be used during spawning additional jobs. It is
  always stored as a child entity of DatastoreAdminOperation.
  Entity key name is job unique id.
  """
  pass


def StartOperation(description):
  """Start datastore admin operation.

  Args:
    description: operation description to be displayed to user.

  Returns:
    an instance of DatastoreAdminOperation.
  """



  operation = DatastoreAdminOperation(
      description=description,
      id=db.allocate_ids(
          db.Key.from_path(DatastoreAdminOperation.kind(), 1), 1)[0])
  operation.put(config=_CreateDatastoreConfig())
  return operation


@db.non_transactional(allow_existing=False)
def StartMap(operation_key,
             job_name,
             handler_spec,
             reader_spec,
             writer_spec,
             mapper_params,
             mapreduce_params=None,
             queue_name=None,
             shard_count=MAPREDUCE_DEFAULT_SHARDS):
  """Start map as part of datastore admin operation.

  Will increase number of active jobs inside the operation and start new map.

  Args:
    operation_key: Key of the DatastoreAdminOperation for current operation.
    job_name: Map job name.
    handler_spec: Map handler specification.
    reader_spec: Input reader specification.
    writer_spec: Output writer specification.
    mapper_params: Custom mapper parameters.
    mapreduce_params: Custom mapreduce parameters.
    queue_name: the name of the queue that will be used by the M/R.
    shard_count: the number of shards the M/R will try to use.

  Returns:
    resulting map job id as string.
  """

  if not mapreduce_params:
    mapreduce_params = {}
  mapreduce_params[DatastoreAdminOperation.PARAM_DATASTORE_ADMIN_OPERATION] = (
      str(operation_key))
  mapreduce_params['done_callback'] = '%s/%s' % (config.BASE_PATH,
                                                 MapreduceDoneHandler.SUFFIX)
  if queue_name is not None:
    mapreduce_params['done_callback_queue'] = queue_name
  mapreduce_params['force_writes'] = 'True'

  @db.transactional(xg=True)
  def tx():
    """Start MapReduce job and update datastore admin state.

    Returns:
      result MapReduce job id as a string.
    """
    job_id = control.start_map(
        job_name, handler_spec, reader_spec,
        mapper_params,
        output_writer_spec=writer_spec,
        mapreduce_parameters=mapreduce_params,
        base_path=config.MAPREDUCE_PATH,
        shard_count=shard_count,
        in_xg_transaction=True,
        queue_name=queue_name)
    operation = DatastoreAdminOperation.get(operation_key)
    operation.status = DatastoreAdminOperation.STATUS_ACTIVE
    operation.active_jobs += 1
    operation.active_job_ids = list(set(operation.active_job_ids + [job_id]))
    operation.put(config=_CreateDatastoreConfig())
    return job_id

  return tx()


def RunMapForKinds(operation_key,
                   kinds,
                   job_name_template,
                   handler_spec,
                   reader_spec,
                   writer_spec,
                   mapper_params,
                   mapreduce_params=None,
                   queue_name=None,
                   max_shard_count=None):
  """Run mapper job for all entities in specified kinds.

  Args:
    operation_key: The key of the DatastoreAdminOperation to record all jobs.
    kinds: list of entity kinds as strings.
    job_name_template: template for naming individual mapper jobs. Can
      reference %(kind)s and %(namespace)s formatting variables.
    handler_spec: mapper handler specification.
    reader_spec: reader specification.
    writer_spec: writer specification.
    mapper_params: custom parameters to pass to mapper.
    mapreduce_params: dictionary parameters relevant to the whole job.
    queue_name: the name of the queue that will be used by the M/R.
    max_shard_count: maximum value for shards count.

  Returns:
    Ids of all started mapper jobs as list of strings.
  """
  jobs = []
  try:
    for kind in kinds:
      mapper_params['entity_kind'] = kind
      job_name = job_name_template % {'kind': kind, 'namespace':
                                      mapper_params.get('namespace', '')}
      shard_count = GetShardCount(kind, max_shard_count)
      jobs.append(StartMap(operation_key, job_name, handler_spec, reader_spec,
                           writer_spec, mapper_params, mapreduce_params,
                           queue_name=queue_name, shard_count=shard_count))
    return jobs

  except BaseException, ex:
    AbortAdminOperation(operation_key,
                        _status=DatastoreAdminOperation.STATUS_FAILED,
                        _status_info='%s: %s' % (ex.__class__.__name__, ex))
    raise


def GetShardCount(kind, max_shard_count=None):
  stat = stats.KindStat.all().filter('kind_name =', kind).get()
  if stat:

    shard_count = min(max(MAPREDUCE_MIN_SHARDS,
                          stat.bytes // (32 * 1024 * 1024)),
                      MAPREDUCE_MAX_SHARDS)
    if max_shard_count and max_shard_count < shard_count:
      shard_count = max_shard_count
    return shard_count

  return MAPREDUCE_DEFAULT_SHARDS


def AbortAdminOperation(operation_key,
                        _status=DatastoreAdminOperation.STATUS_ABORTED,
                        _status_info=''):
  """Aborts active jobs."""
  operation = DatastoreAdminOperation.get(operation_key)
  operation.status = _status
  operation.status_info = _status_info
  operation.put(config=_CreateDatastoreConfig())
  for job in operation.active_job_ids:
    logging.info('Aborting Job %s', job)
    model.MapreduceControl.abort(job, config=_CreateDatastoreConfig())


def get_kind_from_entity_pb(entity):
  element_list = entity.key().path().element_list()
  return element_list[-1].type() if element_list else None


def FixKeys(entity_proto, app_id):
  """Go over keys in the given entity and update the application id.

  Args:
    entity_proto: An EntityProto to be fixed up. All identifiable keys in the
      proto will have the 'app' field reset to match app_id.
    app_id: The desired application id, typically os.getenv('APPLICATION_ID').
  """

  def FixKey(mutable_key):
    mutable_key.set_app(app_id)

  def FixPropertyList(property_list):
    for prop in property_list:
      prop_value = prop.mutable_value()
      if prop_value.has_referencevalue():
        FixKey(prop_value.mutable_referencevalue())
      elif prop.meaning() == entity_pb.Property.ENTITY_PROTO:
        embedded_entity_proto = entity_pb.EntityProto()
        try:
          embedded_entity_proto.ParsePartialFromString(prop_value.stringvalue())
        except Exception:
          logging.exception('Failed to fix-keys for property %s of %s',
                            prop.name(),
                            entity_proto.key())
        else:
          FixKeys(embedded_entity_proto, app_id)
          prop_value.set_stringvalue(
              embedded_entity_proto.SerializePartialToString())


  if entity_proto.has_key() and entity_proto.key().path().element_size():
    FixKey(entity_proto.mutable_key())

  FixPropertyList(entity_proto.property_list())
  FixPropertyList(entity_proto.raw_property_list())


class ReserveKeyPool(object):
  """Mapper pool which buffers keys with ids to reserve.

  Runs AllocateIds rpc(s) when flushed.
  """

  def __init__(self):
    self.keys = []

  def reserve_key(self, key):
    for id_or_name in key.to_path()[1::2]:
      if isinstance(id_or_name, (int, long)):
        self.keys.append(key)
        if len(self.keys) >= RESERVE_KEY_POOL_MAX_SIZE:
          self.flush()
        return

  def flush(self):
    if self.keys:

      datastore._GetConnection()._reserve_keys(self.keys)
      self.keys = []


class ReserveKey(mr_operation.Operation):
  """Mapper operation to reserve key ids."""

  def __init__(self, key):
    self.key = key
    self.app_id = key.app()
    self.pool_id = 'reserve_key_%s_pool' % self.app_id

  def __call__(self, ctx):
    pool = ctx.get_pool(self.pool_id)
    if not pool:
      pool = ReserveKeyPool()
      ctx.register_pool(self.pool_id, pool)
    pool.reserve_key(self.key)


class PutPool(context.Pool):
  """A trimmed copy of the MutationPool class.

  Properties:
    puts: a list of entities to put to datastore.
    max_entity_count: maximum number of entities before flushing it to db.
  """
  POOL_NAME = 'put_pool'

  def __init__(self, max_entity_count=context.MAX_ENTITY_COUNT):
    """Constructor.

    Args:
      max_entity_count: maximum number of entities before flushing it to db.
    """
    self.max_entity_count = max_entity_count
    self.puts = []

  def Put(self, entity):
    """Registers entity to put to datastore.

    Args:
      entity: The EntityProto for the entity to be put.
    """
    if len(self.puts) >= self.max_entity_count:
      self.flush()
    self.puts.append(entity)

  def flush(self):
    """Flush all puts to datastore."""
    if self.puts:
      datastore_rpc.Connection(config=_CreateDatastoreConfig()).put(self.puts)
    self.puts = []


class Put(mr_operation.Operation):
  """Mapper operation to batch puts."""

  def __init__(self, entity):
    """Constructor.

    Args:
      entity: The EntityProto of the entity to put.
    """
    self.entity = entity

  def __call__(self, ctx):
    pool = ctx.get_pool(PutPool.POOL_NAME)
    if not pool:
      pool = PutPool(
          max_entity_count=(context.MAX_ENTITY_COUNT/(2**ctx.task_retry_count)))
      ctx.register_pool(PutPool.POOL_NAME, pool)
    pool.Put(self.entity)


def GetKinds(all_ns=True, deadline=40):
  """Obtain a list of all kind names from the datastore.

  Args:
    all_ns: If true, list kind names for all namespaces.
            If false, list kind names only for the current namespace.
    deadline: maximum number of seconds to spend getting kinds.

  Returns:
    kinds: an alphabetized list of kinds for the specified namespace(s).
    more_kinds: a boolean indicating whether there may be additional kinds
        not included in 'kinds' (e.g. because the query deadline was reached).
  """
  if all_ns:
    kinds, more_kinds = GetKindsForAllNamespaces(deadline)
  else:
    kinds, more_kinds = GetKindsForCurrentNamespace(deadline)
  return kinds, more_kinds


def GetKindsForAllNamespaces(deadline):
  """Obtain a list of all kind names from the datastore.

  Pulls kinds from all namespaces. The result is deduped and alphabetized.

  Args:
    deadline: maximum number of seconds to spend getting kinds.

  Returns:
    kinds: an alphabetized list of kinds for the specified namespace(s).
    more_kinds: a boolean indicating whether there may be additional kinds
        not included in 'kinds' (e.g. because the query deadline was reached).
  """
  start = time.time()
  kind_name_set = set()

  def ReadFromKindIters(kind_iter_list):
    """Read kinds from a list of iterators.

    Reads a kind from each iterator in kind_iter_list, adds it to
    kind_name_set, and removes any completed iterators.

    Args:
      kind_iter_list: a list of iterators of kinds.
    """
    completed = []
    for kind_iter in kind_iter_list:
      try:
        kind_name = kind_iter.next().kind_name
        if IsKindNameVisible(kind_name):
          kind_name_set.add(kind_name)
      except StopIteration:
        completed.append(kind_iter)
    for kind_iter in completed:
      kind_iter_list.remove(kind_iter)

  more_kinds = False
  try:
    namespace_iter = metadata.Namespace.all().run(batch_size=1000,
                                                  deadline=deadline)
    kind_iter_list = []
    for ns in namespace_iter:


      remaining = deadline - (time.time() - start)

      if remaining <= 0:
        raise datastore_errors.Timeout
      kind_iter_list.append(metadata.Kind.all(namespace=ns.namespace_name)
                            .run(batch_size=1000, deadline=remaining))
      while len(kind_iter_list) == MAX_RPCS:
        ReadFromKindIters(kind_iter_list)
    while kind_iter_list:
      ReadFromKindIters(kind_iter_list)
  except (datastore_errors.Timeout, apiproxy_errors.DeadlineExceededError):
    more_kinds = True
    logging.warning('Failed to retrieve all kinds within deadline.')
  return sorted(kind_name_set), more_kinds


def GetKindsForCurrentNamespace(deadline):
  """Obtain a list of all kind names from the datastore.

  Pulls kinds from the current namespace only. The result is alphabetized.

  Args:
    deadline: maximum number of seconds to spend getting kinds.

  Returns:
    kinds: an alphabetized list of kinds for the specified namespace(s).
    more_kinds: a boolean indicating whether there may be additional kinds
        not included in 'kinds' (e.g. because the query limit was reached).
  """
  more_kinds = False
  kind_names = []
  try:
    kinds = metadata.Kind.all().order('__key__').run(batch_size=1000,
                                                     deadline=deadline)
    for kind in kinds:
      kind_name = kind.kind_name
      if IsKindNameVisible(kind_name):
        kind_names.append(kind_name)
  except (datastore_errors.Timeout, apiproxy_errors.DeadlineExceededError):
    more_kinds = True
    logging.warning('Failed to retrieve all kinds within deadline.')
  return kind_names, more_kinds


def get_service_account_names():
  """ AppScale: Fetch list of service accounts from IAM API. """
  project_id = app_identity.get_application_id()
  iam_location = 'https://127.0.0.1:17441'
  url = iam_location + '/v1/projects/{}/serviceAccounts'.format(project_id)
  token = app_identity.get_access_token(
      ['https://www.googleapis.com/auth/cloud-platform'])[0]
  headers = {'Authorization': 'Bearer {}'.format(token)}
  response = urlfetch.fetch(url, headers=headers, validate_certificate=False)
  try:
    accounts = json.loads(response.content)['accounts']
  except (KeyError, ValueError):
    raise ValueError('Invalid list of service accounts: '
                     '{}'.format(response.content))

  return tuple(account['email'] for account in accounts)
