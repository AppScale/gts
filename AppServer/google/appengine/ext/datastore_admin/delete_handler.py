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




"""Used to confirm and act on delete requests from the Admin Console."""






import os
import re
import urllib

# AppScale: Use bundled mapreduce library.
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation

from google.appengine.api import capabilities
from google.appengine.api import datastore
import webapp2 as webapp
from google.appengine.ext.datastore_admin import config
from google.appengine.ext.datastore_admin import utils


MAPREDUCE_OBJECTS = [model.MapreduceState.kind(),
                     model.ShardState.kind()]
XSRF_ACTION = 'delete'
KIND_AND_SIZE_RE = re.compile('^(.*)\|(-?[0-9]+)$')


def DeleteEntity(key):
  """Delete function which deletes all processed entities.

  Args:
    key: key of the entity to delete.

  Yields:
    a delete operation if the entity is not an active mapreduce or
    DatastoreAdminOperation object.
  """
  if key.kind() in MAPREDUCE_OBJECTS:
    entity = datastore.Get(key)
    if entity and not entity["active"]:
      yield operation.db.Delete(key)
  elif key.kind() == utils.DatastoreAdminOperation.kind():
    entity = datastore.Get(key)
    if entity and not entity["active_jobs"]:
      yield operation.db.Delete(key)
  else:
    yield operation.db.Delete(key)


class ConfirmDeleteHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to delete data."""

  SUFFIX = 'confirm_delete'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py or get.

    This method executes no action, so the method by which it is accessed is
    immaterial.  Creating a form with get may be a desirable function.  That is,
    if this builtin is turned on, anyone can create a form to delete a kind by
    simply linking to the ConfirmDeleteHandler like so:
    <a href="/_ah/datastore_admin/confirm_delete?kind=trash">
        Delete all Trash Objects</a>

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    readonly_warning = not capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    namespace = handler.request.get('namespace')
    kinds = handler.request.get_all('kind')
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)

    (namespace_str, kind_str) = utils.GetPrintableStrs(namespace, kinds)
    template_params = {
        'readonly_warning': readonly_warning,
        'form_target': DoDeleteHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'app_id': handler.request.get('app_id'),
        'datastore_admin_home': utils.GenerateHomeUrl(handler.request),
        'kind_str': kind_str,
        'namespace_str': namespace_str,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
    }
    utils.RenderToResponse(handler, 'confirm_delete.html', template_params)

  def get(self):
    """Handler for get requests to datastore_admin/confirm_delete."""
    ConfirmDeleteHandler.Render(self)


class DoDeleteHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to delete data."""

  SUFFIX = 'delete.do'
  DELETE_HANDLER = (
      'google.appengine.ext.datastore_admin.delete_handler.DeleteEntity')
  INPUT_READER = input_readers.__name__ + '.DatastoreKeyInputReader'
  MAPREDUCE_DETAIL = config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin/delete.do.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get_all('job')
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')
    noconfirm_error = self.request.get('noconfirm_error', '')

    template_params = {
        'job_list': jobs,
        'mapreduce_detail': self.MAPREDUCE_DETAIL,
        'error': error,
        'xsrf_error': xsrf_error,
        'noconfirm_error': noconfirm_error,
        'datastore_admin_home': config.BASE_PATH,
    }
    utils.RenderToResponse(self, 'do_delete.html', template_params)

  def post(self):
    """Handler for post requests to datastore_admin/delete.do.

    Jobs are executed and user is redirected to the get handler.
    """
    namespace = self.request.get('namespace')
    kinds = self.request.get_all('kind')
    (namespace_str, kinds_str) = utils.GetPrintableStrs(namespace, kinds)
    token = self.request.get('xsrf_token')
    readonly_warning = self.request.get('readonly_warning')

    jobs = []

    if (readonly_warning == 'True') and not self.request.get(
        'confirm_readonly_delete'):
      parameters = [('noconfirm_error', '1')]
    else:
      if utils.ValidateXsrfToken(token, XSRF_ACTION):
        try:
          op = utils.StartOperation(
              'Deleting %s%s' % (kinds_str, namespace_str))
          name_template = 'Delete all %(kind)s objects%(namespace)s'
          mapreduce_params = {'force_ops_writes': True}
          queue = self.request.get('queue')
          queue = queue or os.environ.get(
              'HTTP_X_APPENGINE_QUEUENAME', 'default')
          if queue[0] == '_':

            queue = 'default'
          jobs = utils.RunMapForKinds(
              op.key(),
              kinds,
              name_template,
              self.DELETE_HANDLER,
              self.INPUT_READER,
              None,
              {},
              mapreduce_params=mapreduce_params,
              queue_name=queue,
              max_shard_count=utils.MAPREDUCE_DEFAULT_SHARDS)
          error = ''


        except Exception, e:
          error = self._HandleException(e)

        parameters = [('job', job) for job in jobs]
        if error:
          parameters.append(('error', error))
      else:
        parameters = [('xsrf_error', '1')]

    query = urllib.urlencode(parameters)

    self.redirect('%s/%s?%s' % (config.BASE_PATH, self.SUFFIX, query))

  def _HandleException(self, e):
    """Make exception handling overrideable by tests.

    In normal cases, return only the error string; do not fail to render the
    page for user.
    """
    return str(e)
