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
"""Serves the stub App Engine APIs (e.g. memcache, datastore) over HTTP.

The Remote API protocol is used for communication.
"""

import contextlib
import errno
import getpass
import itertools
import logging
import os
import pickle
import shutil
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib2
import urlparse

import google
import yaml

# Stubs
from google.appengine.api import datastore_file_stub
from google.appengine.api import mail_stub
from google.appengine.api import request_info as request_info_lib
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub
from google.appengine.api.app_identity import (app_identity_stub,
                                               app_identity_external_stub)
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.capabilities import capability_stub
from google.appengine.api.channel import channel_service_stub
from google.appengine.api.files import file_service_stub
from google.appengine.api.logservice import logservice_stub
from google.appengine.api.search import appscale_search_stub
from google.appengine.api.taskqueue import taskqueue_distributed # AS
from google.appengine.api.prospective_search import prospective_search_stub
from google.appengine.api.memcache import memcache_distributed # AS
from google.appengine.api.modules import modules_stub
from google.appengine.api.remote_socket import _remote_socket_stub
from google.appengine.api.system import system_stub
from google.appengine.api.xmpp import xmpp_service_real # AS
from google.appengine.datastore import datastore_sqlite_stub
from google.appengine.datastore import datastore_stub_util
from google.appengine.datastore import datastore_v4_stub

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore
from google.appengine.ext.cloudstorage import stub_dispatcher as gcs_dispatcher
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.ext.remote_api import remote_api_services
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools.devappserver2 import application_configuration
from google.appengine.tools.devappserver2 import cli_parser
from google.appengine.tools.devappserver2 import constants
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import wsgi_request_info
from google.appengine.tools.devappserver2 import wsgi_server

# AppScale
from google.appengine.api import datastore_distributed
from google.appengine.api.blobstore import datastore_blob_storage


# TODO: Remove this lock when stubs have been audited for thread
# safety.
GLOBAL_API_LOCK = threading.RLock()

# The default app id used when launching the api_server.py as a binary, without
# providing the context of a specific application.
DEFAULT_API_SERVER_APP_ID = 'dev~app_id'

def _execute_request(request, request_id=None):
  """Executes an API method call and returns the response object.

  Args:
    request: A remote_api_pb.Request object representing the API call e.g. a
        call to memcache.Get.
    request_id: Override default request identifier
  Returns:
    A ProtocolBuffer.ProtocolMessage representing the API response e.g. a
    memcache_service_pb.MemcacheGetResponse.

  Raises:
    apiproxy_errors.CallNotFoundError: if the requested method doesn't exist.
    apiproxy_errors.ApplicationError: if the API method calls fails.
  """
  service = request.service_name()
  method = request.method()
  if not request_id:
    if request.has_request_id():
      request_id = request.request_id()
    else:
      logging.error('Received a request without request_id: %s', request)

  service_methods = remote_api_services.SERVICE_PB_MAP.get(service, {})
  request_class, response_class = service_methods.get(method, (None, None))
  if not request_class:
    raise apiproxy_errors.CallNotFoundError('%s.%s does not exist' % (service,
                                                                      method))

  request_data = request_class()
  request_data.ParseFromString(request.request())
  response_data = response_class()
  service_stub = apiproxy_stub_map.apiproxy.GetStub(service)

  def make_request():
    service_stub.MakeSyncCall(service,
                              method,
                              request_data,
                              response_data,
                              request_id)

  # If the service has not declared itself as threadsafe acquire
  # GLOBAL_API_LOCK.
  if service_stub.THREADSAFE:
    make_request()
  else:
    with GLOBAL_API_LOCK:
      make_request()
  return response_data


