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




"""Simple datastore view and interactive console, for use in dev_appserver."""









import cgi
import collections
import csv
import cStringIO
import datetime
import decimal
import logging
import math
import mimetypes
import os
import os.path
import pickle
import pprint
import random
import sys
import time
import traceback
import types
import urllib
import urlparse




try:
  from google.appengine.cron import groctimespecification
  from google.appengine.api import croninfo
except ImportError:
  HAVE_CRON = False
else:
  HAVE_CRON = True

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import backends
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import memcache
from google.appengine.api import search
from google.appengine.api import taskqueue
from google.appengine.api import users
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.datastore import datastore_stats_generator
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.db import metadata
from google.appengine.ext.webapp import _template
from google.appengine.ext.webapp import util
from google.appengine.runtime import apiproxy_errors


_DEBUG = True


QUEUE_MODE = taskqueue_service_pb.TaskQueueMode


_UsecToSec = taskqueue_stub._UsecToSec
_FormatEta = taskqueue_stub._FormatEta
_EtaDelta = taskqueue_stub._EtaDelta

_DATASTORE_CACHING_WARNING = (
    'If your app uses memcache to cache entities (e.g. uses NDB), you may see '
    'stale results unless you flush memcache.')



DEFAULT_MAX_DATASTORE_VIEWER_COLUMNS = 100




class _AhAdminXsrfToken_(db.Model):
  """Model class used to persist the XSRF token."""

  XSRF_KEY_NAME = '_XSRF_'

  xsrf_token = db.StringProperty()


def get_xsrf_token():
  """Return the XSRF token.

  This is read from the datastore.  If no token is present in the
  datastore, we create a random token and insert it.
  """
  entity = _AhAdminXsrfToken_.get_by_key_name(_AhAdminXsrfToken_.XSRF_KEY_NAME)
  if not entity:
    randints = ['%08x' % (random.randrange(-2**31, 2**31-1) & (2**32-1))
                for i in range(6)]
    xsrf_token = '_'.join(randints)
    entity = _AhAdminXsrfToken_(key_name=_AhAdminXsrfToken_.XSRF_KEY_NAME,
                                xsrf_token=xsrf_token)
    entity.put()
  return entity.xsrf_token


def xsrf_required(method):
  """Decorator to protect post() handlers against XSRF attacks."""
  def xsrf_required_decorator(self):
    expected_token = get_xsrf_token()
    actual_token = self.request.get('xsrf_token')
    if actual_token != expected_token:
      self.response.set_status(403, 'Invalid XSRF token')
      self.response.out.write('<h1>Invalid XSRF token</h1>\n' +
                              '<p>Please reload the form page</n>\n' +
                              ' '*512)
    else:
      method(self)
  return xsrf_required_decorator


def ustr(value):
  """Like str(), but UTF-8-encodes Unicode instead of failing."""
  try:
    return str(value)
  except UnicodeError:
    return unicode(value).encode('UTF-8')


def urepr(value):
  """Like repr(), but UTF-8-encodes Unicode inside a list."""
  if isinstance(value, list):
    return '[' + ', '.join(map(urepr, value)) + ']'
  if isinstance(value, unicode):
    return ('u"' +
            value.encode('utf-8').replace('\"', '\\"').replace('\\', '\\\\') +
            '"')
  return repr(value)


def TruncateValue(value):
  """Truncates potentially very long string to a fixed maximum length."""
  value = ustr(value)
  if len(value) > 32:
    return value[:32] + '...'
  return value


class Document(object):
  """Simple representation of document."""

  def __init__(self, doc_id):
    self.doc_id = doc_id
    self.fields = {}


class ImageHandler(webapp.RequestHandler):
  """Serves a static image.

  This exists because we don't want to burden the user with specifying
  a static file handler for the image resources used by the admin tool.
  """

  PATH = '/images/.*'

  def get(self):
    image_name = os.path.basename(self.request.path)
    content_type, encoding = mimetypes.guess_type(image_name)
    if not content_type or not content_type.startswith('image/'):
      logging.debug('image_name=%r, content_type=%r, encoding=%r',
                    image_name, content_type, encoding)
      self.error(404)
      return
    directory = os.path.dirname(__file__)
    path = os.path.join(directory, 'templates', 'images', image_name)
    try:
      image_stream = open(path, 'rb')
    except IOError, e:
      logging.error('Cannot open image %s: %s', image_name, e)
      self.error(404)
      return
    try:
      image_data = image_stream.read()
    finally:
      image_stream.close()
    self.response.headers['Content-Type'] = content_type
    self.response.out.write(image_data)


class BaseRequestHandler(webapp.RequestHandler):
  """Supplies a common template generation function.

  When you call generate(), we augment the template variables supplied with
  the current user in the 'user' variable and the current webapp request
  in the 'request' variable.
  """

  def generate(self, template_name, template_values={}):
    base_path = self.base_path()
    values = {
        'application_name': self.request.environ['APPLICATION_ID'],
        'sdk_version': self.request.environ.get('SDK_VERSION', 'Unknown'),
        'user': users.get_current_user(),
        'request': self.request,
        'home_path': base_path + DefaultPageHandler.PATH,
        'datastore_path': base_path + DatastoreQueryHandler.PATH,
        'datastore_indexes': base_path + DatastoreGetIndexesHandler.PATH,
        'datastore_edit_path': base_path + DatastoreEditHandler.PATH,
        'datastore_batch_edit_path': base_path + DatastoreBatchEditHandler.PATH,
        'datastore_stats_path': base_path + DatastoreStatsHandler.PATH,
        'interactive_path': base_path + InteractivePageHandler.PATH,
        'interactive_execute_path': base_path + InteractiveExecuteHandler.PATH,
        'memcache_path': base_path + MemcachePageHandler.PATH,
        'queues_path': base_path + QueuesPageHandler.PATH,
        'search_path': base_path + SearchIndexesListHandler.PATH,
        'search_index_path': base_path + SearchIndexHandler.PATH,
        'search_document_path': base_path + SearchDocumentHandler.PATH,
        'search_batch_delete_path': base_path + SearchBatchDeleteHandler.PATH,
        'tasks_path': base_path + TasksPageHandler.PATH,
        'xmpp_path': base_path + XMPPPageHandler.PATH,
        'inboundmail_path': base_path + InboundMailPageHandler.PATH,
        'backends_path': base_path + BackendsPageHandler.PATH,
        'xsrf_token': get_xsrf_token(),
      }
    if HAVE_CRON:
      values['cron_path'] = base_path + CronPageHandler.PATH
    if 'X-AppEngine-Datastore-Admin-Enabled' in self.request.headers:
      values['datastore_admin_path'] = base_path + DatastoreAdminHandler.PATH

    values['interactive_console'] = self.interactive_console_enabled()

    values.update(template_values)
    directory = os.path.dirname(__file__)
    path = os.path.join(directory, os.path.join('templates', template_name))
    self.response.out.write(_template.render(path, values, debug=_DEBUG))

  def base_path(self):
    """Returns the base path of this admin app, which is chosen by the user.

    The user specifies which paths map to this application in their app.cfg.
    You can get that base path with this method. Combine with the constant
    paths specified by the classes to construct URLs.
    """
    path = self.__class__.PATH
    return self.request.path[:-len(path)]

  def filter_url(self, args):
    """Filters the current URL to only have the given list of arguments.

    For example, if your URL is /search?q=foo&num=100&start=10, then

       self.filter_url(['start', 'num']) => /search?num=100&start=10
       self.filter_url(['q']) => /search?q=10
       self.filter_url(['random']) => /search?

    """
    queries = []
    for arg in args:
      value = self.request.get(arg)
      if value:
        queries.append(arg + '=' + urllib.quote_plus(
            ustr(self.request.get(arg))))
    return self.request.path + '?' + '&'.join(queries)

  def in_production(self):
    """Detects if app is running in production.

    Returns a boolean.
    """
    server_software = os.getenv('SERVER_SOFTWARE')
    if server_software is None:
      return False
    return not server_software.startswith('Development')

  def interactive_console_enabled(self):
    return 'True' == self.request.headers.get(
        'X-AppEngine-Interactive-Console-Enabled', 'True')


