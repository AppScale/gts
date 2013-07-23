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





"""Handler for data backup operation.

Generic datastore admin console transfers control to ConfirmBackupHandler
after selection of entities. The ConfirmBackupHandler confirms with user
his choice, enters a backup name and transfers control to
DoBackupHandler. DoBackupHandler starts backup mappers and displays confirmation
page.

This module also contains actual mapper code for backing data over.
"""

from __future__ import with_statement



import cStringIO
import datetime
import itertools
import logging
import os
import random
import re
import time
import urllib
import xml.dom.minidom


from google.appengine.datastore import entity_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import app_identity
from google.appengine.api import blobstore as blobstore_api
from google.appengine.api import capabilities
from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import files
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch
from google.appengine.api.files import records
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import datastore_query
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import backup_pb2
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import datastore_range_iterators as db_iters
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation as op
from google.appengine.ext.mapreduce import output_writers
from google.appengine.runtime import apiproxy_errors


XSRF_ACTION = 'backup'
BUCKET_PATTERN = (r'^([a-zA-Z0-9]+([\-_]+[a-zA-Z0-9]+)*)'
                  r'(\.([a-zA-Z0-9]+([\-_]+[a-zA-Z0-9]+)*))*$')
MAX_BUCKET_LEN = 222
MIN_BUCKET_LEN = 3
MAX_BUCKET_SEGMENT_LEN = 63
NUM_KINDS_DEFERRED_THRESHOLD = 10
MAX_BLOBS_PER_DELETE = 500
TEST_WRITE_FILENAME_PREFIX = 'datastore_backup_write_test'
MAX_KEYS_LIST_SIZE = 100
MAX_TEST_FILENAME_TRIES = 10

MEANING_TO_PRIMITIVE_TYPE = {
    entity_pb.Property.GD_WHEN: backup_pb2.EntitySchema.DATE_TIME,
    entity_pb.Property.GD_RATING: backup_pb2.EntitySchema.RATING,
    entity_pb.Property.ATOM_LINK: backup_pb2.EntitySchema.LINK,
    entity_pb.Property.ATOM_CATEGORY: backup_pb2.EntitySchema.CATEGORY,
    entity_pb.Property.GD_PHONENUMBER: backup_pb2.EntitySchema.PHONE_NUMBER,
    entity_pb.Property.GD_POSTALADDRESS: backup_pb2.EntitySchema.POSTAL_ADDRESS,
    entity_pb.Property.GD_EMAIL: backup_pb2.EntitySchema.EMAIL,
    entity_pb.Property.GD_IM: backup_pb2.EntitySchema.IM_HANDLE,
    entity_pb.Property.BLOBKEY: backup_pb2.EntitySchema.BLOB_KEY,
    entity_pb.Property.TEXT: backup_pb2.EntitySchema.TEXT,
    entity_pb.Property.BLOB: backup_pb2.EntitySchema.BLOB,
    entity_pb.Property.BYTESTRING: backup_pb2.EntitySchema.SHORT_BLOB
}


class ConfirmBackupHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'confirm_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    kinds = handler.request.get_all('kind')
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    blob_warning = bool(blobstore.BlobInfo.all().count(1))
    template_params = {
        'form_target': DoBackupHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'queues': None,
        'cancel_url': handler.request.get('cancel_url'),
        'namespaces': get_namespaces(handler.request.get('namespace', None)),
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning,
        'blob_warning': blob_warning,
        'backup_name': 'datastore_backup_%s' % time.strftime('%Y_%m_%d')
    }
    utils.RenderToResponse(handler, 'confirm_backup.html', template_params)


def get_namespaces(selected_namespace):
  namespaces = [('--All--', '*', selected_namespace is None)]
  for ns in datastore.Query('__namespace__', keys_only=True).Run():
    ns_name = ns.name() or ''
    namespaces.append((ns_name or '--Default--',
                       ns_name,
                       ns_name == selected_namespace))
  return namespaces


class ConfirmDeleteBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to delete a backup copy."""

  SUFFIX = 'confirm_delete_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    requested_backup_ids = handler.request.get_all('backup_id')
    backups = []
    gs_warning = False
    if requested_backup_ids:
      for backup in db.get(requested_backup_ids):
        if backup:
          backups.append(backup)
          gs_warning |= backup.filesystem == files.GS_FILESYSTEM
    template_params = {
        'form_target': DoBackupDeleteHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'backups': backups,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'gs_warning': gs_warning
    }
    utils.RenderToResponse(handler, 'confirm_delete_backup.html',
                           template_params)


class ConfirmAbortBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to abort a backup copy."""

  SUFFIX = 'confirm_abort_backup'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    requested_backup_ids = handler.request.get_all('backup_id')
    backups = []
    if requested_backup_ids:
      for backup in db.get(requested_backup_ids):
        if backup:
          backups.append(backup)
    template_params = {
        'form_target': DoBackupAbortHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'backups': backups,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION)
    }
    utils.RenderToResponse(handler, 'confirm_abort_backup.html',
                           template_params)