class APIServer(wsgi_server.WsgiServer):
  """Serves API calls over HTTP."""

  def __init__(self, host, port, app_id, request_context):
    self._app_id = app_id
    self._host = host
    if request_context:
      self._request_context = request_context
    else:
      @contextlib.contextmanager
      def noop_context(environ):
        yield None
      self._request_context = noop_context
    super(APIServer, self).__init__((host, port), self)

  def start(self):
    """Start the API Server."""
    super(APIServer, self).start()
    logging.info('Starting API server at: http://%s:%d', self._host, self.port)

  def quit(self):
    cleanup_stubs()
    super(APIServer, self).quit()

  def _handle_POST(self, environ, start_response):
    start_response('200 OK', [('Content-Type', 'application/octet-stream')])

    start_time = time.time()
    response = remote_api_pb.Response()
    try:
      request = remote_api_pb.Request()
      # NOTE: Exceptions encountered when parsing the PB or handling the request
      # will be propagated back to the caller the same way as exceptions raised
      # by the actual API call.
      if environ.get('HTTP_TRANSFER_ENCODING') == 'chunked':
        # CherryPy concatenates all chunks  when 'wsgi.input' is read but v3.2.2
        # will not return even when all of the data in all chunks has been
        # read. See: https://bitbucket.org/cherrypy/cherrypy/issue/1131.
        wsgi_input = environ['wsgi.input'].read(2**32)
      else:
        wsgi_input = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))
      request.ParseFromString(wsgi_input)
      with self._request_context(environ) as request_id:
        api_response = _execute_request(request, request_id).Encode()
      response.set_response(api_response)
    except Exception, e:
      if isinstance(e, apiproxy_errors.ApplicationError):
        level = logging.DEBUG
        application_error = response.mutable_application_error()
        application_error.set_code(e.application_error)
        application_error.set_detail(e.error_detail)
        # TODO: is this necessary? Python remote stub ignores exception
        # when application error is specified; do other runtimes use it?
        response.set_exception(pickle.dumps(e))
      else:
        # If the runtime instance is not Python, it won't be able to unpickle
        # the exception so use level that won't be ignored by default.
        level = logging.ERROR
        # Even if the runtime is Python, the exception may be unpicklable if
        # it requires importing a class blocked by the sandbox so just send
        # back the exception representation.
        response.set_exception(pickle.dumps(RuntimeError(repr(e))))
      logging.log(level, 'Exception while handling %s\n%s', request,
                  traceback.format_exc())
    encoded_response = response.Encode()
    logging.debug('Handled %s.%s in %0.4f',
                  request.service_name(),
                  request.method(),
                  time.time() - start_time)
    return [encoded_response]

  def _handle_GET(self, environ, start_response):
    params = urlparse.parse_qs(environ['QUERY_STRING'])
    rtok = params.get('rtok', ['0'])[0]

    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [yaml.dump({'app_id': self._app_id,
                       'rtok': rtok})]

  def __call__(self, environ, start_response):
    if environ['REQUEST_METHOD'] == 'GET':
      return self._handle_GET(environ, start_response)
    elif environ['REQUEST_METHOD'] == 'POST':
      return self._handle_POST(environ, start_response)
    else:
      start_response('405 Method Not Allowed')
      return []