class DefaultPageHandler(BaseRequestHandler):
  """Redirects to the Datastore application by default."""

  PATH = '/'

  def get(self):
    if self.request.path.endswith('/'):
      base = self.request.path[:-1]
    else:
      base = self.request.path
    self.redirect(base + DatastoreQueryHandler.PATH)


class DatastoreAdminHandler(BaseRequestHandler):
  """Loads the Datastore Admin handler in an iframe."""
  PATH = '/datastore_admin'

  def get(self):
    self.generate('datastore_admin_frame.html')


class InteractivePageHandler(BaseRequestHandler):
  """Shows our interactive console HTML."""
  PATH = '/interactive'

  def get(self):
    self.generate('interactive.html')


class InteractiveExecuteHandler(BaseRequestHandler):
  """Executes the Python code submitted in a POST within this context.

  For obvious reasons, this should only be available to administrators
  of the applications.
  """

  PATH = InteractivePageHandler.PATH + '/execute'

  @xsrf_required
  def post(self):
    if self.interactive_console_enabled():

      save_stdout = sys.stdout
      results_io = cStringIO.StringIO()
      try:
        sys.stdout = results_io


        code = self.request.get('code')
        code = code.replace("\r\n", "\n")

        try:
          compiled_code = compile(code, '<string>', 'exec')
          exec(compiled_code, globals())
        except Exception, e:
          traceback.print_exc(file=results_io)
      finally:
        sys.stdout = save_stdout

      results = results_io.getvalue()
    else:
      results = """The interactive console has been disabled for security
because the dev_appserver is listening on a non-default address.
If you would like to re-enable the console, invoke dev_appserver
with the --enable_console argument.

See https://developers.google.com/appengine/docs/python/tools/devserver#The_Interactive_Console
for more information."""
    self.generate('interactive-output.html', {'output': results})


class CronPageHandler(BaseRequestHandler):
  """Shows information about configured cron jobs in this application."""
  PATH = '/cron'

  def get(self, now=None):
    """Shows template displaying the configured cron jobs."""
    if not now:
      now = datetime.datetime.utcnow()
    values = {'request': self.request}
    cron_info = _ParseCronYaml()
    values['cronjobs'] = []
    values['now'] = str(now)
    if cron_info and cron_info.cron:
      for entry in cron_info.cron:
        job = {}
        values['cronjobs'].append(job)
        if entry.description:
          job['description'] = entry.description
        else:
          job['description'] = '(no description)'
        if entry.timezone:
          job['timezone'] = entry.timezone
        job['url'] = entry.url
        job['schedule'] = entry.schedule


        schedule = groctimespecification.GrocTimeSpecification(entry.schedule)

        matches = schedule.GetMatches(now, 3)
        job['times'] = []
        for match in matches:
          job['times'].append({'runtime': match.strftime('%Y-%m-%d %H:%M:%SZ'),
                               'difference': str(match - now)})
    self.generate('cron.html', values)


class XMPPPageHandler(BaseRequestHandler):
  """Tests XMPP requests."""
  PATH = '/xmpp'

  def get(self):
    """Shows template displaying the XMPP."""

    xmpp_configured = True
    values = {
        'xmpp_configured': xmpp_configured,
        'request': self.request
        }
    self.generate('xmpp.html', values)


class InboundMailPageHandler(BaseRequestHandler):
  """Tests Mail requests."""
  PATH = '/inboundmail'

  def get(self):
    """Shows template displaying the Inbound Mail form."""

    inboundmail_configured = True
    values = {
      'inboundmail_configured': inboundmail_configured,
      'request': self.request
    }
    self.generate('inboundmail.html', values)


class TaskQueueHelper(object):
  """Taskqueue rpc wrapper."""

  def _make_sync_call(self, rpc_name, request):
    """Make a synchronous taskqueue api call.

    Args:
      rpc_name: The name of the rpc to call.
      request: The protocol buffer to be used as the request.

    Returns:
      The rpc response. This is an instance of the correct response protocol
      buffer for the request 'rpc_name'.
    """
    response = getattr(taskqueue_service_pb, 'TaskQueue%sResponse' % rpc_name)()
    apiproxy_stub_map.MakeSyncCall('taskqueue', rpc_name, request, response)
    return response

  def get_queues(self, now):
    """Get a list of queue in the application.

    Args:
      now: The current time. A datetime.datetime object with a utc timezone.

    Returns:
      A list of queue dicts corresponding to the tasks for this application.
    """
    request = taskqueue_service_pb.TaskQueueFetchQueuesRequest()
    request.set_max_rows(1000)
    response = self._make_sync_call('FetchQueues', request)

    queue_stats_request = taskqueue_service_pb.TaskQueueFetchQueueStatsRequest()
    queue_stats_request.set_max_num_tasks(0)

    queues = []
    for queue_proto in response.queue_list():
      queue = {'name': queue_proto.queue_name(),
               'mode': queue_proto.mode(),
               'rate': queue_proto.user_specified_rate(),
               'bucket_size': queue_proto.bucket_capacity()}
      queues.append(queue)
      queue_stats_request.queue_name_list().append(queue_proto.queue_name())

    queue_stats_response = self._make_sync_call(
        'FetchQueueStats', queue_stats_request)
    for queue, queue_stats in zip(queues,
                                  queue_stats_response.queuestats_list()):
      queue['tasks_in_queue'] = queue_stats.num_tasks()
      if queue_stats.oldest_eta_usec() != -1:
        queue['oldest_task'] = _FormatEta(queue_stats.oldest_eta_usec())
        queue['eta_delta'] = _EtaDelta(queue_stats.oldest_eta_usec(), now)
    return queues

  def get_number_tasks_in_queue(self, queue_name):
    """Returns the number of tasks in the named queue.

    Args:
      queue_name: The name of the queue.

    Returns:
      The number of tasks in the queue.
    """
    queue_stats_request = taskqueue_service_pb.TaskQueueFetchQueueStatsRequest()
    queue_stats_request.set_max_num_tasks(0)
    queue_stats_request.add_queue_name(queue_name)
    queue_stats_response = self._make_sync_call(
        'FetchQueueStats', queue_stats_request)

    assert queue_stats_response.queuestats_size() == 1
    return queue_stats_response.queuestats(0).num_tasks()

  def get_tasks(self,
                now,
                queue_name,
                start_eta_usec,
                start_task_name,
                num_tasks):
    """Fetch the specified tasks from taskqueue.

    Note: This only searchs by eta.

    Args:
      now: The current time. This is used to calculate the EtaFromNow. Must be a
          datetime.datetime in the utc timezone.
      queue_name: The queue to search for tasks.
      start_eta_usec: The earliest eta to return.
      start_task_name: For tasks with the same eta_usec, this is used as a tie
          breaker.
      num_tasks: The maximum number of tasks to return.

    Returns:
      A list of task dicts (as returned by
          taskqueue_stub.QueryTasksResponseToDict).
    """
    request = taskqueue_service_pb.TaskQueueQueryTasksRequest()
    request.set_queue_name(queue_name)
    request.set_start_task_name(start_task_name)
    request.set_start_eta_usec(start_eta_usec)
    request.set_max_rows(num_tasks)

    response = self._make_sync_call('QueryTasks', request)
    tasks = []
    for task in response.task_list():
      tasks.append(taskqueue_stub.QueryTasksResponseToDict(
          queue_name, task, now))
    return tasks

  def delete_task(self, queue_name, task_name):
    """Delete the named task.

    Args:
      queue_name: The name of the queue.
      task_name: The name of the task.
    """
    request = taskqueue_service_pb.TaskQueueDeleteRequest()
    request.set_queue_name(queue_name)
    request.task_name_list().append(task_name)

    self._make_sync_call('Delete', request)

  def purge_queue(self, queue_name):
    """Purge the named queue.

    Args:
      queue_name: the name of the queue.
    """
    request = taskqueue_service_pb.TaskQueuePurgeQueueRequest()
    request.set_queue_name(queue_name)
    self._make_sync_call('PurgeQueue', request)