class ConfirmRestoreFromBackupHandler(webapp.RequestHandler):
  """Handler to confirm admin console requests to restore from backup."""

  SUFFIX = 'confirm_restore_from_backup'

  @classmethod
  def Render(cls, handler, default_backup_id=None,
             default_delete_backup_after_restore=False):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
      default_backup_id: default value for handler.request
      default_delete_backup_after_restore: default value for handler.request
    """
    backup_id = handler.request.get('backup_id', default_backup_id)
    backup = db.get(backup_id) if backup_id else None
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    original_app_warning = backup.original_app
    if os.getenv('APPLICATION_ID') == original_app_warning:
      original_app_warning = None
    template_params = {
        'form_target': DoBackupRestoreHandler.SUFFIX,
        'queues': None,
        'cancel_url': handler.request.get('cancel_url'),
        'backup': backup,
        'delete_backup_after_restore': handler.request.get(
            'delete_backup_after_restore', default_delete_backup_after_restore),
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning,
        'original_app_warning': original_app_warning
    }
    utils.RenderToResponse(handler, 'confirm_restore_from_backup.html',
                           template_params)


class ConfirmBackupImportHandler(webapp.RequestHandler):
  """Handler to import backup information."""

  SUFFIX = 'backup_information'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    gs_handle = handler.request.get('gs_handle')
    error = None if gs_handle else 'Google Cloud Storage path is missing'
    other_backup_info_files = []
    selected_backup_info_file = None
    backup_info_specified = False
    if not error:
      try:
        gs_handle = gs_handle.rstrip()
        bucket_name, prefix = parse_gs_handle(gs_handle)
        validate_gs_bucket_name(bucket_name)
        if not is_accessible_bucket_name(bucket_name):
          raise BackupValidationException(
              'Bucket "%s" is not accessible' % bucket_name)
        if prefix.endswith('.backup_info'):
          prefix = prefix[0:prefix.rfind('/')]
          backup_info_specified = True
        elif prefix and not prefix.endswith('/'):
          prefix += '/'
        for backup_info_file in list_bucket_files(bucket_name, prefix):
          backup_info_path = '/gs/%s/%s' % (bucket_name, backup_info_file)
          if backup_info_specified and backup_info_path == gs_handle:
            selected_backup_info_file = backup_info_path
          elif (backup_info_file.endswith('.backup_info')
                and backup_info_file.count('.') == 1):
            other_backup_info_files.append(backup_info_path)
      except Exception, ex:
        error = 'Failed to read bucket: %s' % ex
    template_params = {
        'error': error,
        'form_target': DoBackupImportHandler.SUFFIX,
        'cancel_url': handler.request.get('cancel_url'),
        'selected_backup_info_file': selected_backup_info_file,
        'other_backup_info_files': other_backup_info_files,
        'backup_info_specified': backup_info_specified,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION)
    }
    utils.RenderToResponse(handler, 'confirm_backup_import.html',
                           template_params)


class BackupInformationHandler(webapp.RequestHandler):
  """Handler to display backup information."""

  SUFFIX = 'backup_information'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    backup_ids = handler.request.get_all('backup_id')
    template_params = {
        'backups': db.get(backup_ids),
        'back_target': handler.request.get('cancel_url'),
    }
    utils.RenderToResponse(handler, 'backup_information.html', template_params)


class BaseDoHandler(webapp.RequestHandler):
  """Base class for all Do*Handlers."""

  MAPREDUCE_DETAIL = utils.config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin backup operations.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get_all('job')
    tasks = self.request.get_all('task')
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')

    template_params = {
        'job_list': jobs,
        'task_list': tasks,
        'mapreduce_detail': self.MAPREDUCE_DETAIL,
        'error': error,
        'xsrf_error': xsrf_error,
        'datastore_admin_home': utils.config.BASE_PATH,
    }
    utils.RenderToResponse(self, self._get_html_page, template_params)

  @property
  def _get_html_page(self):
    """Return the name of the HTML page for HTTP/GET requests."""
    raise NotImplementedError

  @property
  def _get_post_html_page(self):
    """Return the name of the HTML page for HTTP/POST requests."""
    raise NotImplementedError

  def _ProcessPostRequest(self):
    """Process the HTTP/POST request and return the result as parametrs."""
    raise NotImplementedError

  def _GetBasicMapperParams(self):
    namespace = self.request.get('namespace', None)
    if namespace == '*':
      namespace = None
    return {'namespace': namespace}

  def post(self):
    """Handler for post requests to datastore_admin/backup.do.

    Redirects to the get handler after processing the request.
    """
    token = self.request.get('xsrf_token')

    if not utils.ValidateXsrfToken(token, XSRF_ACTION):
      parameters = [('xsrf_error', '1')]
    else:
      try:
        parameters = self._ProcessPostRequest()


      except Exception, e:
        error = self._HandleException(e)
        parameters = [('error', error)]

    query = urllib.urlencode(parameters)
    self.redirect('%s/%s?%s' % (utils.config.BASE_PATH,
                                self._get_post_html_page,
                                query))

  def _HandleException(self, e):
    """Make exception handling overrideable by tests.

    Args:
      e: The exception to handle.

    Returns:
      The exception error string.
    """
    return '%s: %s' % (type(e), e)


class BackupValidationException(Exception):
  pass


def _perform_backup(kinds, selected_namespace,
                    filesystem, gs_bucket_name, backup,
                    queue, mapper_params, max_jobs):
  """Triggers backup mapper jobs.

  Args:
    kinds: a sequence of kind names
    selected_namespace: The selected namespace or None for all
    filesystem: files.BLOBSTORE_FILESYSTEM or files.GS_FILESYSTEM
        or None to default to blobstore
    gs_bucket_name: the GS file system bucket in which to store the backup
        when using the GS file system, and otherwise ignored
    backup: the backup name
    queue: the task queue for the backup task
    mapper_params: the mapper parameters
    max_jobs: if backup needs more jobs than this, defer them

  Returns:
    The job or task ids.

  Raises:
    BackupValidationException: On validation error.
    Exception: On other error.
  """
  BACKUP_COMPLETE_HANDLER = __name__ +  '.BackupCompleteHandler'
  BACKUP_HANDLER = __name__ + '.BackupEntity.map'
  INPUT_READER = __name__ + '.DatastoreEntityProtoInputReader'
  OUTPUT_WRITER = output_writers.__name__ + '.FileRecordsOutputWriter'

  queue = queue or os.environ.get('HTTP_X_APPENGINE_QUEUENAME', 'default')
  if queue[0] == '_':

    queue = 'default'
  if not filesystem:
    filesystem = files.BLOBSTORE_FILESYSTEM
  if filesystem == files.GS_FILESYSTEM:

    if not gs_bucket_name:
      raise BackupValidationException('Bucket name missing.')
    bucket_name, path = parse_gs_handle(gs_bucket_name)
    gs_bucket_name = ('%s/%s' % (bucket_name, path)).rstrip('/')
    validate_gs_bucket_name(bucket_name)
    verify_bucket_writable(bucket_name)
  elif filesystem == files.BLOBSTORE_FILESYSTEM:
    pass
  else:
    raise BackupValidationException('Unknown filesystem "%s".' % filesystem)

  job_name = 'datastore_backup_%s_%%(kind)s' % re.sub(r'[^\w]', '_', backup)
  try:
    job_operation = utils.StartOperation('Backup: %s' % backup)
    backup_info = BackupInformation(parent=job_operation)
    backup_info.filesystem = filesystem
    backup_info.name = backup
    backup_info.kinds = kinds
    if selected_namespace is not None:
      backup_info.namespaces = [selected_namespace]
    backup_info.put(force_writes=True)
    mapreduce_params = {
        'done_callback_handler': BACKUP_COMPLETE_HANDLER,
        'backup_info_pk': str(backup_info.key()),
        'force_ops_writes': True,
    }
    mapper_params = dict(mapper_params)
    mapper_params['filesystem'] = filesystem
    if filesystem == files.GS_FILESYSTEM:
      mapper_params['gs_bucket_name'] = gs_bucket_name
    if len(kinds) <= max_jobs:
      return [('job', job) for job in _run_map_jobs(
          job_operation.key(), backup_info.key(), kinds, job_name,
          BACKUP_HANDLER, INPUT_READER, OUTPUT_WRITER,
          mapper_params, mapreduce_params, queue)]
    else:
      retry_options = taskqueue.TaskRetryOptions(task_retry_limit=1)
      deferred_task = deferred.defer(_run_map_jobs_deferred,
                                     backup, job_operation.key(),
                                     backup_info.key(), kinds, job_name,
                                     BACKUP_HANDLER, INPUT_READER,
                                     OUTPUT_WRITER, mapper_params,
                                     mapreduce_params, queue, _queue=queue,
                                     _url=utils.ConfigDefaults.DEFERRED_PATH,
                                     _retry_options=retry_options)
      return [('task', deferred_task.name)]
  except Exception:
    logging.exception('Failed to start a datastore backup job[s] for "%s".',
                      backup)
    if backup_info:
      delete_backup_info(backup_info)
    if job_operation:
      job_operation.status = utils.DatastoreAdminOperation.STATUS_FAILED
      job_operation.put(force_writes=True)
    raise


class BackupLinkHandler(webapp.RequestHandler):
  """Handler to deal with requests to the backup link to backup data."""

  SUFFIX = 'backup.create'

  def get(self):
    """Handler for get requests to datastore_admin/backup.create."""
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup.create."""
    try:
      backup_prefix = self.request.get('name')
      if not backup_prefix:
        if self.request.headers.get('X-AppEngine-Cron'):
          backup_prefix = 'cron-'
        else:
          backup_prefix = 'link-'
      backup_prefix_with_date = backup_prefix + time.strftime('%Y_%m_%d')
      backup_name = backup_prefix_with_date
      backup_suffix_counter = 1
      while BackupInformation.name_exists(backup_name):
        backup_suffix_counter += 1
        backup_name = backup_prefix_with_date + '-' + str(backup_suffix_counter)
      kinds = self.request.get_all('kind')
      if not kinds:
        self.errorResponse('Backup must include at least one kind.')
        return
      for kind in kinds:
        if not utils.IsKindNameVisible(kind):
          self.errorResponse('Invalid kind %s.' % kind)
          return
      namespace = self.request.get('namespace', None)
      if namespace == '*':
        namespace = None
      mapper_params = {'namespace': namespace}
      _perform_backup(kinds,
                      namespace,
                      self.request.get('filesystem'),
                      self.request.get('gs_bucket_name'),
                      backup_name,
                      self.request.get('queue'),
                      mapper_params,
                      1000000)
    except Exception, e:
      self.errorResponse(e.message)

  def errorResponse(self, message):
    logging.error('Could not create backup via link: %s', message)
    self.response.set_status(400, message)