def create_api_server(request_info, storage_path, options, app_id, app_root,
                      request_context=None):
  """Creates an API server.

  Args:
    request_info: An apiproxy_stub.RequestInfo instance used by the stubs to
      lookup information about the request associated with an API call.
    storage_path: A string directory for storing API stub data.
    options: An instance of argparse.Namespace containing command line flags.
    app_id: String representing an application ID, used for configuring paths
      and string constants in API stubs.
    app_root: The path to the directory containing the user's
        application e.g. "/home/joe/myapp", used for locating application yaml
        files, eg index.yaml for the datastore stub.
    request_context: Callback for starting requests
  Returns:
    An instance of APIServer.
  """
  datastore_path = options.datastore_path or os.path.join(
      storage_path, 'datastore.db')
  logs_path = options.logs_path or os.path.join(storage_path, 'logs.db')
  search_index_path = options.search_indexes_path or os.path.join(
      storage_path, 'search_indexes')
  prospective_search_path = options.prospective_search_path or os.path.join(
      storage_path, 'prospective-search')
  blobstore_path = options.blobstore_path or os.path.join(
      storage_path, 'blobs')

  if options.clear_datastore:
    _clear_datastore_storage(datastore_path)

  if options.clear_prospective_search:
    _clear_prospective_search_storage(prospective_search_path)

  if options.clear_search_indexes:
    _clear_search_indexes_storage(search_index_path)
  if options.auto_id_policy == datastore_stub_util.SEQUENTIAL:
    logging.warn("--auto_id_policy='sequential' is deprecated. This option "
                 "will be removed in a future release.")

  application_address = '%s' % options.host
  if options.port and options.port != 80:
    application_address += ':' + str(options.port)

  user_login_url = '/%s?%s=%%s' % (
      login.LOGIN_URL_RELATIVE, login.CONTINUE_PARAM)
  user_logout_url = '%s&%s=%s' % (
      user_login_url, login.ACTION_PARAM, login.LOGOUT_ACTION)

  if options.datastore_consistency_policy == 'time':
    consistency = datastore_stub_util.TimeBasedHRConsistencyPolicy()
  elif options.datastore_consistency_policy == 'random':
    consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy()
  elif options.datastore_consistency_policy == 'consistent':
    consistency = datastore_stub_util.PseudoRandomHRConsistencyPolicy(1.0)
  else:
    assert 0, ('unknown consistency policy: %r' %
               options.datastore_consistency_policy)

  app_identity_location = None
  if options.external_api_port:
    app_identity_location = ':'.join(['localhost',
                                      str(options.external_api_port)])

  maybe_convert_datastore_file_stub_data_to_sqlite(app_id, datastore_path)
  setup_stubs(
      request_data=request_info,
      app_id=app_id,
      application_root=app_root,
      # The "trusted" flag is only relevant for Google administrative
      # applications.
      trusted=getattr(options, 'trusted', False),
      blobstore_path=blobstore_path,
      datastore_path=datastore_path,
      datastore_consistency=consistency,
      datastore_require_indexes=options.require_indexes,
      datastore_auto_id_policy=options.auto_id_policy,
      images_host_prefix='http://%s' % application_address,
      logs_path=logs_path,
      mail_smtp_host=options.smtp_host,
      mail_smtp_port=options.smtp_port,
      mail_smtp_user=options.smtp_user,
      mail_smtp_password=options.smtp_password,
      mail_enable_sendmail=options.enable_sendmail,
      mail_show_mail_body=options.show_mail_body,
      matcher_prospective_search_path=prospective_search_path,
      search_index_path=search_index_path,
      taskqueue_auto_run_tasks=options.enable_task_running,
      taskqueue_default_http_server=application_address,
      user_login_url=user_login_url,
      user_logout_url=user_logout_url,
      default_gcs_bucket_name=options.default_gcs_bucket_name,
      uaserver_path=options.uaserver_path,
      xmpp_path=options.xmpp_path,
      xmpp_domain=options.login_server,
      app_identity_location=app_identity_location)

  # The APIServer must bind to localhost because that is what the runtime
  # instances talk to.
  return APIServer('localhost', options.api_port, app_id, request_context)


def _clear_datastore_storage(datastore_path):
  """Delete the datastore storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(datastore_path):
    try:
      os.remove(datastore_path)
    except OSError, err:
      logging.warning(
          'Failed to remove datastore file %r: %s', datastore_path, err)


def _clear_prospective_search_storage(prospective_search_path):
  """Delete the perspective search storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(prospective_search_path):
    try:
      os.remove(prospective_search_path)
    except OSError, err:
      logging.warning(
          'Failed to remove prospective search file %r: %s',
          prospective_search_path, err)


def _clear_search_indexes_storage(search_index_path):
  """Delete the search indexes storage file at the given path."""
  # lexists() returns True for broken symlinks, where exists() returns False.
  if os.path.lexists(search_index_path):
    try:
      os.remove(search_index_path)
    except OSError, err:
      logging.warning(
          'Failed to remove search indexes file %r: %s', search_index_path, err)


