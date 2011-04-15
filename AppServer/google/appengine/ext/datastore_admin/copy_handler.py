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





"""Handler for data copy operation.

Generic datastore admin console transfers control to ConfirmCopyHandler
after selection of entities. The ConfirmCopyHandler confirms with user
his choice, enters target application id and transfers control to
DoCopyHandler. DoCopyHandler starts copying mappers and displays confirmation
page.

This module also contains actual mapper code for copying data over.
"""


import logging
import urllib

from google.appengine.api import datastore
from google.appengine.api import capabilities
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import remote_api_put_stub
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import operation


XSRF_ACTION = 'copy'


class ConfirmCopyHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to copy data."""

  SUFFIX = 'confirm_copy'

  @classmethod
  def Render(cls, handler):
    """Rendering method that can be called by main.py.

    Args:
      handler: the webapp.RequestHandler invoking the method
    """
    namespace = handler.request.get('namespace')
    kinds = handler.request.get('kind', allow_multiple=True)
    sizes_known, size_total, remainder = utils.ParseKindsAndSizes(kinds)

    (namespace_str, kind_str) = utils.GetPrintableStrs(namespace, kinds)
    notreadonly_warning = capabilities.CapabilitySet(
        'datastore_v3', capabilities=['write']).is_enabled()
    blob_warning = bool(blobstore.BlobInfo.all().fetch(1))
    datastore_type = datastore._GetConnection().get_datastore_type()
    high_replication_warning = (
        datastore_type == datastore_rpc.Connection.HIGH_REPLICATION_DATASTORE)

    template_params = {
        'form_target': DoCopyHandler.SUFFIX,
        'kind_list': kinds,
        'remainder': remainder,
        'sizes_known': sizes_known,
        'size_total': size_total,
        'app_id': handler.request.get('app_id'),
        'cancel_url': handler.request.get('cancel_url'),
        'kind_str': kind_str,
        'namespace_str': namespace_str,
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
        'notreadonly_warning': notreadonly_warning,
        'blob_warning': blob_warning,
        'high_replication_warning': high_replication_warning,
    }
    utils.RenderToResponse(handler, 'confirm_copy.html', template_params)




class DoCopyHandler(webapp.RequestHandler):
  """Handler to deal with requests from the admin console to copy data."""

  SUFFIX = 'copy.do'

  COPY_HANDLER = (
      'google.appengine.ext.datastore_admin.copy_handler.CopyEntity.map')
  INPUT_READER = (
      'google.appengine.ext.mapreduce.input_readers.ConsistentKeyReader')
  MAPREDUCE_DETAIL = utils.config.MAPREDUCE_PATH + '/detail?mapreduce_id='

  def get(self):
    """Handler for get requests to datastore_admin/copy.do.

    Status of executed jobs is displayed.
    """
    jobs = self.request.get('job', allow_multiple=True)
    error = self.request.get('error', '')
    xsrf_error = self.request.get('xsrf_error', '')

    template_params = {
        'job_list': jobs,
        'mapreduce_detail': self.MAPREDUCE_DETAIL,
        'error': error,
        'xsrf_error': xsrf_error,
    }
    utils.RenderToResponse(self, 'do_copy.html', template_params)

  def post(self):
    """Handler for post requests to datastore_admin/copy.do.

    Jobs are executed and user is redirected to the get handler.
    """
    namespace = self.request.get('namespace')
    kinds = self.request.get('kind', allow_multiple=True)
    (namespace_str, kinds_str) = utils.GetPrintableStrs(namespace, kinds)
    token = self.request.get('xsrf_token')
    remote_url = self.request.get('remote_url')
    extra_header = self.request.get('extra_header')

    jobs = []
    if not remote_url:
      parameters = [('error', 'Unspecified remote URL.')]
    elif not utils.ValidateXsrfToken(token, XSRF_ACTION):
      parameters = [('xsrf_error', '1')]
    else:
      try:


        if extra_header:
          extra_headers = dict([extra_header.split(':', 1)])
        else:
          extra_headers = None
        target_app = remote_api_put_stub.get_remote_appid(remote_url,
                                                          extra_headers)
        op = utils.StartOperation(
            'Copying %s%s to %s' % (kinds_str, namespace_str, target_app))
        name_template = 'Copy all %(kind)s objects%(namespace)s'
        mapper_params = {
            'target_app': target_app,
            'remote_url': remote_url,
            'extra_header': extra_header,
        }
        jobs = utils.RunMapForKinds(
            op,
            kinds,
            name_template,
            self.COPY_HANDLER,
            self.INPUT_READER,
            mapper_params)

        error = ''


      except Exception, e:
        logging.exception('Handling exception.')
        error = self._HandleException(e)

      parameters = [('job', job) for job in jobs]
      if error:
        parameters.append(('error', error))

    query = urllib.urlencode(parameters)
    self.redirect('%s/%s?%s' % (utils.config.BASE_PATH, self.SUFFIX, query))

  def _HandleException(self, e):
    """Make exception handling overrideable by tests.

    In normal cases, return only the error string; do not fail to render the
    page for user.
    """
    return str(e)


class AllocateMaxIdPool(object):
  """Mapper pool to keep track of all allocated ids.

  Runs allocate_ids rpcs when flushed.

  This code uses the knowloedge of allocate_id implementation detail.
  Though we don't plan to change allocate_id logic, we don't really
  want to depend on it either. We are using this details here to implement
  batch-style remote allocate_ids.
  """

  def __init__(self, app_id):
    self.app_id = app_id

    self.key_path_to_max_id = {}

  def allocate_max_id(self, key):
    """Record the key to allocate max id.

    Args:
      key: Datastore key.
    """
    path = key.to_path()
    if not isinstance(path[-1], (int, long)):

      return
    if len(path) == 2:


      max_id = path[-1]
      path_tuple = (path[0], 1)
      self.key_path_to_max_id[path_tuple] = max(
          max_id, self.key_path_to_max_id.get(path_tuple, 0))
    else:


      max_id = 0
      for path_element in path[2:]:
        if isinstance(path_element, (int, long)):
          max_id = max(max_id, path_element)
      path_tuple = (path[0], path[1], 'Foo', 1)
      self.key_path_to_max_id[path_tuple] = max(
          max_id, self.key_path_to_max_id.get(path_tuple, 0))

  def flush(self):
    for path, maxid in self.key_path_to_max_id.items():
      db.allocate_id_range(db.Key.from_path(_app=self.app_id, *list(path)),
                           1, maxid)
    self.key_path_to_max_id = {}


class AllocateMaxId(operation.Operation):
  """Mapper operation to allocate max id."""

  def __init__(self, key, app_id):
    self.key = key
    self.app_id = app_id
    self.pool_id = 'allocate_max_id_%s_pool' % self.app_id

  def __call__(self, ctx):
    pool = ctx.get_pool(self.pool_id)
    if not pool:
      pool = AllocateMaxIdPool(self.app_id)
      ctx.register_pool(self.pool_id, pool)
    pool.allocate_max_id(self.key)




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


  FixKey(entity_proto.mutable_key())

  FixPropertyList(entity_proto.property_list())
  FixPropertyList(entity_proto.raw_property_list())



def KindPathFromKey(key):
  """Return kinds path as '/'-delimited string for a particular key."""
  path = key.to_path()
  kinds = []
  is_kind = True
  for item in path:
    if is_kind:
      kinds.append(item)
    is_kind = not is_kind
  kind_path = '/'.join(kinds)
  return kind_path


def get_mapper_params():
  """Return current mapreduce mapper params. Easily stubbed out for testing."""
  return context.get().mapreduce_spec.mapper.params


class CopyEntity(object):
  """A class which contains a map handler to copy entities remotely.

  The class manages the connection.
  """

  def __init__(self):
    self.remote_api_stub_initialized = False

  def setup_stub(self):
    """Set up the remote API stub."""
    if self.remote_api_stub_initialized:
      return
    params = get_mapper_params()
    if 'extra_header' in params and params['extra_header']:

      extra_headers = dict([params['extra_header'].split(':', 1)])
    else:
      extra_headers = {}

    remote_api_put_stub.configure_remote_put(params['remote_url'],
                                             params['target_app'],
                                             extra_headers)

    self.remote_api_stub_initialized = True

  def map(self, key):
    """Copy data map handler.

    Args:
      key: Datastore entity key to copy.

    Yields:
      A db operation to store the entity in the target app.
      A counter operation incrementing the count for the entity kind.
    """
    if not self.remote_api_stub_initialized:
      self.setup_stub()

    mapper_params = get_mapper_params()
    target_app = mapper_params['target_app']

    if isinstance(key, datastore.Entity):

      entity = key
      key = entity.key()
    else:
      entity = datastore.Get(key)
    entity_proto = entity._ToPb()
    FixKeys(entity_proto, target_app)
    target_entity = datastore.Entity._FromPb(entity_proto)

    yield operation.db.Put(target_entity)
    yield AllocateMaxId(key, target_app)
    yield operation.counters.Increment(KindPathFromKey(key))


def handlers_list(base_path):
  return [
      (r'%s/%s' % (base_path, ConfirmCopyHandler.SUFFIX), ConfirmCopyHandler),
      (r'%s/%s' % (base_path, DoCopyHandler.SUFFIX), DoCopyHandler),
      ]