class DatastoreEntityProtoInputReader(input_readers.RawDatastoreInputReader):
  """An input reader which yields datastore entity proto for a kind."""

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeEntityProtoIterator


class DoBackupHandler(BaseDoHandler):
  """Handler to deal with requests from the admin console to backup data."""

  SUFFIX = 'backup.do'
  _get_html_page = 'do_backup.html'
  _get_post_html_page = SUFFIX

  def _ProcessPostRequest(self):
    """Triggers backup mapper jobs and returns their ids."""
    try:
      backup = self.request.get('backup_name').strip()
      if not backup:
        raise BackupValidationException('Unspecified backup name.')
      if BackupInformation.name_exists(backup):
        raise BackupValidationException('Backup "%s" already exists.' % backup)
      mapper_params = self._GetBasicMapperParams()
      backup_result = _perform_backup(self.request.get_all('kind'),
                                      mapper_params.get('namespace'),
                                      self.request.get('filesystem'),
                                      self.request.get('gs_bucket_name'),
                                      backup,
                                      self.request.get('queue'),
                                      mapper_params,
                                      10)
      return backup_result
    except BackupValidationException, e:
      return [('error', e.message)]


def _run_map_jobs_deferred(backup_name, job_operation_key, backup_info_key,
                           kinds, job_name, backup_handler, input_reader,
                           output_writer, mapper_params, mapreduce_params,
                           queue):
  backup_info = BackupInformation.get(backup_info_key)
  if backup_info:
    try:
      _run_map_jobs(job_operation_key, backup_info_key, kinds, job_name,
                    backup_handler, input_reader, output_writer, mapper_params,
                    mapreduce_params, queue)
    except BaseException:
      logging.exception('Failed to start a datastore backup job[s] for "%s".',
                        backup_name)
      delete_backup_info(backup_info)
  else:
    logging.info('Missing backup info, can not start backup jobs for "%s"',
                 backup_name)


def _run_map_jobs(job_operation_key, backup_info_key, kinds, job_name,
                  backup_handler, input_reader, output_writer, mapper_params,
                  mapreduce_params, queue):
  """Creates backup/restore MR jobs for the given operation.

  Args:
    job_operation_key: a key of utils.DatastoreAdminOperation entity.
    backup_info_key: a key of BackupInformation entity.
    kinds: a list of kinds to run the M/R for.
    job_name: the M/R job name prefix.
    backup_handler: M/R job completion handler.
    input_reader: M/R input reader.
    output_writer: M/R output writer.
    mapper_params: custom parameters to pass to mapper.
    mapreduce_params: dictionary parameters relevant to the whole job.
    queue: the name of the queue that will be used by the M/R.

  Returns:
    Ids of all started mapper jobs as list of strings.
  """
  backup_info = BackupInformation.get(backup_info_key)
  if not backup_info:
    return []
  jobs = utils.RunMapForKinds(
      job_operation_key,
      kinds,
      job_name,
      backup_handler,
      input_reader,
      output_writer,
      mapper_params,
      mapreduce_params,
      queue_name=queue)
  backup_info.active_jobs = jobs
  backup_info.put(force_writes=True)
  return jobs


def get_backup_files(backup_info, selected_kinds=None):
  """Returns the backup filenames for selected kinds or all if None/Empty."""
  if backup_info.blob_files:

    return backup_info.blob_files
  else:
    kinds_backup_files = backup_info.get_kind_backup_files(selected_kinds)
    return list(itertools.chain(*(
        kind_backup_files.files for kind_backup_files in kinds_backup_files)))


def delete_backup_files(filesystem, backup_files):
  if backup_files:

    if filesystem == files.BLOBSTORE_FILESYSTEM:


      blob_keys = []
      for fname in backup_files:
        blob_key = files.blobstore.get_blob_key(fname)
        if blob_key:
          blob_keys.append(blob_key)
          if len(blob_keys) == MAX_BLOBS_PER_DELETE:
            blobstore_api.delete(blob_keys)
            blob_keys = []
      if blob_keys:
        blobstore_api.delete(blob_keys)


def delete_backup_info(backup_info, delete_files=True):
  """Deletes a backup including its associated files and other metadata."""
  if backup_info.blob_files:
    delete_backup_files(backup_info.filesystem, backup_info.blob_files)
    backup_info.delete(force_writes=True)
  else:
    kinds_backup_files = tuple(backup_info.get_kind_backup_files())
    if delete_files:
      delete_backup_files(backup_info.filesystem, itertools.chain(*(
          kind_backup_files.files for kind_backup_files in kinds_backup_files)))
    db.delete(kinds_backup_files + (backup_info,), force_writes=True)


class DoBackupDeleteHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to delete backup data."""

  SUFFIX = 'backup_delete.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup_delete.do.

    Deletes are executed and user is redirected to the base-path handler.
    """
    backup_ids = self.request.get_all('backup_id')
    token = self.request.get('xsrf_token')
    error = None
    if backup_ids and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        for backup_info in db.get(backup_ids):
          if backup_info:
            delete_backup_info(backup_info)
      except Exception, e:
        logging.exception('Failed to delete datastore backup.')
        error = str(e)

    if error:
      query = urllib.urlencode([('error', error)])
      self.redirect('%s?%s' % (utils.config.BASE_PATH, query))
    else:
      self.redirect(utils.config.BASE_PATH)


class DoBackupAbortHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to abort pending backups."""

  SUFFIX = 'backup_abort.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/backup_abort.do.

    Abort is executed and user is redirected to the base-path handler.
    """
    backup_ids = self.request.get_all('backup_id')
    token = self.request.get('xsrf_token')
    error = None
    if backup_ids and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        for backup_info in db.get(backup_ids):
          if backup_info:
            utils.AbortAdminOperation(backup_info.parent_key())
            delete_backup_info(backup_info)
      except Exception, e:
        logging.exception('Failed to abort pending datastore backup.')
        error = str(e)

    if error:
      self.redirect(utils.config.BASE_PATH + '?error=%s' % error)
    else:
      self.redirect(utils.config.BASE_PATH)


class DoBackupRestoreHandler(BaseDoHandler):
  """Handler to restore backup data.

  Deals with requests from the admin console.
  """
  SUFFIX = 'backup_restore.do'
  BACKUP_RESTORE_HANDLER = __name__ + '.RestoreEntity.map'
  RESTORE_COMPLETE_HANDLER = __name__ + '.RestoreCompleteHandler'

  INPUT_READER = input_readers.__name__ + '.RecordsReader'
  _get_html_page = 'do_restore_from_backup.html'
  _get_post_html_page = SUFFIX

  def _ProcessPostRequest(self):
    """Triggers backup restore mapper jobs and returns their ids."""
    backup_id = self.request.get('backup_id')
    if not backup_id:
      return [('error', 'Unspecified Backup.')]

    backup = db.get(db.Key(backup_id))
    if not backup:
      return [('error', 'Invalid Backup id.')]

    if backup.gs_handle:
      if not is_readable_gs_handle(backup.gs_handle):
        return [('error', 'Backup not readable')]

    queue = self.request.get('queue')
    job_name = 'datastore_backup_restore_%s' % re.sub(r'[^\w]', '_',
                                                      backup.name)
    job_operation = None
    kinds = set(self.request.get_all('kind'))
    if not (backup.blob_files or kinds):
      return [('error', 'No kinds were selected')]
    backup_kinds = set(backup.kinds)
    difference = kinds.difference(backup_kinds)
    if difference:
      return [('error', 'Backup does not have kind[s] %s' %
               ', '.join(difference))]
    kinds = list(kinds) if len(backup_kinds) != len(kinds) else []
    try:
      operation_name = 'Restoring %s from backup: %s' % (
          ', '.join(kinds) if kinds else 'all', backup.name)
      job_operation = utils.StartOperation(operation_name)
      mapper_params = self._GetBasicMapperParams()
      mapper_params['files'] = get_backup_files(backup, kinds)
      mapper_params['kind_filter'] = kinds
      mapper_params['original_app'] = backup.original_app
      mapreduce_params = {
          'backup_name': backup.name,
          'force_ops_writes': True
      }
      shard_count = min(max(utils.MAPREDUCE_MIN_SHARDS,
                            len(mapper_params['files'])),
                        utils.MAPREDUCE_MAX_SHARDS)
      job = utils.StartMap(job_operation.key(), job_name,
                           self.BACKUP_RESTORE_HANDLER, self.INPUT_READER, None,
                           mapper_params, mapreduce_params, queue_name=queue,
                           shard_count=shard_count)
      return [('job', job)]
    except Exception:
      logging.exception('Failed to start a restore from backup job "%s".',
                        job_name)
      if job_operation:
        job_operation.status = utils.DatastoreAdminOperation.STATUS_FAILED
        job_operation.put(force_writes=True)
      raise
    finally:



      if self.request.get('delete_backup_after_restore', '').lower() == 'true':
        delete_backup_info(backup, delete_files=False)


class DoBackupImportHandler(BaseDoHandler):
  """Handler to deal with datastore admin requests to import backup info."""

  SUFFIX = 'import_backup.do'

  def get(self):
    self.post()

  def post(self):
    """Handler for post requests to datastore_admin/import_backup.do.

    Import is executed and user is redirected to the base-path handler.
    """
    gs_handle = self.request.get('gs_handle')
    token = self.request.get('xsrf_token')
    error = None
    if gs_handle and utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        bucket_name, path = parse_gs_handle(gs_handle)
        file_content = get_gs_object(bucket_name, path)
        entities = parse_backup_info_file(file_content)
        original_backup_info = entities.next()
        entity = datastore.Entity(BackupInformation.kind())
        entity.update(original_backup_info)
        backup_info = BackupInformation.from_entity(entity)
        if original_backup_info.key().app() != os.getenv('APPLICATION_ID'):
          backup_info.original_app = original_backup_info.key().app()

        def tx():
          backup_info.put(force_writes=True)
          kind_files_models = []
          for entity in entities:
            kind_files = backup_info.create_kind_backup_files(
                entity.key().name(), entity['files'])
            kind_files_models.append(kind_files)
          db.put(kind_files_models, force_writes=True)
        db.run_in_transaction(tx)
        backup_id = str(backup_info.key())
      except Exception, e:
        logging.exception('Failed to Import datastore backup information.')
        error = str(e)

    if error:
      query = urllib.urlencode([('error', error)])
      self.redirect('%s?%s' % (utils.config.BASE_PATH, query))
    elif self.request.get('Restore'):
      ConfirmRestoreFromBackupHandler.Render(
          self, default_backup_id=backup_id,
          default_delete_backup_after_restore=True)
    else:
      self.redirect(utils.config.BASE_PATH)


class BackupInformation(db.Model):
  """An entity to keep information on successful backup operations."""

  name = db.StringProperty()
  kinds = db.StringListProperty()
  namespaces = db.StringListProperty()
  filesystem = db.StringProperty(default=files.BLOBSTORE_FILESYSTEM)
  start_time = db.DateTimeProperty(auto_now_add=True)
  active_jobs = db.StringListProperty()
  completed_jobs = db.StringListProperty()
  complete_time = db.DateTimeProperty(default=None)
  blob_files = db.StringListProperty()
  original_app = db.StringProperty(default=None)
  gs_handle = db.TextProperty(default=None)

  @classmethod
  def kind(cls):
    return utils.BACKUP_INFORMATION_KIND

  @classmethod
  def name_exists(cls, backup_name):
    query = BackupInformation.all(keys_only=True)
    query.filter('name =', backup_name)
    return query.get() is not None

  def create_kind_backup_files_key(self, kind):
    return db.Key.from_path(KindBackupFiles.kind(), kind, parent=self.key())

  def create_kind_backup_files(self, kind, kind_files):
    return KindBackupFiles(key=self.create_kind_backup_files_key(kind),
                           files=kind_files)

  def get_kind_backup_files(self, kinds=None):
    if kinds:
      return db.get([self.create_kind_backup_files_key(kind) for kind in kinds])
    else:
      return KindBackupFiles.all().ancestor(self).run()