def get_storage_path(path, app_id):
  """Returns a path to the directory where stub data can be stored."""
  _, _, app_id = app_id.replace(':', '_').rpartition('~')
  if path is None:
    for path in _generate_storage_paths(app_id):
      try:
        os.mkdir(path, 0700)
      except OSError, err:
        if err.errno == errno.EEXIST:
          # Check that the directory is only accessable by the current user to
          # protect against an attacker creating the directory in advance in
          # order to access any created files. Windows has per-user temporary
          # directories and st_mode does not include per-user permission
          # information so assume that it is safe.
          if sys.platform == 'win32' or (
              (os.stat(path).st_mode & 0777) == 0700 and os.path.isdir(path)):
            return path
          else:
            continue
        raise
      else:
        return path
  elif not os.path.exists(path):
    os.mkdir(path)
    return path
  elif not os.path.isdir(path):
    raise IOError('the given storage path %r is a file, a directory was '
                  'expected' % path)
  else:
    return path


def _generate_storage_paths(app_id):
  """Yield an infinite sequence of possible storage paths."""
  if sys.platform == 'win32':
    # The temp directory is per-user on Windows so there is no reason to add
    # the username to the generated directory name.
    user_format = ''
  else:
    try:
      user_name = getpass.getuser()
    except Exception:  # pylint: disable=broad-except
      # The possible set of exceptions is not documented.
      user_format = ''
    else:
      user_format = '.%s' % user_name

  tempdir = tempfile.gettempdir()
  yield os.path.join(tempdir, 'appengine.%s%s' % (app_id, user_format))
  for i in itertools.count(1):
    yield os.path.join(tempdir, 'appengine.%s%s.%d' % (app_id, user_format, i))


