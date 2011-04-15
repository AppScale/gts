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
import logging
import os
import random

from google.appengine.api import lib_config
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.db import metadata
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import control
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model

MEMCACHE_NAMESPACE = '_ah-datastore_admin'
XSRF_VALIDITY_TIME = 600
KINDS_AND_SIZES_VAR = 'kinds_and_sizes'


class ConfigDefaults(object):
  """Configurable constants.

  To override datastore_admin configuration values, define values like this
  in your appengine_config.py file (in the root of your app):

    datastore_admin_MAPREDUCE_PATH = /_ah/mapreduce
  """

  BASE_PATH = '/_ah/datastore_admin'
  MAPREDUCE_PATH = '/_ah/mapreduce'
  CLEANUP_MAPREDUCE_STATE = True



config = lib_config.register('datastore_admin', ConfigDefaults.__dict__)




config.BASE_PATH


from google.appengine.ext.webapp import template


def RenderToResponse(handler, template_file, template_params):
  """Render the given template_file using template_vals and write to response.

  Args:
    handler: the handler whose response we should render to
    template_file: the file name only of the template file we are using
    template_params: the parameters used to render the given template
  """
  template_params = _GetDefaultParams(template_params)
  rendered = template.render(_GetTemplatePath(template_file), template_params)
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
  """Update template_params to always contain necessary paths and never be None.
  """
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
      ''.join([chr(int(random.random()*255)) for _ in range(0, 64)]))

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

  token_str = token_obj[0]
  token_action = token_obj[1]

  if user_str != token_str or action != token_action:
    return False

  return True


def CacheStats(formatted_results):
  """Cache last retrieved kind size values in memcache.

  Args:
    formatted_results: list of dictionaries of the form returnned by
      main._PresentableKindStats.
  """
  kinds_and_sizes = {}
  for kind_dict in formatted_results:
    kinds_and_sizes[kind_dict['kind_name']] = kind_dict['total_bytes']

  memcache.set(KINDS_AND_SIZES_VAR,
               kinds_and_sizes,
               namespace=MEMCACHE_NAMESPACE)


def RetrieveCachedStats():
  """Retrieve cached kind sizes from last datastore stats call.

  Returns:
    Dictionary mapping kind names to total bytes.
  """
  kinds_and_sizes = memcache.get(KINDS_AND_SIZES_VAR,
                                 namespace=MEMCACHE_NAMESPACE)

  return kinds_and_sizes


def _MakeUserStr():
  """Make a user string to use to represent the user.  'noauth' by default."""
  user = users.get_current_user()
  if not user:
    user_str = 'noauth'
  else:
    user_str = user.nickname()

  return user_str


def GetPrettyBytes(bytes, significant_digits=0):
  """Get a pretty print view of the given number of bytes.

  This will give a string like 'X MBytes'.

  Args:
    bytes: the original number of bytes to pretty print.
    significant_digits: number of digits to display after the decimal point.

  Returns:
    A string that has the pretty print version of the given bytes.
  """
  byte_prefixes = ['', 'K', 'M', 'G', 'T', 'P', 'E']
  for i in range(0, 7):
    exp = i * 10
    if bytes < 2**(exp + 10):
      if i == 0:
        formatted_bytes = str(bytes)
      else:
        formatted_bytes = '%.*f' % (significant_digits, (bytes * 1.0 / 2**exp))
      if formatted_bytes != '1':
        plural = 's'
      else:
        plural = ''
      return '%s %sByte%s' % (formatted_bytes, byte_prefixes[i], plural)

  logging.error('Number too high to convert: %d', bytes)
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
  namespace_str = ''
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
  """Create datastore config for use during datastore admin operations."""
  return datastore_rpc.Configuration(force_writes=True)