class KindBackupFiles(db.Model):
  """An entity to keep files information per kind for a backup.

  A key for this model should created using kind as a name and the associated
  BackupInformation as a parent.
  """
  files = db.StringListProperty(indexed=False)

  @property
  def backup_kind(self):
    return self.key().name()

  @classmethod
  def kind(cls):
    return utils.BACKUP_INFORMATION_FILES_KIND


@db.transactional
def BackupCompleteHandler(operation, job_id, mapreduce_state):
  """Updates BackupInformation record for a completed mapper job."""
  mapreduce_spec = mapreduce_state.mapreduce_spec
  kind = mapreduce_spec.mapper.params['entity_kind']
  backup_info = BackupInformation.get(mapreduce_spec.params['backup_info_pk'])
  if backup_info:
    if job_id in backup_info.active_jobs:
      backup_info.active_jobs.remove(job_id)
      backup_info.completed_jobs = list(
          set(backup_info.completed_jobs + [job_id]))
    filenames = mapreduce_state.writer_state['filenames']


    if backup_info.filesystem == files.BLOBSTORE_FILESYSTEM:
      filenames = drop_empty_files(filenames)
    if backup_info.blob_files:




      backup_info.blob_files = list(set(backup_info.blob_files + filenames))
      backup_info.put(force_writes=True)
    else:
      kind_backup_files = backup_info.get_kind_backup_files([kind])[0]
      if kind_backup_files:
        kind_backup_files.files = list(set(kind_backup_files.files + filenames))
      else:
        kind_backup_files = backup_info.create_kind_backup_files(kind,
                                                                 filenames)
      db.put((backup_info, kind_backup_files), force_writes=True)
    if operation.status == utils.DatastoreAdminOperation.STATUS_COMPLETED:
      deferred.defer(finalize_backup_info, backup_info.key(),
                     mapreduce_spec.mapper.params,
                     _url=utils.ConfigDefaults.DEFERRED_PATH,
                     _queue=mapreduce_spec.params.get('done_callback_queue'),
                     _transactional=True)
  else:
    logging.warn('BackupInfo was not found for %s',
                 mapreduce_spec.params['backup_info_pk'])


def finalize_backup_info(backup_info_pk, mapper_params):
  """Finalize the state of BackupInformation and creates info file for GS."""


  def tx():
    backup_info = BackupInformation.get(backup_info_pk)
    if backup_info:
      backup_info.complete_time = datetime.datetime.now()
      if backup_info.filesystem == files.GS_FILESYSTEM:
        gs_bucket = mapper_params['gs_bucket_name']
        BackupInfoWriter(gs_bucket).write(backup_info)
      backup_info.put(force_writes=True)
      logging.info('Backup %s completed', backup_info.name)
    else:
      logging.warn('Backup %s could not be found', backup_info_pk)
  db.run_in_transaction(tx)


def parse_backup_info_file(content):
  """Returns entities iterator from a backup_info file content."""
  reader = records.RecordsReader(cStringIO.StringIO(content))
  version = reader.read()
  if version != '1':
    raise IOError('Unsupported version')
  return (datastore.Entity.FromPb(record) for record in reader)


@db.non_transactional
def drop_empty_files(filenames):
  """Deletes empty files and returns filenames minus the deleted ones."""
  non_empty_filenames = []
  empty_file_keys = []
  blobs_info = blobstore.BlobInfo.get(
      [files.blobstore.get_blob_key(fn) for fn in filenames])
  for filename, blob_info in itertools.izip(filenames, blobs_info):
    if blob_info:
      if blob_info.size > 0:
        non_empty_filenames.append(filename)
      else:
        empty_file_keys.append(blob_info.key())
  blobstore_api.delete(empty_file_keys)
  return non_empty_filenames


class BackupInfoWriter(object):
  """A class for writing Datastore backup metadata files."""

  def __init__(self, gs_bucket):
    """Construct a BackupInfoWriter.

    Args:
      gs_bucket: Required string for the target GS bucket.
    """
    self.__gs_bucket = gs_bucket

  def write(self, backup_info):
    """Write the metadata files for the given backup_info.

    Args:
      backup_info: Required BackupInformation.

    Returns:
      A list with Backup info filename followed by Kind info filenames.
    """
    fn = self._write_backup_info(backup_info)
    return [fn] + self._write_kind_info(backup_info)

  def _generate_filename(self, backup_info, suffix):
    key_str = str(backup_info.key()).replace('/', '_')
    return '/gs/%s/%s%s' % (self.__gs_bucket, key_str, suffix)

  def _write_backup_info(self, backup_info):
    """Writes a backup_info_file.

    Args:
      backup_info: Required BackupInformation.

    Returns:
      Backup info filename.
    """
    filename = self._generate_filename(backup_info, '.backup_info')
    backup_info.gs_handle = filename
    info_file = files.open(files.gs.create(filename), 'a', exclusive_lock=True)
    try:
      with records.RecordsWriter(info_file) as writer:

        writer.write('1')

        writer.write(db.model_to_protobuf(backup_info).SerializeToString())

        for kind_files in backup_info.get_kind_backup_files():
          writer.write(db.model_to_protobuf(kind_files).SerializeToString())
    finally:
      info_file.close(finalize=True)
    return filename

  def _write_kind_info(self, backup_info):
    """Writes type information schema for each kind in backup_info.

    Args:
      backup_info: Required BackupInformation.

    Returns:
      A list with all created filenames.
    """
    filenames = []
    for kind_backup_files in backup_info.get_kind_backup_files():
      backup = self._create_kind_backup(backup_info, kind_backup_files)
      filename = self._generate_filename(
          backup_info, '.%s.backup_info' % kind_backup_files.backup_kind)
      self._write_kind_backup_info_file(filename, backup)
      filenames.append(filename)
    return filenames

  def _create_kind_backup(self, backup_info, kind_backup_files):
    """Creates and populate a backup_pb2.Backup."""
    backup = backup_pb2.Backup()
    backup.backup_info.backup_name = backup_info.name
    backup.backup_info.start_timestamp = datastore_types.DatetimeToTimestamp(
        backup_info.start_time)
    backup.backup_info.end_timestamp = datastore_types.DatetimeToTimestamp(
        backup_info.complete_time)
    kind = kind_backup_files.backup_kind
    kind_info = backup.kind_info.add()
    kind_info.kind = kind
    kind_info.entity_schema.kind = kind
    kind_info.file.extend(kind_backup_files.files)
    entity_type_info = EntityTypeInfo(kind=kind)
    for sharded_aggregation in SchemaAggregationResult.load(
        backup_info.key(), kind):
      if sharded_aggregation.is_partial:
        kind_info.is_partial = True
      if sharded_aggregation.entity_type_info:
        entity_type_info.merge(sharded_aggregation.entity_type_info)
    entity_type_info.populate_entity_schema(kind_info.entity_schema)
    return backup

  @classmethod
  def _write_kind_backup_info_file(cls, filename, backup):
    """Writes a kind backup_info.

    Args:
      filename: The name of the file to be created as string.
      backup: apphosting.ext.datastore_admin.Backup proto.
    """
    f = files.open(files.gs.create(filename), 'a', exclusive_lock=True)
    try:
      f.write(backup.SerializeToString())
    finally:
      f.close(finalize=True)