class QueueBatch(object):
  """Collection of push queues or pull queues."""

  def __init__(self, title, run_manually, rate_limited, contents):
    self.title = title
    self.run_manually = run_manually
    self.rate_limited = rate_limited
    self.contents = contents

  def __eq__(self, other):
    if type(self) is not type(other):
      return NotImplemented
    return (self.title == other.title and
            self.run_manually == other.run_manually and
            self.rate_limited == other.rate_limited and
            self.contents == other.contents)

  def __iter__(self):
    return self.contents.__iter__()


class QueuesPageHandler(BaseRequestHandler):
  """Shows information about configured (and default) task queues."""
  PATH = '/queues'

  def __init__(self, *args, **kwargs):
    super(QueuesPageHandler, self).__init__(*args, **kwargs)
    self.helper = TaskQueueHelper()

  def get(self):
    """Shows template displaying the configured task queues."""

    def is_push_queue(queue):
      return queue['mode'] == QUEUE_MODE.PUSH

    def is_pull_queue(queue):
      return queue['mode'] == QUEUE_MODE.PULL

    now = datetime.datetime.utcnow()
    values = {}
    try:
      queues = self.helper.get_queues(now)
      push_queues = QueueBatch('Push Queues',
                               True,
                               True,
                               filter(is_push_queue, queues))
      pull_queues = QueueBatch('Pull Queues',
                               False,
                               False,
                               filter(is_pull_queue, queues))
      values['queueBatches'] = [push_queues, pull_queues]
    except apiproxy_errors.ApplicationError:


      logging.exception('Could not fetch list of queues.')
    self.generate('queues.html', values)

  @xsrf_required
  def post(self):
    """Handle modifying actions and/or redirect to GET page."""
    queue_name = self.request.get('queue')

    if self.request.get('action:purgequeue'):
      self.helper.purge_queue(queue_name)
    self.redirect(self.request.path_url)


class TasksPageHandler(BaseRequestHandler):
  """Shows information about a queue's tasks."""

  PATH = '/tasks'

  PAGE_SIZE = 20

  MAX_TASKS_TO_FETCH = 1000
  MIN_TASKS_TO_FETCH = 200

  def __init__(self, *args, **kwargs):
    super(TasksPageHandler, self).__init__(*args, **kwargs)
    self.helper = TaskQueueHelper()
    self.prev_page = None
    self.next_page = None
    self.this_page = None

  def parse_arguments(self):
    """Parse the arguments passed into the request and store them on self."""
    self.queue_name = self.request.get('queue')
    self.start_name = self.request.get('start_name', '')
    self.start_eta = int(self.request.get('start_eta', '0'))
    self.per_page = int(self.request.get('per_page', self.PAGE_SIZE))
    self.page_no = int(self.request.get('page_no', '1'))
    assert self.per_page > 0

  def redirect_to_tasks(self, keep_offset=True):
    """Perform a redirect to the tasks page.

    Args:
      keep_offset: If true, will keep the 'start_eta',
        'start_name' and 'page_no' fields.
    """
    params = {'queue': self.queue_name, 'per_page': self.per_page}
    if keep_offset:
      params['start_name'] = self.start_name
      params['start_eta'] = self.start_eta
      params['page_no'] = self.page_no
    self.redirect('%s?%s' % (self.request.path, urllib.urlencode(params)))

  def _generate_page_params(self, page_dict):
    """Generate the params for a page link."""
    params = [
        ('queue', self.queue_name),
        ('start_eta', page_dict['start_eta']),
        ('start_name', page_dict['start_name']),
        ('per_page', self.per_page),
        ('page_no', page_dict['number']),
        ]
    return urllib.urlencode(params)

  def generate_page_dicts(self, start_tasks, end_tasks):
    """Generate the page dicts from a list of tasks.

    Args:
      tasks: A list of task dicts, sorted by eta.

    Returns:
      A list of page dicts containing the following keys: 'start_name',
      'start_eta', 'number', 'has_gap'.
    """
    page_map = {}

    for i, task in enumerate(start_tasks[::self.per_page]):
      page_no = i + 1
      page_map[page_no] = {
          'start_name': task['name'],
          'start_eta': task['eta_usec'],
          'number': page_no}

    if page_map and (page_no < self.page_no - 1):
      page_map[page_no]['has_gap'] = True


    for i, task in enumerate(end_tasks[::self.per_page]):
      page_no = self.page_no + i
      page_map[page_no] = {
          'start_name': task['name'],
          'start_eta': task['eta_usec'],
          'number': self.page_no + i}


    page_map[1] = {'start_name': '', 'start_eta': 0, 'number': 1}

    pages = sorted(sorted(page_map.values()), key=lambda page: page['number'])

    for page in pages:
      page['url'] = self._generate_page_params(page)


    self.this_page = page_map[self.page_no]
    if self.page_no - 1 in page_map:
      self.prev_page = page_map[self.page_no - 1]
    if self.page_no + 1 in page_map:
      self.next_page = page_map[self.page_no + 1]

    return pages

  def get(self):
    """Shows template displaying the queue's tasks."""
    self.parse_arguments()
    now = datetime.datetime.utcnow()


    tasks_to_fetch = min(self.MAX_TASKS_TO_FETCH,
                         max(self.MIN_TASKS_TO_FETCH, self.per_page * 10))

    try:
      tasks = self.helper.get_tasks(now, self.queue_name, self.start_eta,
                                    self.start_name, tasks_to_fetch)
    except apiproxy_errors.ApplicationError:


      logging.exception('Could not fetch list of tasks.')
      tasks = []

    if self.start_eta or self.start_name:
      if not tasks:


        self.redirect_to_tasks(keep_offset=False)
        return


      first_tasks = self.helper.get_tasks(now, self.queue_name, 0, '',
                                          tasks_to_fetch)
    else:
      first_tasks = []

    pages = self.generate_page_dicts(first_tasks, tasks)
    if len(tasks) == tasks_to_fetch:

      pages[-1]['has_gap'] = True
    tasks = tasks[:self.per_page]


    def is_this_push_queue(queue):
      return (queue['name'] == self.queue_name and
              queue['mode'] == QUEUE_MODE.PUSH)

    values = {
        'queue': self.queue_name,
        'per_page': self.per_page,
        'tasks': tasks,
        'prev_page': self.prev_page,
        'next_page': self.next_page,
        'this_page': self.this_page,
        'pages': pages,
        'page_no': self.page_no,
    }
    if any(filter(is_this_push_queue, self.helper.get_queues(now))):
      values['is_push_queue'] = 'true'

    self.generate('tasks.html', values)

  @xsrf_required
  def post(self):
    self.parse_arguments()
    self.task_name = self.request.get('task')

    if self.request.get('action:deletetask'):
      self.helper.delete_task(self.queue_name, self.task_name)

    self.redirect_to_tasks(keep_offset=True)


class BackendsPageHandler(BaseRequestHandler):
  """Shows information about an app's backends."""

  PATH = '/backends'

  def __init__(self, *args, **kwargs):
    super(BackendsPageHandler, self).__init__(*args, **kwargs)
    self.stub = apiproxy_stub_map.apiproxy.GetStub('system')

  def get(self):
    """Shows template displaying the app's backends or a single backend."""
    backend_name = self.request.get('backendName')
    if backend_name:
      return self.render_backend_page(backend_name)
    else:
      return self.render_backends_page()

  def render_backends_page(self):
    """Shows template displaying all the app's backends."""
    if hasattr(self.stub, 'get_backend_info'):
      backend_info = self.stub.get_backend_info() or []
    else:

      backend_info = []

    backend_list = []
    for backend in backend_info:
      backend_list.append({
          'name': backend.name,
          'instances': backend.instances,
          'instanceclass': backend.get_class() or 'B2',
          'address': backends.get_hostname(backend.name),
          'state': 'running',
          'options': backend.options,
      })

    values = {
      'request': self.request,
      'backends': backend_list,
      'backend_path': self.base_path() + self.PATH,
    }
    self.generate('backends.html', values)

  def get_backend_entry(self, backend_name):
    """Get the BackendEntry for a single backend."""
    if not hasattr(self.stub, 'get_backend_info'):
      return None

    backend_entries = self.stub.get_backend_info() or []
    for backend in backend_entries:
      if backend.name == backend_name:
        return backend
    return None

  def render_backend_page(self, backend_name):
    """Shows template displaying a single backend."""
    backend = self.get_backend_entry(backend_name)

    instances = []
    if backend:
      for i in range(backend.instances):
        instances.append({
            'id': i,
            'address': backends.get_hostname(backend_name, i),
            'state': 'running',
        })

    values = {
      'request': self.request,
      'backend_name': backend_name,
      'backend_path': self.base_path() + self.PATH,
      'instances': instances,
    }
    self.generate('backend.html', values)

  @xsrf_required
  def post(self):
    if self.request.get('action:startbackend'):
      self.stub.start_backend(self.request.get('backend'))
    if self.request.get('action:stopbackend'):
      self.stub.stop_backend(self.request.get('backend'))
    self.redirect(self.request.path_url)
    return