def setup_stubs(
    request_data,
    app_id,
    application_root,
    trusted,
    blobstore_path,
    datastore_consistency,
    datastore_path,
    datastore_require_indexes,
    datastore_auto_id_policy,
    images_host_prefix,
    logs_path,
    mail_smtp_host,
    mail_smtp_port,
    mail_smtp_user,
    mail_smtp_password,
    mail_enable_sendmail,
    mail_show_mail_body,
    matcher_prospective_search_path,
    search_index_path,
    taskqueue_auto_run_tasks,
    taskqueue_default_http_server,
    user_login_url,
    user_logout_url,
    default_gcs_bucket_name,
    uaserver_path,
    xmpp_path,
    xmpp_domain,
    app_identity_location):
  """Configures the APIs hosted by this server.

  Args:
    request_data: An apiproxy_stub.RequestInformation instance used by the
        stubs to lookup information about the request associated with an API
        call.
    app_id: The str application id e.g. "guestbook".
    application_root: The path to the directory containing the user's
        application e.g. "/home/joe/myapp".
    trusted: A bool indicating if privileged APIs should be made available.
    blobstore_path: The path to the file that should be used for blobstore
        storage.
    datastore_consistency: The datastore_stub_util.BaseConsistencyPolicy to
        use as the datastore consistency policy.
    datastore_path: The path to the file that should be used for datastore
        storage.
    datastore_require_indexes: A bool indicating if the same production
        datastore indexes requirements should be enforced i.e. if True then
        a google.appengine.ext.db.NeedIndexError will be be raised if a query
        is executed without the required indexes.
    datastore_auto_id_policy: The type of sequence from which the datastore
        stub assigns auto IDs, either datastore_stub_util.SEQUENTIAL or
        datastore_stub_util.SCATTERED.
    images_host_prefix: The URL prefix (protocol://host:port) to prepend to
        image urls on calls to images.GetUrlBase.
    logs_path: Path to the file to store the logs data in.
    mail_smtp_host: The SMTP hostname that should be used when sending e-mails.
        If None then the mail_enable_sendmail argument is considered.
    mail_smtp_port: The SMTP port number that should be used when sending
        e-mails. If this value is None then mail_smtp_host must also be None.
    mail_smtp_user: The username to use when authenticating with the
        SMTP server. This value may be None if mail_smtp_host is also None or if
        the SMTP server does not require authentication.
    mail_smtp_password: The password to use when authenticating with the
        SMTP server. This value may be None if mail_smtp_host or mail_smtp_user
        is also None.
    mail_enable_sendmail: A bool indicating if sendmail should be used when
        sending e-mails. This argument is ignored if mail_smtp_host is not None.
    mail_show_mail_body: A bool indicating whether the body of sent e-mails
        should be written to the logs.
    matcher_prospective_search_path: The path to the file that should be used to
        save prospective search subscriptions.
    search_index_path: The path to the file that should be used for search index
        storage.
    taskqueue_auto_run_tasks: A bool indicating whether taskqueue tasks should
        be run automatically or it the must be manually triggered.
    taskqueue_default_http_server: A str containing the address of the http
        server that should be used to execute tasks.
    user_login_url: A str containing the url that should be used for user login.
    user_logout_url: A str containing the url that should be used for user
        logout.
    default_gcs_bucket_name: A str, overriding the default bucket behavior.
    uaserver_path: (AppScale-specific) A str containing the FQDN or IP address
        of the machine that runs a UserAppServer.
    xmpp_path: (AppScale-specific) A str containing the FQDN or IP address of
        the machine that runs ejabberd, where XMPP clients should connect to.
    xmpp_domain: A string specifying the domain portion of the XMPP user.
    app_identity_location: The location of a server that handles App Identity
        requests.
  """

  if app_identity_location is None:
    identity_stub = app_identity_stub.AppIdentityServiceStub()
    if default_gcs_bucket_name is not None:
      identity_stub.SetDefaultGcsBucketName(default_gcs_bucket_name)
  else:
    identity_stub = app_identity_external_stub.AppIdentityExternalStub(
        app_identity_location)
  apiproxy_stub_map.apiproxy.RegisterStub('app_identity_service', identity_stub)

  blob_storage = datastore_blob_storage.DatastoreBlobStorage(app_id)
  apiproxy_stub_map.apiproxy.RegisterStub(
      'blobstore',
      blobstore_stub.BlobstoreServiceStub(blob_storage,
                                          request_data=request_data))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'capability_service',
      capability_stub.CapabilityServiceStub())

  apiproxy_stub_map.apiproxy.RegisterStub(
      'channel',
      channel_service_stub.ChannelServiceStub(request_data=request_data))

  datastore = datastore_distributed.DatastoreDistributed(
      app_id, datastore_path, trusted=trusted)

  apiproxy_stub_map.apiproxy.ReplaceStub(
      'datastore_v3', datastore)

  apiproxy_stub_map.apiproxy.RegisterStub(
      'datastore_v4',
      datastore_v4_stub.DatastoreV4Stub(app_id))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'file',
      file_service_stub.FileServiceStub(blob_storage))

  serve_address = os.environ['NGINX_HOST']
  try:
    from google.appengine.api.images import images_stub
  except ImportError:

    logging.warning('Could not initialize images API; you are likely missing '
                    'the Python "PIL" module.')
    # We register a stub which throws a NotImplementedError for most RPCs.
    from google.appengine.api.images import images_not_implemented_stub
    apiproxy_stub_map.apiproxy.RegisterStub(
        'images',
        images_not_implemented_stub.ImagesNotImplementedServiceStub(
            host_prefix=images_host_prefix))
  else:
    host_prefix = 'http://{}'.format(serve_address)
    apiproxy_stub_map.apiproxy.RegisterStub(
        'images',
        images_stub.ImagesServiceStub(host_prefix=host_prefix))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'logservice',
      logservice_stub.LogServiceStub(persist=True))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'mail',
      mail_stub.MailServiceStub(mail_smtp_host,
                                mail_smtp_port,
                                mail_smtp_user,
                                mail_smtp_password,
                                enable_sendmail=mail_enable_sendmail,
                                show_mail_body=mail_show_mail_body))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'memcache',
      memcache_distributed.MemcacheService(app_id))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'search',
      appscale_search_stub.SearchServiceStub(app_id=app_id))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'modules',
      modules_stub.ModulesServiceStub(request_data))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'system',
      system_stub.SystemServiceStub(request_data=request_data))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'taskqueue',
      taskqueue_distributed.TaskQueueServiceStub(app_id, serve_address))

  urlmatchers_to_fetch_functions = []
  urlmatchers_to_fetch_functions.extend(
      gcs_dispatcher.URLMATCHERS_TO_FETCH_FUNCTIONS)
  apiproxy_stub_map.apiproxy.RegisterStub(
      'urlfetch',
      urlfetch_stub.URLFetchServiceStub(
          urlmatchers_to_fetch_functions=urlmatchers_to_fetch_functions))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'user',
      user_service_stub.UserServiceStub(login_url=user_login_url,
                                        logout_url=user_logout_url,
                                        request_data=request_data))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'xmpp',
      xmpp_service_real.XmppService(xmpp_path, domain=xmpp_domain,
                                    uaserver=uaserver_path))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'matcher',
      prospective_search_stub.ProspectiveSearchStub(
          matcher_prospective_search_path,
          apiproxy_stub_map.apiproxy.GetStub('taskqueue')))

  apiproxy_stub_map.apiproxy.RegisterStub(
      'remote_socket',
      _remote_socket_stub.RemoteSocketServiceStub())