class PropertyTypeInfo(model.JsonMixin):
  """Type information for an entity property."""

  def __init__(self, name, is_repeated=False, primitive_types=None,
               embedded_entities=None):
    """Construct a PropertyTypeInfo instance.

    Args:
      name: The name of the property as a string.
      is_repeated: A boolean that indicates if the property is repeated.
      primitive_types: Optional list of PrimitiveType integer values.
      embedded_entities: Optional list of EntityTypeInfo.
    """
    self.__name = name
    self.__is_repeated = is_repeated
    self.__primitive_types = set(primitive_types) if primitive_types else set()
    self.__embedded_entities = {}
    for entity in embedded_entities or ():
      if entity.kind in self.__embedded_entities:
        self.__embedded_entities[entity.kind].merge(entity)
      else:
        self.__embedded_entities[entity.kind] = entity

  @property
  def name(self):
    return self.__name

  @property
  def is_repeated(self):
    return self.__is_repeated

  @property
  def primitive_types(self):
    return self.__primitive_types

  def embedded_entities_kind_iter(self):
    return self.__embedded_entities.iterkeys()

  def get_embedded_entity(self, kind):
    return self.__embedded_entities.get(kind)

  def merge(self, other):
    """Merge a PropertyTypeInfo with this instance.

    Args:
      other: Required PropertyTypeInfo to merge.

    Returns:
      True if anything was changed. False otherwise.

    Raises:
      ValueError: if property names do not match.
      TypeError: if other is not instance of PropertyTypeInfo.
    """
    if not isinstance(other, PropertyTypeInfo):
      raise TypeError('Expected PropertyTypeInfo, was %r' % (other,))

    if other.__name != self.__name:
      raise ValueError('Property names mismatch (%s, %s)' %
                       (self.__name, other.__name))
    changed = False
    if other.__is_repeated and not self.__is_repeated:
      self.__is_repeated = True
      changed = True
    if not other.__primitive_types.issubset(self.__primitive_types):
      self.__primitive_types = self.__primitive_types.union(
          other.__primitive_types)
      changed = True
    for kind, other_embedded_entity in other.__embedded_entities.iteritems():
      embedded_entity = self.__embedded_entities.get(kind)
      if embedded_entity:
        changed = embedded_entity.merge(other_embedded_entity) or changed
      else:
        self.__embedded_entities[kind] = other_embedded_entity
        changed = True
    return changed

  def populate_entity_schema_field(self, entity_schema):
    """Add an populate a Field to the given entity_schema.

    Args:
      entity_schema: apphosting.ext.datastore_admin.EntitySchema proto.
    """
    if not (self.__primitive_types or self.__embedded_entities):
      return

    field = entity_schema.field.add()
    field.name = self.__name
    field_type = field.type.add()
    field_type.is_list = self.__is_repeated
    field_type.primitive_type.extend(self.__primitive_types)
    for embedded_entity in self.__embedded_entities.itervalues():
      embedded_entity_schema = field_type.embedded_schema.add()
      embedded_entity.populate_entity_schema(embedded_entity_schema)

  def to_json(self):
    json = dict()
    json['name'] = self.__name
    json['is_repeated'] = self.__is_repeated
    json['primitive_types'] = list(self.__primitive_types)
    json['embedded_entities'] = [e.to_json() for e in
                                 self.__embedded_entities.itervalues()]
    return json

  @classmethod
  def from_json(cls, json):
    return cls(json['name'], json['is_repeated'], json.get('primitive_types'),
               [EntityTypeInfo.from_json(entity_json) for entity_json
                in json.get('embedded_entities')])


class EntityTypeInfo(model.JsonMixin):
  """Type information for an entity."""

  def __init__(self, kind=None, properties=None):
    """Construct an EntityTypeInfo instance.

    Args:
      kind: An optional kind name as string.
      properties: An optional list of PropertyTypeInfo.
    """
    self.__kind = kind
    self.__properties = {}
    for property_type_info in properties or ():
      if property_type_info.name in self.__properties:
        self.__properties[property_type_info.name].merge(property_type_info)
      else:
        self.__properties[property_type_info.name] = property_type_info

  @property
  def kind(self):
    return self.__kind

  def properties_name_iter(self):
    return self.__properties.iterkeys()

  def get_property(self, name):
    return self.__properties.get(name)

  def merge(self, other):
    """Merge an EntityTypeInfo with this instance.

    Args:
      other: Required EntityTypeInfo to merge.

    Returns:
      True if anything was changed. False otherwise.

    Raises:
      ValueError: if kinds do not match.
      TypeError: if other is not instance of EntityTypeInfo.
    """
    if not isinstance(other, EntityTypeInfo):
      raise TypeError('Expected EntityTypeInfo, was %r' % (other,))

    if other.__kind != self.__kind:
      raise ValueError('Kinds mismatch (%s, %s)' % (self.__kind, other.__kind))
    changed = False
    for name, other_property in other.__properties.iteritems():
      self_property = self.__properties.get(name)
      if self_property:
        changed = self_property.merge(other_property) or changed
      else:
        self.__properties[name] = other_property
        changed = True
    return changed

  def populate_entity_schema(self, entity_schema):
    """Populates the given entity_schema with values from this instance.

    Args:
      entity_schema: apphosting.ext.datastore_admin.EntitySchema proto.
    """
    if self.__kind:
      entity_schema.kind = self.__kind
    for property_type_info in self.__properties.itervalues():
      property_type_info.populate_entity_schema_field(entity_schema)

  def to_json(self):
    return {
        'kind': self.__kind,
        'properties': [p.to_json() for p in self.__properties.itervalues()]
    }

  @classmethod
  def from_json(cls, json):
    kind = json.get('kind')
    properties_json = json.get('properties')
    if properties_json:
      return cls(kind, [PropertyTypeInfo.from_json(p) for p in properties_json])
    else:
      return cls(kind)

  @classmethod
  def create_from_entity_proto(cls, entity_proto):
    """Creates and populates an EntityTypeInfo from an EntityProto."""
    properties = [cls.__get_property_type_info(property_proto) for
                  property_proto in itertools.chain(
                      entity_proto.property_list(),
                      entity_proto.raw_property_list())]
    kind = utils.get_kind_from_entity_pb(entity_proto)
    return cls(kind, properties)

  @classmethod
  def __get_property_type_info(cls, property_proto):
    """Returns the type mapping for the provided property."""
    name = property_proto.name()
    is_repeated = bool(property_proto.multiple())
    primitive_type = None
    entity_type = None
    if property_proto.has_meaning():
      primitive_type = MEANING_TO_PRIMITIVE_TYPE.get(property_proto.meaning())
    if primitive_type is None:
      value = property_proto.value()
      if value.has_int64value():
        primitive_type = backup_pb2.EntitySchema.INTEGER
      elif value.has_booleanvalue():
        primitive_type = backup_pb2.EntitySchema.BOOLEAN
      elif value.has_stringvalue():
        if property_proto.meaning() == entity_pb.Property.ENTITY_PROTO:
          entity_proto = entity_pb.EntityProto()
          try:
            entity_proto.ParsePartialFromString(value.stringvalue())
          except Exception:

            pass
          else:
            entity_type = EntityTypeInfo.create_from_entity_proto(entity_proto)
        else:
          primitive_type = backup_pb2.EntitySchema.STRING
      elif value.has_doublevalue():
        primitive_type = backup_pb2.EntitySchema.FLOAT
      elif value.has_pointvalue():
        primitive_type = backup_pb2.EntitySchema.GEO_POINT
      elif value.has_uservalue():
        primitive_type = backup_pb2.EntitySchema.USER
      elif value.has_referencevalue():
        primitive_type = backup_pb2.EntitySchema.REFERENCE
    return PropertyTypeInfo(
        name, is_repeated,
        (primitive_type,) if primitive_type is not None else None,
        (entity_type,) if entity_type else None)