class MemcachePageHandler(BaseRequestHandler):
  """Shows stats about memcache and query form to get values."""
  PATH = '/memcache'



  TYPES = ((str, str, 'String'),
           (unicode, unicode, 'Unicode String'),
           (bool, lambda value: MemcachePageHandler._ToBool(value), 'Boolean'),
           (int, int, 'Integer'),
           (long, long, 'Long Integer'),
           (float, float, 'Float'))
  DEFAULT_TYPESTR_FOR_NEW = 'String'

  @staticmethod
  def _ToBool(string_value):
    """Convert string to boolean value.

    Args:
      string_value: A string.

    Returns:
      Boolean.  True if string_value is "true", False if string_value is
      "false".  This is case-insensitive.

    Raises:
      ValueError: string_value not "true" or "false".
    """
    string_value_low = string_value.lower()
    if string_value_low not in ('false', 'true'):
      raise ValueError('invalid literal for boolean: %s' % string_value)
    return string_value_low == 'true'

  def _GetValueAndType(self, key):
    """Fetch value from memcache and detect its type.

    Args:
      key: String

    Returns:
      (value, type), value is a Python object or None if the key was not set in
      the cache, type is a string describing the type of the value.
    """
    try:
      value = memcache.get(key)
    except (pickle.UnpicklingError, AttributeError, EOFError, ImportError,
            IndexError), e:


      msg = 'Failed to retrieve value from cache: %s' % e
      return msg, 'error'

    if value is None:

      return None, self.DEFAULT_TYPESTR_FOR_NEW


    for typeobj, _, typestr in self.TYPES:
      if isinstance(value, typeobj):
        break
    else:

      typestr = 'pickled'
      value = pprint.pformat(value, indent=2)

    return value, typestr

  def _SetValue(self, key, type_, value):
    """Convert a string value and store the result in memcache.

    Args:
      key: String
      type_: String, describing what type the value should have in the cache.
      value: String, will be converted according to type_.

    Returns:
      Result of memcache.set(key, converted_value).  True if value was set.

    Raises:
      ValueError: Value can't be converted according to type_.
    """
    for _, converter, typestr in self.TYPES:
      if typestr == type_:
        value = converter(value)
        break
    else:
      raise ValueError('Type %s not supported.' % type_)
    return memcache.set(key, value)

  def get(self):
    """Show template and prepare stats and/or key+value to display/edit."""
    values = {'request': self.request,
              'message': self.request.get('message')}

    edit = self.request.get('edit')
    key = self.request.get('key')
    if edit:

      key = edit
      values['show_stats'] = False
      values['show_value'] = False
      values['show_valueform'] = True
      values['types'] = [typestr for _, _, typestr in self.TYPES]
    elif key:

      values['show_stats'] = True
      values['show_value'] = True
      values['show_valueform'] = False
    else:

      values['show_stats'] = True
      values['show_valueform'] = False
      values['show_value'] = False

    if key:
      values['key'] = key
      values['value'], values['type'] = self._GetValueAndType(key)
      values['key_exists'] = values['value'] is not None

      if values['type'] in ('pickled', 'error'):
        values['writable'] = False
      else:
        values['writable'] = True

    if values['show_stats']:
      memcache_stats = memcache.get_stats()
      if not memcache_stats:

        memcache_stats = {'hits': 0, 'misses': 0, 'byte_hits': 0, 'items': 0,
                          'bytes': 0, 'oldest_item_age': 0}
      values['stats'] = memcache_stats
      try:
        hitratio = memcache_stats['hits'] * 100 / (memcache_stats['hits']
                                                   + memcache_stats['misses'])
      except ZeroDivisionError:
        hitratio = 0
      values['hitratio'] = hitratio
      delta_t = datetime.timedelta(seconds=memcache_stats['oldest_item_age'])
      values['oldest_item_age'] = datetime.datetime.now() - delta_t

    self.generate('memcache.html', values)

  def _urlencode(self, query):
    """Encode a dictionary into a URL query string.

    In contrast to urllib this encodes unicode characters as UTF8.

    Args:
      query: Dictionary of key/value pairs.

    Returns:
      String.
    """
    return '&'.join('%s=%s' % (urllib.quote_plus(k.encode('utf8')),
                               urllib.quote_plus(v.encode('utf8')))
                    for k, v in query.iteritems())

  @xsrf_required
  def post(self):
    """Handle modifying actions and/or redirect to GET page."""
    next_param = {}

    if self.request.get('action:flush'):
      if memcache.flush_all():
        next_param['message'] = 'Cache flushed, all keys dropped.'
      else:
        next_param['message'] = 'Flushing the cache failed.  Please try again.'

    elif self.request.get('action:display'):
      next_param['key'] = self.request.get('key')

    elif self.request.get('action:edit'):
      next_param['edit'] = self.request.get('key')

    elif self.request.get('action:delete'):
      key = self.request.get('key')
      result = memcache.delete(key)
      if result == memcache.DELETE_NETWORK_FAILURE:
        next_param['message'] = ('ERROR: Network failure, key "%s" not deleted.'
                                 % key)
      elif result == memcache.DELETE_ITEM_MISSING:
        next_param['message'] = 'Key "%s" not in cache.' % key
      elif result == memcache.DELETE_SUCCESSFUL:
        next_param['message'] = 'Key "%s" deleted.' % key
      else:
        next_param['message'] = ('Unknown return value.  Key "%s" might still '
                                 'exist.' % key)

    elif self.request.get('action:save'):
      key = self.request.get('key')
      value = self.request.get('value')
      type_ = self.request.get('type')
      next_param['key'] = key
      try:
        if self._SetValue(key, type_, value):
          next_param['message'] = 'Key "%s" saved.' % key
        else:
          next_param['message'] = 'ERROR: Failed to save key "%s".' % key
      except ValueError, e:
        next_param['message'] = 'ERROR: Unable to encode value: %s' % e

    elif self.request.get('action:cancel'):
      next_param['key'] = self.request.get('key')

    else:
      next_param['message'] = 'Unknown action.'

    next = self.request.path_url
    if next_param:
      next = '%s?%s' % (next, self._urlencode(next_param))
    self.redirect(next)


class DatastoreGetIndexesHandler(BaseRequestHandler):
  """Our main request handler that displays indexes"""

  PATH = '/datastore_indexes'

  def get(self):
    indexes = collections.defaultdict(list)
    for index, state in datastore.GetIndexes():
      properties = []
      for property_name, sort_direction in index.Properties():
        properties.append({
          'name': property_name,
          'sort_symbol': ('&#x25b2;', '&#x25bc;')[sort_direction - 1],
          'sort_direction': ('ASCENDING', 'DESCENDING')[sort_direction - 1]
        })
      kind = str(index.Kind())
      kind_indexes = indexes[kind]
      kind_indexes.append({
        'id': str(index.Id()),
        'status': ('BUILDING', 'SERVING', 'DELETING', 'ERROR')[state],
        'has_ancestor': bool(index.HasAncestor()),
        'properties': properties
      })
    self.generate('datastore_indexes.html',
                  {'request': self.request, 'indexes': sorted(indexes.items())})


