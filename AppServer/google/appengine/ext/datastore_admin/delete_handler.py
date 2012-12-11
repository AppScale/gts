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





import re
import urllib

from google.appengine.api import datastore
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation

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
    namespace = handler.request.get('namespace')
    kinds = handler.request.get_all('kind')
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)

    (namespace_str, kind_str) = utils.GetPrintableStrs(namespace, kinds)
    template_params = {
        'form_target': DoDeleteHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'app_id': handler.request.get('app_id'),
        'cancel_url': handler.request.get('cancel_url'),
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
  INPUT_READER = (
      'google.appengine.ext.mapreduce.input_readers.DatastoreKeyInputReader')
  MAPREDUCE_DETAIL = utils.config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin/delete.do.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get_all('job')
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')

    template_params = {
        'job_list': jobs,
        'mapreduce_detail': self.MAPREDUCE_DETAIL,
        'error': error,
        'xsrf_error': xsrf_error,
        'datastore_admin_home': utils.config.BASE_PATH,
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

    jobs = []
    if utils.ValidateXsrfToken(token, XSRF_ACTION):
      try:
        op = utils.StartOperation(
            'Deleting %s%s' % (kinds_str, namespace_str))
        name_template = 'Delete all %(kind)s objects%(namespace)s'
        jobs = utils.RunMapForKinds(
            op.key(),
            kinds,
            name_template,
            self.DELETE_HANDLER,
            self.INPUT_READER,
            None,
            {})
        error = ''


      except Exception, e:
        error = self._HandleException(e)

      parameters = [('job', job) for job in jobs]
      if error:
        parameters.append(('error', error))
    else:
      parameters = [('xsrf_error', '1')]

    query = urllib.urlencode(parameters)

    self.redirect('%s/%s?%s' % (utils.config.BASE_PATH, self.SUFFIX, query))

  def _HandleException(self, e):
    """Make exception handling overrideable by tests.

    In normal cases, return only the error string; do not fail to render the
    page for user.
    """
    return str(e)