class SchemaAggregationResult(db.Model):
  """Persistent aggregated type information for a kind.

  An instance can be retrieved via the load method or created
  using the create method. An instance aggregates all type information
  for all seen embedded_entities via the merge method and persisted when needed
  using the model put method.
  """

  entity_type_info = model.JsonProperty(
      EntityTypeInfo, default=EntityTypeInfo(), indexed=False)
  is_partial = db.BooleanProperty(default=False)

  def merge(self, other):
    """Merge a SchemaAggregationResult or an EntityTypeInfo with this instance.

    Args:
      other: Required SchemaAggregationResult or EntityTypeInfo to merge.

    Returns:
      True if anything was changed. False otherwise.
    """
    if self.is_partial:
      return False
    if isinstance(other, SchemaAggregationResult):
      other = other.entity_type_info
    return self.entity_type_info.merge(other)

  @classmethod
  def _get_parent_key(cls, backup_id, kind_name):
    return datastore_types.Key.from_path('Kind', kind_name, parent=backup_id)

  @classmethod
  def create(cls, backup_id, kind_name, shard_id):
    """Create SchemaAggregationResult instance.

    Args:
      backup_id: Required BackupInformation Key.
      kind_name: Required kind name as string.
      shard_id: Required shard id as string.

    Returns:
      A new SchemaAggregationResult instance.
    """
    parent = cls._get_parent_key(backup_id, kind_name)
    return SchemaAggregationResult(
        key_name=shard_id, parent=parent,
        entity_type_info=EntityTypeInfo(kind=kind_name))

  @classmethod
  def load(cls, backup_id, kind_name, shard_id=None):
    """Retrieve SchemaAggregationResult from the Datastore.

    Args:
      backup_id: Required BackupInformation Key.
      kind_name: Required kind name as string.
      shard_id: Optional shard id as string.

    Returns:
      SchemaAggregationResult iterator or an entity if shard_id not None.
    """
    parent = cls._get_parent_key(backup_id, kind_name)
    if shard_id:
      key = datastore_types.Key.from_path(cls.kind(), shard_id, parent=parent)
      return SchemaAggregationResult.get(key)
    else:
      return db.Query(cls).ancestor(parent).run()

  @classmethod
  def kind(cls):
    return utils.BACKUP_INFORMATION_KIND_TYPE_INFO



class SchemaAggregationPool(object):
  """An MR pool to aggregation type information per kind."""

  def __init__(self, backup_id, kind, shard_id):
    """Construct SchemaAggregationPool instance.

    Args:
      backup_id: Required BackupInformation Key.
      kind: Required kind name as string.
      shard_id: Required shard id as string.
    """
    self.__backup_id = backup_id
    self.__kind = kind
    self.__shard_id = shard_id
    self.__aggregation = SchemaAggregationResult.load(backup_id, kind, shard_id)
    if not self.__aggregation:
      self.__aggregation = SchemaAggregationResult.create(backup_id, kind,
                                                          shard_id)
      self.__needs_save = True
    else:
      self.__needs_save = False

  def merge(self, entity_type_info):
    """Merge EntityTypeInfo into aggregated type information."""
    if self.__aggregation.merge(entity_type_info):
      self.__needs_save = True

  def flush(self):
    """Save aggregated type information to the datastore if changed."""
    if self.__needs_save:

      def update_aggregation_tx():
        aggregation = SchemaAggregationResult.load(
            self.__backup_id, self.__kind, self.__shard_id)
        if aggregation:
          if aggregation.merge(self.__aggregation):
            aggregation.put(force_writes=True)
          self.__aggregation = aggregation
        else:
          self.__aggregation.put(force_writes=True)

      def mark_aggregation_as_partial_tx():
        aggregation = SchemaAggregationResult.load(
            self.__backup_id, self.__kind, self.__shard_id)
        if aggregation is None:
          aggregation = SchemaAggregationResult.create(
              self.__backup_id, self.__kind, self.__shard_id)
        aggregation.is_partial = True
        aggregation.put(force_writes=True)
        self.__aggregation = aggregation

      try:
        db.run_in_transaction(update_aggregation_tx)
      except apiproxy_errors.RequestTooLargeError:
        db.run_in_transaction(mark_aggregation_as_partial_tx)
      self.__needs_save = False


class AggregateSchema(op.Operation):
  """An MR Operation to aggregation type information for a kind.

  This operation will register an MR pool, SchemaAggregationPool, if
  one is not already registered and will invoke the pool's merge operation
  per entity. The pool is responsible for keeping a persistent state of
  type aggregation using the sharded db model, SchemaAggregationResult.
  """

  def __init__(self, entity_proto):
    self.__entity_info = EntityTypeInfo.create_from_entity_proto(entity_proto)

  def __call__(self, ctx):
    pool = ctx.get_pool('schema_aggregation_pool')
    if not pool:
      backup_id = datastore_types.Key(
          context.get().mapreduce_spec.params['backup_info_pk'])
      pool = SchemaAggregationPool(
          backup_id, self.__entity_info.kind, ctx.shard_id)
      ctx.register_pool('schema_aggregation_pool', pool)
    pool.merge(self.__entity_info)


class BackupEntity(object):
  """A class which dumps the entity to the writer."""

  def map(self, entity_proto):
    """Backup entity map handler.

    Args:
      entity_proto: An instance of entity_pb.EntityProto.

    Yields:
      A serialized entity_pb.EntityProto as a string
    """
    yield entity_proto.SerializeToString()
    yield AggregateSchema(entity_proto)