class DatastoreRequestHandler(BaseRequestHandler):
  """The base request handler for our datastore admin pages.

  We provide utility functions for querying the datastore and inferring the
  types of entity properties.
  """

  def start(self):
    """Returns the santized "start" argument from the URL."""
    return self.request.get_range('start', min_value=0, default=0)

  def num(self):
    """Returns the sanitized "num" argument from the URL."""
    return self.request.get_range('num', min_value=1, max_value=100,
                                  default=10)



  def execute_query(self, start=0, num=0, no_order=False):
    """Parses the URL arguments and executes the query.

    Args:
      start: How many entities from the beginning of the result list should be
        skipped from the query.
      num: How many entities should be returned, if 0 (default) then a
        reasonable default will be chosen.

    Returns:
      A tuple (list of entities, total entity count).  If inappropriate URL
      arguments are given, we return an empty set of results and 0 for the
      entity count.
    """
    kind = self.request.get('kind')
    namespace = self.request.get('namespace')
    if not namespace:
      namespace = None
    if not kind:
      return ([], 0)
    query = datastore.Query(kind, _namespace=namespace)


    order = self.request.get('order')
    order_type = self.request.get('order_type')
    if order and order_type:
      order_type = DataType.get_by_name(order_type).python_type()
      if order.startswith('-'):
        direction = datastore.Query.DESCENDING
        order = order[1:]
      else:
        direction = datastore.Query.ASCENDING
      try:
        query.Order((order, order_type, direction))
      except datastore_errors.BadArgumentError:

        pass

    if not start:
      start = self.start()
    if not num:
      num = self.num()
    total = query.Count()
    entities = query.Get(start + num)[start:]
    return (entities, total)

  def get_key_values(self, entities):
    """Returns the union of key names used by the given list of entities.

    We return the union as a dictionary mapping the key names to a sample
    value from one of the entities for the key name.
    """
    key_dict = {}
    for entity in entities:
      for key, value in entity.iteritems():
        if key_dict.has_key(key):
          key_dict[key].append(value)
        else:
          key_dict[key] = [value]
    return key_dict

  def redirect_with_message(self, message):
    """Redirect to the 'next' url with message added as the msg parameter."""
    quoted_message = urllib.quote_plus(message)
    redirect_url = self.request.get('next')
    if '?' in redirect_url:
      redirect_url += '&msg=%s' % quoted_message
    else:
      redirect_url += '?msg=%s' % quoted_message
    self.redirect(redirect_url)


class DatastoreQueryHandler(DatastoreRequestHandler):
  """Our main request handler that executes queries and lists entities.

  We use execute_query() in our base request handler to parse URL arguments
  and execute the datastore query.
  """

  PATH = '/datastore'

  _ONE_MILLION = decimal.Decimal(1000000)

  _DOLLARS_PER_WRITE = 1/_ONE_MILLION

  _PENNIES_PER_WRITE = _DOLLARS_PER_WRITE/100

  def _writes_to_pennies(self, writes):
    return self._PENNIES_PER_WRITE * writes

  def _calculate_writes_for_built_in_indices(self, entity):
    writes = 0
    for prop_name in entity.keys():
      if not prop_name in entity.unindexed_properties():


        prop_vals = entity[prop_name]
        if isinstance(prop_vals, (list)):
          num_prop_vals = len(prop_vals)
        else:
          num_prop_vals = 1
        writes += 2 * num_prop_vals
    return writes

  def _calculate_writes_for_composite_index(self, entity, index):
    composite_index_value_count = 1
    for prop_name, _ in index.Properties():
      if not prop_name in entity.keys() or (
          prop_name in entity.unindexed_properties()):
        return 0
      prop_vals = entity[prop_name]
      if isinstance(prop_vals, (list)):
        composite_index_value_count = (
            composite_index_value_count * len(prop_vals))





    ancestor_count = 1
    if index.HasAncestor():
      key = entity.key().parent()
      while key != None:
        ancestor_count = ancestor_count + 1
        key = key.parent()
    return composite_index_value_count * ancestor_count

  def _get_write_ops(self, entity):

    writes = 2 + self._calculate_writes_for_built_in_indices(entity)


    for index, _ in datastore.GetIndexes():
      if index.Kind() != entity.kind():
        continue
      writes = writes + self._calculate_writes_for_composite_index(
          entity, index)
    return writes

  def _get_creation_cost_analysis(self, entity):
    write_ops = self._get_write_ops(entity)
    return (write_ops, self._writes_to_pennies(write_ops))

  def get_kinds(self, namespace):
    """Get sorted list of kind names the datastore knows about.

    This should only be called in the development environment as metadata
    queries are expensive and no caching is done.

    Args:
      namespace: The namespace to fetch the schema for e.g. 'google.com'. It
          is an error to pass in None.

    Returns:
      A sorted list of kinds e.g. ['Book', 'Guest', Post'] (encoded in utf-8).
    """
    assert namespace is not None
    q = metadata.Kind.all(namespace=namespace)
    return [x.kind_name.encode('utf-8') for x in q.run()]

  def get(self):
    """Formats the results from execute_query() for datastore.html.

    The only complex part of that process is calculating the pager variables
    to generate the Gooooogle pager at the bottom of the page.
    """



    result_set, total = self.execute_query()
    key_values = self.get_key_values(result_set)
    keys = key_values.keys()
    keys.sort()



    headers = []
    for key in keys[:DEFAULT_MAX_DATASTORE_VIEWER_COLUMNS]:
      sample_value = key_values[key][0]
      headers.append({
        'name': ustr(key),
        'type': DataType.get(sample_value).name(),
      })



    entities = []
    edit_path = self.base_path() + DatastoreEditHandler.PATH
    for entity in result_set:
      write_ops = self._get_write_ops(entity)
      attributes = []
      for key in keys[:DEFAULT_MAX_DATASTORE_VIEWER_COLUMNS]:
        if entity.has_key(key):
          raw_value = entity[key]
          data_type = DataType.get(raw_value)
          value = data_type.format(raw_value)
          short_value = data_type.short_format(raw_value)
          additional_html = data_type.additional_short_value_html(raw_value)
        else:
          value = ''
          short_value = ''
          additional_html = ''
        attributes.append({
          'name': ustr(key),
          'value': ustr(value),
          'short_value': short_value,
          'additional_html': ustr(additional_html),
        })
      entities.append({
        'key': ustr(entity.key()),
        'key_name': ustr(entity.key().name()),
        'key_id': entity.key().id(),
        'write_ops' : write_ops,
        'shortened_key': str(entity.key())[:8] + '...',
        'attributes': attributes,
        'edit_uri': edit_path + '?key=' + str(entity.key()) + '&kind=' + urllib.quote(ustr(self.request.get('kind'))) + '&next=' + urllib.quote(ustr(self.filter_url(
                        ['kind', 'order', 'order_type', 'namespace', 'num']))),
      })


    start = self.start()
    num = self.num()
    max_pager_links = 8
    current_page = start / num
    num_pages = int(math.ceil(total * 1.0 / num))
    page_start = max(int(math.floor(current_page - max_pager_links / 2)), 0)
    page_end = min(page_start + max_pager_links, num_pages)

    pages = []
    for page in range(page_start + 1, page_end + 1):
      pages.append({
        'number': page,
        'start': (page - 1) * num,
      })
    current_page += 1

    in_production = self.in_production()
    if in_production:
      kinds = None
    else:
      kinds = self.get_kinds(self.request.get('namespace'))


    values = {
        'request': self.request,
        'in_production': in_production,
        'kinds': kinds,
        'kind': ustr(self.request.get('kind')),
        'order': self.request.get('order'),
        'headers': headers,
        'entities': entities,
        'message': self.request.get('msg'),
        'pages': pages,
        'current_page': current_page,
        'namespace': self.request.get('namespace'),
        'show_namespace': self.request.get('namespace', None) is not None,
        'num': num,
        'next_start': -1,
        'prev_start': -1,
        'start': start,
        'total': total,
        'start_base_url': self.filter_url(['kind', 'order', 'order_type',
                                           'namespace', 'num']),
        'order_base_url': self.filter_url(['kind', 'namespace', 'num']),
        'property_overflow': len(keys) > DEFAULT_MAX_DATASTORE_VIEWER_COLUMNS,
    }
    if current_page > 1:
      values['prev_start'] = int((current_page - 2) * num)
    if current_page < num_pages:
      values['next_start'] = int(current_page * num)

    self.generate('datastore.html', values)