def maybe_convert_datastore_file_stub_data_to_sqlite(app_id, filename):
  if not os.access(filename, os.R_OK | os.W_OK):
    return
  try:
    with open(filename, 'rb') as f:
      if f.read(16) == 'SQLite format 3\x00':
        return
  except (IOError, OSError):
    return
  try:
    _convert_datastore_file_stub_data_to_sqlite(app_id, filename)
  except:
    logging.exception('Failed to convert datastore file stub data to sqlite.')
    raise


def _convert_datastore_file_stub_data_to_sqlite(app_id, datastore_path):
  logging.info('Converting datastore stub data to sqlite.')
  previous_stub = apiproxy_stub_map.apiproxy.GetStub('datastore_v3')
  try:
    apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
    datastore_stub = datastore_file_stub.DatastoreFileStub(
        app_id, datastore_path, trusted=True, save_changes=False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', datastore_stub)

    entities = _fetch_all_datastore_entities()
    sqlite_datastore_stub = datastore_sqlite_stub.DatastoreSqliteStub(
        app_id, datastore_path + '.sqlite', trusted=True)
    apiproxy_stub_map.apiproxy.ReplaceStub('datastore_v3',
                                           sqlite_datastore_stub)
    datastore.Put(entities)
    sqlite_datastore_stub.Close()
  finally:
    apiproxy_stub_map.apiproxy.ReplaceStub('datastore_v3', previous_stub)

  shutil.copy(datastore_path, datastore_path + '.filestub')
  os.remove(datastore_path)
  shutil.move(datastore_path + '.sqlite', datastore_path)
  logging.info('Datastore conversion complete. File stub data has been backed '
               'up in %s', datastore_path + '.filestub')


def _fetch_all_datastore_entities():
  """Returns all datastore entities from all namespaces as a list."""
  all_entities = []
  for namespace in datastore.Query('__namespace__').Run():
    namespace_name = namespace.key().name()
    for kind in datastore.Query('__kind__', namespace=namespace_name).Run():
      all_entities.extend(
          datastore.Query(kind.key().name(), namespace=namespace_name).Run())
  return all_entities


def test_setup_stubs(
    request_data=None,
    app_id='myapp',
    application_root='/tmp/root',
    trusted=False,
    blobstore_path='/dev/null',
    datastore_consistency=None,
    datastore_path=':memory:',
    datastore_require_indexes=False,
    datastore_auto_id_policy=datastore_stub_util.SCATTERED,
    images_host_prefix='http://localhost:8080',
    logs_path=':memory:',
    mail_smtp_host='',
    mail_smtp_port=25,
    mail_smtp_user='',
    mail_smtp_password='',
    mail_enable_sendmail=False,
    mail_show_mail_body=False,
    matcher_prospective_search_path='/dev/null',
    search_index_path=None,
    taskqueue_auto_run_tasks=False,
    taskqueue_default_http_server='http://localhost:8080',
    user_login_url='/_ah/login?continue=%s',
    user_logout_url='/_ah/login?continue=%s',
    default_gcs_bucket_name=None,
    uaserver_path='localhost',
    xmpp_path='localhost',
    xmpp_domain='localhost',
    app_identity_location=None):
  """Similar to setup_stubs with reasonable test defaults and recallable."""

  # Reset the stub map between requests because a stub map only allows a
  # stub to be added once.
  apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()

  if datastore_consistency is None:
    datastore_consistency = (
        datastore_stub_util.PseudoRandomHRConsistencyPolicy())

  setup_stubs(request_data,
              app_id,
              application_root,
              trusted,
              blobstore_path,
              datastore_consistency,
              datastore_path,
              datastore_require_indexes,
              datastore_auto_id_policy,
              images_host_prefix,
              logs_path,
              mail_smtp_host,
              mail_smtp_port,
              mail_smtp_user,
              mail_smtp_password,
              mail_enable_sendmail,
              mail_show_mail_body,
              matcher_prospective_search_path,
              search_index_path,
              taskqueue_auto_run_tasks,
              taskqueue_default_http_server,
              user_login_url,
              user_logout_url,
              default_gcs_bucket_name,
              uaserver_path,
              xmpp_path,
              xmpp_domain,
              app_identity_location)


def cleanup_stubs():
  """Do any necessary stub cleanup e.g. saving data."""
  # Not necessary in AppScale, since the API services exist outside of the
  # AppServer.
  pass


def main():
  """Parses command line options and launches the API server."""
  shutdown.install_signal_handlers()

  # Initialize logging early -- otherwise some library packages may
  # pre-empt our log formatting.  NOTE: the level is provisional; it may
  # be changed based on the --debug flag.
  logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')

  options = cli_parser.create_command_line_parser(
      cli_parser.API_SERVER_CONFIGURATION).parse_args()
  logging.getLogger().setLevel(
      constants.LOG_LEVEL_TO_PYTHON_CONSTANT[options.dev_appserver_log_level])

  # Parse the application configuration if config_paths are provided, else
  # provide sensible defaults.
  if options.config_paths:
    app_config = application_configuration.ApplicationConfiguration(
        options.config_paths, options.app_id)
    app_id = app_config.app_id
    app_root = app_config.modules[0].application_root
  else:
    app_id = (options.app_id if
              options.app_id else DEFAULT_API_SERVER_APP_ID)
    app_root = tempfile.mkdtemp()

  # pylint: disable=protected-access
  # TODO: Rename LocalFakeDispatcher or re-implement for api_server.py.
  request_info = wsgi_request_info.WSGIRequestInfo(
      request_info_lib._LocalFakeDispatcher())
  # pylint: enable=protected-access

  os.environ['APPLICATION_ID'] = app_id
  os.environ['APPNAME'] = app_id
  os.environ['NGINX_HOST'] = options.nginx_host

  def request_context(environ):
      return request_info.request(environ, None)

  server = create_api_server(
      request_info=request_info,
      storage_path=get_storage_path(options.storage_path, app_id),
      options=options, app_id=app_id, app_root=app_root,
      request_context=request_context)

  if options.pidfile:
      with open(options.pidfile, 'w') as pidfile:
          pidfile.write(str(os.getpid()))

  try:
    server.start()
    shutdown.wait_until_shutdown()
  finally:
    server.quit()


if __name__ == '__main__':
  main()