class MapreduceDoneHandler(webapp.RequestHandler):
  """Handler to delete data associated with successful MapReduce jobs."""

  SUFFIX = 'mapreduce_done'

  def post(self):
    """Mapreduce done callback to delete job data if it was successful."""
    if 'Mapreduce-Id' in self.request.headers:
      mapreduce_id = self.request.headers['Mapreduce-Id']
      mapreduce_state = model.MapreduceState.get_by_job_id(mapreduce_id)

      keys = []
      job_success = True
      for shard_state in model.ShardState.find_by_mapreduce_id(mapreduce_id):
        keys.append(shard_state.key())
        if not shard_state.result_status == 'success':
          job_success = False

      db_config = _CreateDatastoreConfig()
      if job_success:
        operation = DatastoreAdminOperation.get(
            mapreduce_state.mapreduce_spec.params[
                DatastoreAdminOperation.PARAM_DATASTORE_ADMIN_OPERATION])
        def tx():
          operation.active_jobs -= 1
          operation.completed_jobs += 1
          if not operation.active_jobs:
            operation.status = DatastoreAdminOperation.STATUS_COMPLETED
          db.delete(DatastoreAdminOperationJob.all().ancestor(operation),
                    config=db_config)
          operation.put(config=db_config)
        db.run_in_transaction(tx)

        if config.CLEANUP_MAPREDUCE_STATE:

          keys.append(mapreduce_state.key())
          keys.append(model.MapreduceControl.get_key_by_job_id(mapreduce_id))
          db.delete(keys, config=db_config)
          logging.info('State for successful job %s was deleted.', mapreduce_id)
      else:
        logging.info('Job %s was not successful so no state was deleted.', (
            mapreduce_id))
    else:
      logging.error('Done callback called without Mapreduce Id.')


class DatastoreAdminOperation(db.Model):
  """An entity to keep progress and status of datastore admin operation."""
  STATUS_ACTIVE = "Active"
  STATUS_COMPLETED = "Completed"


  PARAM_DATASTORE_ADMIN_OPERATION = 'datastore_admin_operation'

  description = db.TextProperty()
  status = db.StringProperty()
  active_jobs = db.IntegerProperty(default=0)
  completed_jobs = db.IntegerProperty(default=0)

  @classmethod
  def kind(cls):
    return "_AE_DatastoreAdmin_Operation"


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
      status=DatastoreAdminOperation.STATUS_ACTIVE,
      id=db.allocate_ids(
          db.Key.from_path(DatastoreAdminOperation.kind(), 1), 1)[0])
  operation.put(config=_CreateDatastoreConfig())
  return operation


def StartMap(operation,
             job_name,
             handler_spec,
             reader_spec,
             mapper_params,
             mapreduce_params=None,
             start_transaction=True):
  """Start map as part of datastore admin operation.

  Will increase number of active jobs inside the operation and start new map.

  Args:
    operation: An instance of DatastoreAdminOperation for current operation.
    job_name: Map job name.
    handler_spec: Map handler specification.
    reader_spec: Input reader specification.
    mapper_params: Custom mapper parameters.
    mapreduce_params: Custom mapreduce parameters.
    start_transaction: Specify if a new transaction should be started.

  Returns:
    resulting map job id as string.
  """

  if not mapreduce_params:
    mapreduce_params = dict()
  mapreduce_params[DatastoreAdminOperation.PARAM_DATASTORE_ADMIN_OPERATION] = (
      str(operation.key()))
  mapreduce_params['done_callback'] = '%s/%s' % (
      config.BASE_PATH, MapreduceDoneHandler.SUFFIX)
  mapreduce_params['force_writes'] = 'True'

  def tx():
    operation.active_jobs += 1
    operation.put(config=_CreateDatastoreConfig())


    return control.start_map(
        job_name, handler_spec, reader_spec,
        mapper_params,
        mapreduce_parameters=mapreduce_params,
        base_path=config.MAPREDUCE_PATH,
        shard_count=32,
        transactional=True)
  if start_transaction:
    return db.run_in_transaction(tx)
  else:
    return tx()


def RunMapForKinds(operation,
                   kinds,
                   job_name_template,
                   handler_spec,
                   reader_spec,
                   mapper_params):
  """Run mapper job for all entities in specified kinds.

  Args:
    operation: instance of DatastoreAdminOperation to record all jobs.
    kinds: list of entity kinds as strings.
    job_name_template: template for naming individual mapper jobs. Can
      reference %(kind)s and %(namespace)s formatting variables.
    handler_spec: mapper handler specification.
    reader_spec: reader specification.
    mapper_params: custom parameters to pass to mapper.

  Returns:
    Ids of all started mapper jobs as list of strings.
  """
  jobs = []
  for kind in kinds:
    mapper_params['entity_kind'] = kind
    job_name = job_name_template % {'kind': kind, 'namespace': ''}
    jobs.append(StartMap(
        operation, job_name, handler_spec, reader_spec, mapper_params))
  return jobs