class DatastoreBatchEditHandler(DatastoreRequestHandler):
  """Request handler for a batch operation on entities.

  Supports deleting multiple entities by key, then redirecting to another url.
  """

  PATH = DatastoreQueryHandler.PATH + '/batchedit'

  @xsrf_required
  def post(self):
    """Handle POST."""
    if self.request.get('flush_memcache'):
      if memcache.flush_all():
        message = 'Cache flushed, all keys dropped.'
      else:
        message = 'Flushing the cache failed.  Please try again.'
      self.redirect_with_message(message)
      return

    kind = self.request.get('kind')



    keys = []
    index = 0
    num_keys = int(self.request.get('numkeys'))
    for i in xrange(1, num_keys+1):
      key = self.request.get('key%d' % i)
      if key:
        keys.append(key)

    if self.request.get('action') == 'Delete':
      num_deleted = 0

      for key in keys:
        datastore.Delete(datastore.Key(key))
        num_deleted = num_deleted + 1
      message = '%d entit%s deleted. %s' % (
        num_deleted, ('ies', 'y')[num_deleted == 1], _DATASTORE_CACHING_WARNING)
      self.redirect_with_message(message)
      return


    self.error(404)


class DatastoreEditHandler(DatastoreRequestHandler):
  """Request handler for the entity create/edit form.

  We determine how to generate a form to edit an entity by doing a query
  on the entity kind and looking at the set of keys and their types in
  the result set. We use the DataType subclasses for those introspected types
  to generate the form and parse the form results.
  """

  PATH = DatastoreQueryHandler.PATH + '/edit'

  def get(self):

    entity_key = self.request.get('key')
    if entity_key:
      key_instance = datastore.Key(entity_key)
      entity_key_name = key_instance.name()
      if entity_key_name:
        entity_key_name = ustr(entity_key_name)
      entity_key_id = key_instance.id()
      namespace = key_instance.namespace()
      parent_key = key_instance.parent()
      kind = key_instance.kind()
      entity = datastore.Get(key_instance)
      sample_entities = [entity]
    else:

      kind = self.request.get('kind')
      sample_entities = self.execute_query()[0]

    if len(sample_entities) < 1:





      next_uri = self.request.get('next')
      next_uri += '&msg=%s' % urllib.quote_plus(
          "The kind %s doesn't exist in the %s namespace" % (
              kind,
              self.request.get('namespace', '<Empty>')))

      kind_param = 'kind=%s' % kind
      if not kind_param in next_uri:
        if '?' in next_uri:
          next_uri += '&' + kind_param
        else:
          next_uri += '?' + kind_param
      self.redirect(next_uri)
      return

    if not entity_key:
      key_instance = None
      entity_key_name = None
      entity_key_id = None
      namespace = self.request.get('namespace')
      parent_key = None
      entity = None

    if parent_key:
      parent_kind = parent_key.kind()
      parent_key_string = PseudoBreadcrumbs(parent_key)
    else:
      parent_kind = None
      parent_key_string = None




    fields = []
    key_values = self.get_key_values(sample_entities)
    for key, sample_values in sorted(key_values.iteritems()):
      if entity and entity.has_key(key):
        data_type = DataType.get(entity[key])
      else:
        data_type = DataType.get(sample_values[0])
      name = data_type.name() + "|" + key
      if entity and entity.has_key(key):
        value = entity[key]
      else:
        value = None
      field = data_type.input_field(name, value, sample_values)
      fields.append((ustr(key), data_type.name(), field))





    self.generate('datastore_edit.html', {
      'kind': ustr(kind),
      'key': entity_key,
      'key_name': entity_key_name,
      'key_id': entity_key_id,
      'fields': fields,
      'focus': self.request.get('focus'),
      'namespace': namespace,
      'next': self.request.get('next'),
      'parent_key': parent_key,
      'parent_kind': parent_kind,
      'parent_key_string': parent_key_string,
    })

  @xsrf_required
  def post(self):

    kind = self.request.get('kind')
    entity_key = self.request.get('key')
    if entity_key:

      if self.request.get('action') == 'Delete':
        datastore.Delete(datastore.Key(entity_key))
        self.redirect_with_message(
            'Entity deleted. %s' % _DATASTORE_CACHING_WARNING)
        return
      entity = datastore.Get(datastore.Key(entity_key))
    else:
      namespace = self.request.get('namespace')
      if not namespace:
        namespace = None
      entity = datastore.Entity(kind, _namespace=namespace)

    args = self.request.arguments()
    for arg in args:
      bar = arg.find('|')
      if bar > 0:
        data_type_name = arg[:bar]
        field_name = arg[bar + 1:]
        form_value = self.request.get(arg)
        data_type = DataType.get_by_name(data_type_name)



        if entity and entity.has_key(field_name):
          old_formatted_value = data_type.format(entity[field_name])
          if old_formatted_value == ustr(form_value):
            continue


        if len(form_value) > 0:
          value = data_type.parse(form_value)
          entity[field_name] = value
        elif entity.has_key(field_name):
          del entity[field_name]


    datastore.Put(entity)

    if entity_key:
      self.redirect_with_message(
          'Entity updated. %s' % _DATASTORE_CACHING_WARNING)
    else:
      self.redirect(self.request.get('next'))


class DatastoreStatsHandler(BaseRequestHandler):
  """Allows computation of datastore stats."""

  PATH = '/datastore_stats'

  def get(self):
    """Shows Datastore Stats generator button."""
    values = {
        'request': self.request,
        'app_id': self.request.get('app_id', None),
        'status': self.request.get('status', None),
        'msg': self.request.get('msg', None)}
    self.generate('datastore_stats.html', values)

  @xsrf_required
  def post(self):
    """Handle actions and redirect to GET page."""
    app_id = self.request.get('app_id', None)
    if self.request.get('action:compute_stats'):
      status = 'OK'
      msg = self.generate_stats(_app=app_id)
    else:
      status = 'FAIL'
      msg = 'No processing requested'

    uri = self.request.path_url
    self.redirect('%s?%s' % (uri, urllib.urlencode(
        [('msg', msg), ('status', status)])))

  def generate_stats(self, _app=None):
    """Generate datastore stats."""
    processor = datastore_stats_generator.DatastoreStatsProcessor(_app)
    return processor.Run().Report()


class SearchIndexesListHandler(BaseRequestHandler):
  """FTS main page with list on indexes."""

  PATH = '/search'

  def get(self):
    """Displays list of FTS indexes."""
    start = self.request.get_range('start', min_value=0, default=0)
    limit = self.request.get_range('num', min_value=1, max_value=100,
                                   default=10)
    namespace = self.request.get('namespace', default_value=None)
    resp = search.get_indexes(offset=start, limit=limit+1,
                              namespace=namespace or '')
    has_more = len(resp.results) > limit
    indexes = resp.results[:limit]

    current_page = start / limit + 1
    values = {
        'request': self.request,
        'namespace': namespace,
        'has_namespace': namespace is not None,
        'current_page': current_page,
        'next_start': -1,
        'prev_start': -1,
        'num': limit,
        'start': start,
        'start_base_url': self.filter_url(['num', 'namespace']),
        'next': urllib.quote(ustr(self.request.uri)),
        'indexes': indexes}
    if current_page > 1:
      values['prev_start'] = int((current_page - 2) * limit)
      values['paging'] = True
    if has_more:
      values['next_start'] = int(current_page * limit)
      values['paging'] = True

    self.generate('search.html', values)