class RestoreEntity(object):
  """A class which restore the entity to datastore."""

  def __init__(self):
    self.initialized = False
    self.kind_filter = None
    self.app_id = None

  def initialize(self):
    if self.initialized:
      return
    mapper_params = context.get().mapreduce_spec.mapper.params
    kind_filter = mapper_params.get('kind_filter')
    self.kind_filter = set(kind_filter) if kind_filter else None
    original_app = mapper_params.get('original_app')
    if original_app and os.getenv('APPLICATION_ID') != original_app:
      self.app_id = os.getenv('APPLICATION_ID')
    self.initialized = True

  def map(self, record):
    """Restore entity map handler.

    Args:
      record: A serialized entity_pb.EntityProto.

    Yields:
      A operation.db.Put for the mapped entity
    """
    self.initialize()
    pb = entity_pb.EntityProto(contents=record)
    if self.app_id:
      utils.FixKeys(pb, self.app_id)
    entity = datastore.Entity.FromPb(pb)
    if not self.kind_filter or entity.kind() in self.kind_filter:
      yield op.db.Put(entity)
      if self.app_id:
        yield utils.AllocateMaxId(entity.key(), self.app_id)


def validate_gs_bucket_name(bucket_name):
  """Validate the format of the given bucket_name.

  Validation rules are based:
  https://developers.google.com/storage/docs/bucketnaming#requirements

  Args:
    bucket_name: The bucket name to validate.

  Raises:
    BackupValidationException: If the bucket name is invalid.
  """
  if len(bucket_name) > MAX_BUCKET_LEN:
    raise BackupValidationException(
        'Bucket name length should not be longer than %d' % MAX_BUCKET_LEN)
  if len(bucket_name) < MIN_BUCKET_LEN:
    raise BackupValidationException(
        'Bucket name length should be longer than %d' % MIN_BUCKET_LEN)
  if bucket_name.lower().startswith('goog'):
    raise BackupValidationException(
        'Bucket name should not start with a "goog" prefix')
  bucket_elements = bucket_name.split('.')
  for bucket_element in bucket_elements:
    if len(bucket_element) > MAX_BUCKET_SEGMENT_LEN:
      raise BackupValidationException(
          'Segment length of bucket name should not be longer than %d' %
          MAX_BUCKET_SEGMENT_LEN)
  if not re.match(BUCKET_PATTERN, bucket_name):
    raise BackupValidationException('Invalid bucket name "%s"' % bucket_name)


def is_accessible_bucket_name(bucket_name):
  """Returns True if the application has access to the specified bucket."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_write'
  url = 'https://%s.commondatastorage.googleapis.com/' % bucket_name
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.HEAD, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  return result and result.status_code == 200


def verify_bucket_writable(bucket_name):
  """Verify the application can write to the specified bucket.

  Args:
    bucket_name: The bucket to verify.

  Raises:
    BackupValidationException: If the bucket is not writable.
  """
  path = '/gs/%s' % bucket_name
  try:
    file_names = files.gs.listdir(path,
                                  {'prefix': TEST_WRITE_FILENAME_PREFIX,
                                   'max_keys': MAX_KEYS_LIST_SIZE})
  except (files.InvalidParameterError, files.PermissionDeniedError):
    raise BackupValidationException('Bucket "%s" not accessible' % bucket_name)
  except files.InvalidFileNameError:
    raise BackupValidationException('Bucket "%s" does not exist' % bucket_name)
  file_name = '%s/%s.tmp' % (path, TEST_WRITE_FILENAME_PREFIX)
  file_name_try = 0
  while True:
    if file_name_try >= MAX_TEST_FILENAME_TRIES:


      return
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


def is_readable_gs_handle(gs_handle):
  """Return True if the application can read the specified gs_handle."""
  try:
    with files.open(gs_handle) as bak_file:
      bak_file.read(1)
  except files.PermissionDeniedError:
    return False
  return True



def parse_gs_handle(gs_handle):
  """Splits [/gs/]?bucket_name[/folder]*[/file]? to (bucket_name, path | '')."""
  if gs_handle.startswith('/'):
    filesystem = gs_handle[1:].split('/', 1)[0]
    if filesystem == 'gs':
      gs_handle = gs_handle[4:]
    else:
      raise BackupValidationException('Unsupported filesystem: %s' % filesystem)
  tokens = gs_handle.split('/', 1)
  return (tokens[0], '') if len(tokens) == 1 else tuple(tokens)


def list_bucket_files(bucket_name, prefix, max_keys=1000):
  """Returns a listing of of a bucket that matches the given prefix."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_only'
  url = 'https://%s.commondatastorage.googleapis.com/?' % bucket_name
  query = [('max-keys', max_keys)]
  if prefix:
    query.append(('prefix', prefix))
  url += urllib.urlencode(query)
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.GET, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  if result and result.status_code == 200:
    doc = xml.dom.minidom.parseString(result.content)
    return [node.childNodes[0].data for node in doc.getElementsByTagName('Key')]
  raise BackupValidationException('Request to Google Cloud Storage failed')


def get_gs_object(bucket_name, path):
  """Returns a listing of of a bucket that matches the given prefix."""
  scope = 'https://www.googleapis.com/auth/devstorage.read_only'
  url = 'https://%s.commondatastorage.googleapis.com/%s' % (bucket_name, path)
  auth_token, _ = app_identity.get_access_token(scope)
  result = urlfetch.fetch(url, method=urlfetch.GET, headers={
      'Authorization': 'OAuth %s' % auth_token,
      'x-goog-api-version': '2'})
  if result and result.status_code == 200:
    return result.content
  raise BackupValidationException('Requested path was not found')



def get_queue_names(app_id=None, max_rows=100):
  """Returns a list with all non-special queue names for app_id."""
  rpc = apiproxy_stub_map.UserRPC('taskqueue')
  request = taskqueue_service_pb.TaskQueueFetchQueuesRequest()
  response = taskqueue_service_pb.TaskQueueFetchQueuesResponse()
  if app_id:
    request.set_app_id(app_id)
  request.set_max_rows(max_rows)
  queues = ['default']
  try:
    rpc.make_call('FetchQueues', request, response)
    rpc.check_success()

    for queue in response.queue_list():
      if (queue.mode() == taskqueue_service_pb.TaskQueueMode.PUSH and
          not queue.queue_name().startswith('__') and
          queue.queue_name() != 'default'):
        queues.append(queue.queue_name())
  except Exception:
    logging.exception('Failed to get queue names.')
  return queues


def handlers_list(base_path):
  return [
      (r'%s/%s' % (base_path, BackupLinkHandler.SUFFIX),
       BackupLinkHandler),
      (r'%s/%s' % (base_path, ConfirmBackupHandler.SUFFIX),
       ConfirmBackupHandler),
      (r'%s/%s' % (base_path, DoBackupHandler.SUFFIX), DoBackupHandler),
      (r'%s/%s' % (base_path, DoBackupRestoreHandler.SUFFIX),
       DoBackupRestoreHandler),
      (r'%s/%s' % (base_path, DoBackupDeleteHandler.SUFFIX),
       DoBackupDeleteHandler),
      (r'%s/%s' % (base_path, DoBackupAbortHandler.SUFFIX),
       DoBackupAbortHandler),
      (r'%s/%s' % (base_path, DoBackupImportHandler.SUFFIX),
       DoBackupImportHandler),
      ]
