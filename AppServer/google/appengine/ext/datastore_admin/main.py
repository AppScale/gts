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



import logging
import operator
import os

from google.appengine.api import app_identity
from google.appengine.api import datastore_errors
from google.appengine.api import users
from google.appengine.ext import deferred
import webapp2 as webapp
from google.appengine.ext.db import stats
from google.appengine.ext.webapp import util
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext.datastore_admin import backup_handler
from google.appengine.ext.datastore_admin import config
from google.appengine.ext.datastore_admin import delete_handler
from google.appengine.ext.datastore_admin import utils






ENTITY_ACTIONS = {
    'Delete Entities': delete_handler.ConfirmDeleteHandler.Render,
    'Backup Entities': backup_handler.ConfirmBackupHandler.Render,
}


BACKUP_ACTIONS = {
    'Delete': backup_handler.ConfirmDeleteBackupHandler.Render,
    'Restore': backup_handler.ConfirmRestoreFromBackupHandler.Render,
    'Info': backup_handler.BackupInformationHandler.Render,
}

PENDING_BACKUP_ACTIONS = {
    'Abort': backup_handler.ConfirmAbortBackupHandler.Render,
    'Info': backup_handler.BackupInformationHandler.Render,
}

GET_ACTIONS = ENTITY_ACTIONS.copy()
GET_ACTIONS.update(BACKUP_ACTIONS)
GET_ACTIONS.update(PENDING_BACKUP_ACTIONS)
GET_ACTIONS.update({'Import Backup Information':
                    backup_handler.ConfirmBackupImportHandler.Render})


def _GetDatastoreStats(kinds_list, use_stats_kinds=False):
  """Retrieves stats for kinds.

  Args:
    kinds_list: List of known kinds.
    use_stats_kinds: If stats are available, kinds_list will be ignored and
      all kinds found in stats will be used instead.

  Returns:
    timestamp: records time that statistics were last updated.
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
        and (use_stats_kinds or kind_ent.kind_name in kinds_list)
        and kind_ent.count > 0):
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
  entity_bytes = kind_ent.entity_bytes
  total_bytes = kind_ent.bytes
  average_bytes = entity_bytes / count
  return {'kind_name': kind_ent.kind_name,
          'count': utils.FormatThousands(kind_ent.count),
          'entity_bytes_str': utils.GetPrettyBytes(entity_bytes),
          'entity_bytes': entity_bytes,
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
    more_kinds = False
    try:
      kinds, more_kinds = utils.GetKinds()
      if not kinds:
        use_stats_kinds = True
        logging.warning('Found no kinds. Using datastore stats instead.')
    except datastore_errors.Error, e:
      logging.exception(e)
      use_stats_kinds = True

    last_stats_update, kind_stats = _GetDatastoreStats(
        kinds, use_stats_kinds=use_stats_kinds)

    template_params = {
        'run_as_a_service': self.request.get('run_as_a_service'),
        'datastore_admin_home': utils.GenerateHomeUrl(None),
        'offer_service': (self.request.get('service') and not
                          self.request.get('run_as_a_service')),
        'kind_stats': kind_stats,
        'more_kinds': more_kinds,
        'last_stats_update': last_stats_update,
        'app_id': self.request.get('app_id'),
        'hosting_app_id': app_identity.get_application_id(),
        'has_namespace': self.request.get('namespace', None) is not None,
        'namespace': self.request.get('namespace'),
        'action_list': sorted(ENTITY_ACTIONS.keys()),
        'backup_action_list': sorted(BACKUP_ACTIONS.keys()),
        'pending_backup_action_list': sorted(PENDING_BACKUP_ACTIONS.keys()),
        'error': error,
        'completed_operations': self.GetOperations(active=False),
        'active_operations': self.GetOperations(active=True),
        'pending_backups': self.GetPendingBackups(),
        'backups': self.GetBackups(),
        'map_reduce_path': config.MAPREDUCE_PATH + '/detail',
        'service_accounts': utils.get_service_account_names()
    }
    utils.RenderToResponse(self, 'list_actions.html', template_params)

  def RouteAction(self, action_dict):
    action = self.request.get('action')
    if not action:
      self.ListActions(error=self.request.get('error', None))
    elif action not in action_dict:
      error = '%s is not a valid action.' % action
      self.ListActions(error=error)
    else:
      action_dict[action](self)

  def get(self):
    self.RouteAction(GET_ACTIONS)

  def post(self):
    self.RouteAction(GET_ACTIONS)

  def GetOperations(self, active=False, limit=100):
    """Obtain a list of operation, ordered by last_updated."""
    query = utils.DatastoreAdminOperation.all()
    if active:
      query.filter('status = ', utils.DatastoreAdminOperation.STATUS_ACTIVE)
    else:
      query.filter('status IN ', [
          utils.DatastoreAdminOperation.STATUS_COMPLETED,
          utils.DatastoreAdminOperation.STATUS_FAILED,
          utils.DatastoreAdminOperation.STATUS_ABORTED])
    operations = query.fetch(max(10000, limit) if limit else 1000)
    operations = sorted(operations, key=operator.attrgetter('last_updated'),
                        reverse=True)
    return operations[:limit]

  def GetBackups(self, limit=100, deadline=10):
    """Obtain a list of backups.

    Args:
      limit: maximum number of backup records to retrieve.
      deadline: maximum number of seconds to spend getting backups.

    Returns:
      List of backups, sorted in reverse order by completion time.
    """
    backups = []
    query = backup_handler.BackupInformation.all()
    query.filter('complete_time > ', 0)
    query.order('-complete_time')
    try:
      backups.extend(query.run(deadline=deadline, limit=limit))
    except (datastore_errors.Timeout, apiproxy_errors.DeadlineExceededError):
      logging.warning('Failed to retrieve all backups within deadline.')
    return backups

  def GetPendingBackups(self, limit=100):
    """Obtain a list of pending backups."""
    query = backup_handler.BackupInformation.all()
    query.filter('complete_time = ', None)
    backups = query.fetch(max(10000, limit) if limit else 1000)
    backups = sorted(backups, key=operator.attrgetter('start_time'),
                     reverse=True)
    return backups[:limit]


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
    relative_path = self.request.path.split(config.BASE_PATH + '/')[1]
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


class LoginRequiredHandler(webapp.RequestHandler):
  """Handle federated login identity selector page."""

  def get(self):
    target = self.request.get('continue')
    if not target:
      self.error(400)
      return


    login_url = users.create_login_url(target)
    self.redirect(login_url)


def CreateApplication():
  """Create new WSGIApplication and register all handlers.

  Returns:
    an instance of webapp.WSGIApplication with all mapreduce handlers
    registered.
  """
  return webapp.WSGIApplication(
      backup_handler.handlers_list(config.BASE_PATH) +
      [(r'%s/%s' % (config.BASE_PATH,
                    delete_handler.ConfirmDeleteHandler.SUFFIX),
        delete_handler.ConfirmDeleteHandler),
       (r'%s/%s' % (config.BASE_PATH, delete_handler.DoDeleteHandler.SUFFIX),
        delete_handler.DoDeleteHandler),
       (r'%s/%s' % (config.BASE_PATH, utils.MapreduceDoneHandler.SUFFIX),
        utils.MapreduceDoneHandler),
       (config.DEFERRED_PATH, deferred.TaskHandler),
       (r'%s/static.*' % config.BASE_PATH, StaticResourceHandler),
       (r'/_ah/login_required', LoginRequiredHandler),
       (r'.*', RouteByActionHandler)])


APP = CreateApplication()


def main():
  util.run_wsgi_app(APP)


if __name__ == '__main__':
  main()