class SearchIndexHandler(BaseRequestHandler):
  """FTS index information."""

  PATH = '/search_index'

  def _ProcessSearchResponse(self, response):
    """Format document list and produce corresponding hdf representation."""

    documents = []
    field_names = set()



    for result in response.results:
      doc = Document(result.doc_id)
      for field in result.fields:
        field_names.add(field.name)
        doc.fields[field.name] = field
      documents.append(doc)

    field_names = sorted(field_names)
    docs = []

    for doc in documents:
      doc_fields = []
      for field_name in field_names:
        if field_name in doc.fields:
          value = TruncateValue(doc.fields[field_name].value)
        else:
          value = ''
        doc_fields.append(value)
      docs.append({
          'doc_id': doc.doc_id,
          'fields': doc_fields
          })

    return {
        'documents': docs,
        'field_names': field_names,
        }

  def get(self):
    """Displays documents in a FTS index."""
    start = self.request.get_range('start', min_value=0, default=0)
    query = self.request.get('query')
    namespace = self.request.get('namespace')
    limit = self.request.get_range('num', min_value=1, max_value=100,
                                   default=10)
    index_name = self.request.get('index') or 'index'
    index = search.Index(name=index_name, namespace=namespace)
    resp = index.search(query=search.Query(
        query_string=query,
        options=search.QueryOptions(offset=start, limit=limit)))
    has_more = resp.number_found > start + limit

    current_page = start / limit + 1
    values = {
        'request': self.request,
        'namespace': namespace,
        'index': index_name,
        'query': query,
        'current_page': current_page,
        'next_start': -1,
        'prev_start': -1,
        'start_base_url': self.filter_url([
            'query', 'index', 'num', 'namespace']),
        'next': urllib.quote(ustr(self.request.uri)),
        'values': self._ProcessSearchResponse(resp),
        'prev': self.request.get(
            'next',
            default_value=self.base_path() + SearchIndexesListHandler.PATH)}
    if current_page > 1:
      values['prev_start'] = int((current_page - 2) * limit)
      values['paging'] = True
    if has_more:
      values['next_start'] = int(current_page * limit)
      values['paging'] = True

    self.generate('search_index.html', values)


class SearchDocumentHandler(BaseRequestHandler):
  """FTS document information."""

  PATH = '/search_document'

  def get(self):
    """Displays FTS document."""
    index_name = self.request.get('index')
    doc_id = self.request.get('id')
    namespace = self.request.get('namespace')
    doc = None
    index = search.Index(name=index_name, namespace=namespace)
    resp = index.get_range(start_id=doc_id, limit=1)
    if resp.results and resp.results[0].doc_id == doc_id:
      doc = resp.results[0]

    values = {
        'request': self.request,
        'namespace': namespace,
        'index': index_name,
        'doc_id': doc_id,
        'doc': doc,
        'prev': self.request.get(
            'next', default_value=self.base_path() + SearchIndexHandler.PATH +
            '?index=' + index_name)}
    self.generate('search_document.html', values)


class SearchBatchDeleteHandler(BaseRequestHandler):
  """FTS batch delete handler."""

  PATH = '/search_batch_delete'

  @xsrf_required
  def post(self):
    """Handle POST."""
    index_name = self.request.get('index')
    namespace = self.request.get('namespace')

    docs = []
    index = 0
    num_docs = int(self.request.get('numdocs'))
    for i in xrange(1, num_docs+1):
      key = self.request.get('doc%d' % i)
      if key:
        docs.append(key)

    index = search.Index(name=index_name, namespace=namespace)
    index.delete(docs)
    self.redirect(self.request.get('next'))



class DataType(object):
  """A DataType represents a data type in the datastore.

  Each DataType subtype defines four methods:

     format: returns a formatted string for a datastore value
     input_field: returns a string HTML <input> element for this DataType
     name: the friendly string name of this DataType
     parse: parses the formatted string representation of this DataType
     python_type: the canonical Python type for this datastore type

  We use DataType instances to display formatted values in our result lists,
  and we uses input_field/format/parse to generate forms and parse the results
  from those forms to allow editing of entities.
  """
  @staticmethod
  def get(value):
    return _DATA_TYPES[value.__class__]

  @staticmethod
  def get_by_name(name):
    return _NAMED_DATA_TYPES[name]

  def format(self, value):
    return ustr(value)

  def short_format(self, value):
    return self.format(value)

  def input_field(self, name, value, sample_values):
    string_value = self.format(value) if value else ''
    return '<input class="%s" name="%s" type="text" size="%d" value="%s"/>' % (cgi.escape(ustr(self.name())), cgi.escape(ustr(name)),
            self.input_field_size(),
            cgi.escape(string_value, True))

  def input_field_size(self):
    return 30

  def additional_short_value_html(self, unused_value):

    return ''


class StringType(DataType):
  def format(self, value):
    return ustr(value)

  def input_field(self, name, value, sample_values):
    name = ustr(name)
    string_value = self.format(value) if value else ''
    sample_values = [self.format(s) for s in sample_values]
    multiline = False
    if value:
      multiline = len(string_value) > 255 or string_value.find('\n') >= 0
    if not multiline:
      for sample_value in sample_values:
        if sample_value and (len(sample_value) > 255 or
                             sample_value.find('\n') >= 0):
          multiline = True
          break
    if multiline:
      return '<textarea name="%s" rows="5" cols="50">%s</textarea>' % (cgi.escape(name), cgi.escape(string_value))
    else:
      return DataType.input_field(self, name, value, sample_values)

  def name(self):
    return 'string'

  def parse(self, value):
    return value

  def python_type(self):
    return str

  def input_field_size(self):
    return 50


class TextType(StringType):
  def name(self):
    return 'Text'

  def input_field(self, name, value, sample_values):
    string_value = self.format(value) if value else ''
    return '<textarea name="%s" rows="5" cols="50">%s</textarea>' % (cgi.escape(ustr(name)), cgi.escape(string_value))

  def parse(self, value):
    return datastore_types.Text(value)

  def python_type(self):
    return datastore_types.Text


class ByteStringType(StringType):
  def format(self, value):

    if value is None:
      return 'None'
    r = value.encode('string-escape')
    return r

  def name(self):
    return 'ByteString'

  def parse(self, value):


    bytestring = value.encode('ascii').decode('string-escape')
    return datastore_types.ByteString(bytestring)

  def python_type(self):
    return datastore_types.ByteString


class BlobType(StringType):
  def name(self):
    return 'Blob'

  def input_field(self, name, value, sample_values):
    return '&lt;binary&gt;'

  def format(self, value):
    return '<binary>'

  def python_type(self):
    return datastore_types.Blob


class EmbeddedEntityType(BlobType):
  def name(self):
    return 'entity:proto'

  def python_type(self):
    return datastore_types.EmbeddedEntity


class TimeType(DataType):
  _FORMAT = '%Y-%m-%d %H:%M:%S'

  def format(self, value):
    return value.isoformat(' ')[0:19]

  def name(self):
    return 'datetime'

  def parse(self, value):
    return datetime.datetime(*(time.strptime(ustr(value),
                                             TimeType._FORMAT)[0:6]))

  def python_type(self):
    return datetime.datetime


class ListType(DataType):
  def format(self, value):
    return urepr(value)

  def short_format_orig(self, value):
    format = self.format(value)
    if len(format) > 20:
      return format[:20] + '...'
    else:
      return format

  def utf8_short_format(self, value):
    format = self.format(value).decode('utf-8')
    if len(format) > 20:
      return format[:20].encode('utf-8') + '...'
    else:
      return format.encode('utf-8')

  def short_format(self, value):


    try:
      return self.utf8_short_format(value)
    except Exception:
      return self.short_format_orig(value)

  def name(self):
    return 'list'

  def input_field(self, name, value, sample_values):
    string_value = self.format(value) if value else ''
    return cgi.escape(string_value)

  def python_type(self):
    return list


class BoolType(DataType):
  def name(self):
    return 'bool'

  def input_field(self, name, value, sample_values):
    selected = { None: '', False: '', True: '' };
    selected[value] = "selected"
    return """<select class="%s" name="%s">
    <option %s value=''></option>
    <option %s value='0'>False</option>
    <option %s value='1'>True</option></select>""" % (cgi.escape(self.name()), cgi.escape(name), selected[None],
            selected[False], selected[True])

  def parse(self, value):
    if value.lower() is 'true':
      return True
    if value.lower() is 'false':
      return False

    return bool(int(value))

  def python_type(self):
    return bool


