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




"""Main module for datastore admin receiver.

To use, add this to app.yaml:
  builtins:
  - datastore_admin: on
"""


import os

from google.appengine.api import datastore_errors
from google.appengine.ext import webapp
from google.appengine.ext.datastore_admin import copy_handler
from google.appengine.ext.datastore_admin import delete_handler
from google.appengine.ext.datastore_admin import utils
from google.appengine.ext.db import stats
from google.appengine.ext.db import metadata
from google.appengine.ext.webapp import util





GET_ACTIONS = {
    'Copy to Another App': copy_handler.ConfirmCopyHandler.Render,
    'Delete Entities': delete_handler.ConfirmDeleteHandler.Render,
}


def _GetDatastoreStats(kinds_list, use_stats_kinds=False):
  """Retrieves stats for kinds.

  Args:
    kinds_list: List of known kinds.
    use_stats_kinds: If stats are available, kinds_list will be ignored and
      all kinds found in stats will be used instead.

  Returns:
    timestamp: records time that statistics were last updated.
    global_size: total size of all known kinds.
    kind_dict: dictionary of kind objects with the following members:
    - kind_name: the name of this kind.
    - count: number of known entities of this type.
    - total_bytes_str: total bytes for this kind as a string.
    - average_bytes_str: average bytes per entity as a string.
  """
  global_stat = stats.GlobalStat.all().fetch(1)
  if not global_stat:
    return _KindsListToTuple(kinds_list)

  global_ts = global_stat[0].timestamp

  kind_stats = stats.KindStat.all().filter('timestamp =', global_ts).fetch(1000)
  if not kind_stats:
    return _KindsListToTuple(kinds_list)

  results = {}
  for kind_ent in kind_stats:



    if (not kind_ent.kind_name.startswith('__')
        and (use_stats_kinds or kind_ent.kind_name in kinds_list)):
      results[kind_ent.kind_name] = _PresentatableKindStats(kind_ent)

  utils.CacheStats(results.values())



  for kind_str in kinds_list or []:
    if kind_str not in results:
      results[kind_str] = {'kind_name': kind_str}

  return (global_ts,
          sorted(results.values(), key=lambda x: x['kind_name']))


def _KindsListToTuple(kinds_list):
  """Build default tuple when no datastore statistics are available. """
  return '', [{'kind_name': kind} for kind in sorted(kinds_list)]


def _PresentatableKindStats(kind_ent):
  """Generate dict of presentable values for template."""
  count = kind_ent.count
  total_bytes = kind_ent.bytes
  average_bytes = total_bytes / count
  return {'kind_name': kind_ent.kind_name,
          'count': utils.FormatThousands(kind_ent.count),
          'total_bytes_str': utils.GetPrettyBytes(total_bytes),
          'total_bytes': total_bytes,
          'average_bytes_str': utils.GetPrettyBytes(average_bytes),
         }


class RouteByActionHandler(webapp.RequestHandler):
  """Route to the appropriate handler based on the action parameter."""

  def ListActions(self, error=None):
    """Handler for get requests to datastore_admin/confirm_delete."""
    use_stats_kinds = False
    kinds = []
    try:
      kinds = self.GetKinds()
      if not kinds:
        use_stats_kinds = True
    except datastore_errors.Error:
      use_stats_kinds = True

    last_stats_update, kind_stats = _GetDatastoreStats(
        kinds, use_stats_kinds=use_stats_kinds)

    template_params = {
        'kind_stats': kind_stats,
        'cancel_url': self.request.path + '?' + self.request.query_string,
        'last_stats_update': last_stats_update,
        'app_id': self.request.get('app_id'),
        'namespace': self.request.get('namespace'),
        'action_list': sorted(GET_ACTIONS.keys()),
        'error': error,
        'operations': utils.DatastoreAdminOperation.all().fetch(100),
    }
    utils.RenderToResponse(self, 'list_actions.html', template_params)

  def RouteAction(self, action_dict):
    action = self.request.get('action')
    if not action:
      self.ListActions()
    elif action not in action_dict:
      error = '%s is not a valid action.' % action
      self.ListActions(error=error)
    else:
      action_dict[action](self)

  def get(self):
    self.RouteAction(GET_ACTIONS)

  def post(self):
    self.RouteAction(GET_ACTIONS)

  def GetKinds(self):
    """Obtain list of all entity kinds from the datastore."""
    kinds = metadata.Kind.all().fetch(99999999)
    kind_names = []
    for kind in kinds:
      kind_name = kind.kind_name
      if (kind_name.startswith('__') or
          kind_name == utils.DatastoreAdminOperation.kind()):
        continue
      kind_names.append(kind_name)
    return kind_names


class StaticResourceHandler(webapp.RequestHandler):
  """Read static files from disk."""






  _BASE_FILE_PATH = os.path.dirname(__file__)

  _RESOURCE_MAP = {
      'static/js/compiled.js': 'text/javascript',
      'static/css/compiled.css': 'text/css',
      'static/img/help.gif': 'image/gif',
      'static/img/tip.png': 'image/png',
      'static/img/icn/icn-warning.gif': 'image/gif',
  }

  def get(self):
    relative_path = self.request.path.split(utils.config.BASE_PATH + '/')[1]
    if relative_path not in self._RESOURCE_MAP:
      self.response.set_status(404)
      self.response.out.write('Resource not found.')
      return

    path = os.path.join(self._BASE_FILE_PATH, relative_path)
    self.response.headers['Cache-Control'] = 'public; max-age=300'
    self.response.headers['Content-Type'] = self._RESOURCE_MAP[relative_path]
    if relative_path == 'static/css/compiled.css':


      self.response.out.write(
          open(path).read().replace('url(/img/', 'url(../img/'))
    else:
      self.response.out.write(open(path).read())


def CreateApplication():
  """Create new WSGIApplication and register all handlers.

  Returns:
    an instance of webapp.WSGIApplication with all mapreduce handlers
    registered.
  """
  return webapp.WSGIApplication([
      (r'%s/%s' % (utils.config.BASE_PATH,
                   delete_handler.ConfirmDeleteHandler.SUFFIX),
       delete_handler.ConfirmDeleteHandler),
      (r'%s/%s' % (utils.config.BASE_PATH,
                   delete_handler.DoDeleteHandler.SUFFIX),
       delete_handler.DoDeleteHandler),
      (r'%s/%s' % (utils.config.BASE_PATH,
                   utils.MapreduceDoneHandler.SUFFIX),
       utils.MapreduceDoneHandler),
      ] + copy_handler.handlers_list(utils.config.BASE_PATH) + [
      (r'%s/static.*' % utils.config.BASE_PATH, StaticResourceHandler),
      (r'.*', RouteByActionHandler),
      ])


APP = CreateApplication()


def main():
  util.run_wsgi_app(APP)


if __name__ == '__main__':
  main()