class NumberType(DataType):
  def input_field_size(self):
    return 10


class IntType(NumberType):
  def name(self):
    return 'int'

  def parse(self, value):
    return int(value)

  def python_type(self):
    return int


class LongType(NumberType):
  def name(self):
    return 'long'

  def parse(self, value):
    return long(value)

  def python_type(self):
    return long


class FloatType(NumberType):
  def name(self):
    return 'float'

  def parse(self, value):
    return float(value)

  def python_type(self):
    return float


class UserType(DataType):
  def name(self):
    return 'User'

  def parse(self, value):
    return users.User(value)

  def python_type(self):
    return users.User

  def input_field_size(self):
    return 15



class ReferenceType(DataType):
  def name(self):
    return 'Key'

  def short_format(self, value):
    return str(value)[:8] + '...'

  def parse(self, value):
    return datastore_types.Key(value)

  def python_type(self):
    return datastore_types.Key

  def input_field(self, name, value, sample_values):
    string_value = self.format(value) if value else ''
    html = '<input class="%s" name="%s" type="text" size="%d" value="%s"/>' % (cgi.escape(self.name()), cgi.escape(name), self.input_field_size(),
            cgi.escape(string_value, True))
    if value:
      html += '<br><a href="?key=%s">%s</a>' % (cgi.escape(string_value, True),
           cgi.escape(PseudoBreadcrumbs(value), True))
    return html

  def input_field_size(self):
    return 85

  def additional_short_value_html(self, value):
    if not value:
      return ''
    return '<br><a href="./datastore/edit?key=%s">%s</a>' % (cgi.escape(str(value), True),
         cgi.escape(PseudoBreadcrumbs(value), True))


class EmailType(StringType):
  def name(self):
    return 'Email'

  def parse(self, value):
    return datastore_types.Email(value)

  def python_type(self):
    return datastore_types.Email


class CategoryType(StringType):
  def name(self):
    return 'Category'

  def parse(self, value):
    return datastore_types.Category(value)

  def python_type(self):
    return datastore_types.Category


class LinkType(StringType):
  def name(self):
    return 'Link'

  def parse(self, value):
    return datastore_types.Link(value)

  def python_type(self):
    return datastore_types.Link


class GeoPtType(DataType):
  def name(self):
    return 'GeoPt'

  def parse(self, value):
    return datastore_types.GeoPt(value)

  def python_type(self):
    return datastore_types.GeoPt


class ImType(DataType):
  def name(self):
    return 'IM'

  def parse(self, value):
    return datastore_types.IM(value)

  def python_type(self):
    return datastore_types.IM


class PhoneNumberType(StringType):
  def name(self):
    return 'PhoneNumber'

  def parse(self, value):
    return datastore_types.PhoneNumber(value)

  def python_type(self):
    return datastore_types.PhoneNumber


class PostalAddressType(StringType):
  def name(self):
    return 'PostalAddress'

  def parse(self, value):
    return datastore_types.PostalAddress(value)

  def python_type(self):
    return datastore_types.PostalAddress


class RatingType(NumberType):
  def name(self):
    return 'Rating'

  def parse(self, value):
    return datastore_types.Rating(value)

  def python_type(self):
    return datastore_types.Rating


class NoneType(DataType):
  def name(self):
    return 'None'

  def parse(self, value):
    return None

  def python_type(self):
    return None

  def format(self, value):
    return 'None'


class BlobKeyType(StringType):
  def name(self):
    return 'BlobKey'

  def parse(self, value):
    return datastore_types.BlobKey(value)

  def python_type(self):
    return datastore_types.BlobKey




_DATA_TYPES = {
  types.NoneType: NoneType(),
  types.StringType: StringType(),
  types.UnicodeType: StringType(),
  datastore_types.Text: TextType(),
  datastore_types.Blob: BlobType(),
  datastore_types.EmbeddedEntity: EmbeddedEntityType(),
  types.BooleanType: BoolType(),
  types.IntType: IntType(),
  types.LongType: LongType(),
  types.FloatType: FloatType(),
  datetime.datetime: TimeType(),
  users.User: UserType(),
  datastore_types.Key: ReferenceType(),
  types.ListType: ListType(),
  datastore_types.Email: EmailType(),
  datastore_types.Category: CategoryType(),
  datastore_types.Link: LinkType(),
  datastore_types.GeoPt: GeoPtType(),
  datastore_types.IM: ImType(),
  datastore_types.PhoneNumber: PhoneNumberType(),
  datastore_types.PostalAddress: PostalAddressType(),
  datastore_types.Rating: RatingType(),
  datastore_types.BlobKey: BlobKeyType(),
  datastore_types.ByteString: ByteStringType(),
}

_NAMED_DATA_TYPES = {}
for _data_type in _DATA_TYPES.values():
  _NAMED_DATA_TYPES[_data_type.name()] = _data_type


def _ParseCronYaml():
  """Loads the cron.yaml file and parses it.

  The CWD of the dev_appserver is the root of the application here.

  Returns a dict representing the contents of cron.yaml.
  """
  cronyaml_files = 'cron.yaml', 'cron.yml'
  for cronyaml in cronyaml_files:
    try:
      fh = open(cronyaml, "r")
    except IOError:
      continue
    try:
      cron_info = croninfo.LoadSingleCron(fh)
      return cron_info
    finally:
      fh.close()
  return None



def PseudoBreadcrumbs(key):
  """Return a string that looks like the breadcrumbs (for key properties).

  Args:
    key: A datastore_types.Key object.

  Returns:
    A string looking like breadcrumbs.
  """
  path = key.to_path()
  parts = []
  for i in range(0, len(path)//2):
    kind = path[i*2]
    if isinstance(kind, unicode):
      kind = kind.encode('utf8')
    value = path[i*2 + 1]
    if isinstance(value, (int, long)):
      parts.append('%s: id=%d' % (kind, value))
    else:
      if isinstance(value, unicode):
        value = value.encode('utf8')
      parts.append('%s: name=%s' % (kind, value))
  return ' > '.join(parts)


handlers = [
    ('.*' + DatastoreGetIndexesHandler.PATH, DatastoreGetIndexesHandler),
    ('.*' + DatastoreQueryHandler.PATH, DatastoreQueryHandler),
    ('.*' + DatastoreEditHandler.PATH, DatastoreEditHandler),
    ('.*' + DatastoreBatchEditHandler.PATH, DatastoreBatchEditHandler),
    ('.*' + DatastoreStatsHandler.PATH, DatastoreStatsHandler),
    ('.*' + DatastoreAdminHandler.PATH, DatastoreAdminHandler),
    ('.*' + InteractivePageHandler.PATH, InteractivePageHandler),
    ('.*' + InteractiveExecuteHandler.PATH, InteractiveExecuteHandler),
    ('.*' + MemcachePageHandler.PATH, MemcachePageHandler),
    ('.*' + ImageHandler.PATH, ImageHandler),
    ('.*' + QueuesPageHandler.PATH, QueuesPageHandler),
    ('.*' + SearchIndexesListHandler.PATH, SearchIndexesListHandler),
    ('.*' + SearchIndexHandler.PATH, SearchIndexHandler),
    ('.*' + SearchDocumentHandler.PATH, SearchDocumentHandler),
    ('.*' + SearchBatchDeleteHandler.PATH, SearchBatchDeleteHandler),
    ('.*' + TasksPageHandler.PATH, TasksPageHandler),
    ('.*' + XMPPPageHandler.PATH, XMPPPageHandler),
    ('.*' + InboundMailPageHandler.PATH, InboundMailPageHandler),
    ('.*' + BackendsPageHandler.PATH, BackendsPageHandler),
    ('.*', DefaultPageHandler),
  ]
if HAVE_CRON:
  handlers.insert(0, ('.*' + CronPageHandler.PATH, CronPageHandler))
application = webapp.WSGIApplication(handlers, debug=_DEBUG)


def main():
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
