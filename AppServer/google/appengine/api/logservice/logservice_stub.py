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




"""Stub implementation for Log Service that utilizes the Datastore.

Logs can be flushed, which will store them in the Datastore, and retrieved for
use by the user. Users can retrieve logs along a number of different query
parameters, including the time the request began, whether or not
application-level logs should be included, and so on.
"""




import os
import time

from google.appengine.api import apiproxy_stub
from google.appengine.api import datastore_errors
from google.appengine.api import logservice
from google.appengine.api import namespace_manager
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.logservice import logservice
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors


LOG_NAMESPACE = '_Logs'
_FUTURE_TIME = 2**34
_REQUEST_TIME = 0
_CURRENT_REQUEST_ID_HASH = ''


def _get_request_id():
  """Returns the request ID bound to this request.

  Specifically, we see if the request ID hash has changed since the last time we
  have examined it. If so, we generate a new ID based on the current time.
  Regardless, we return a string whose value decreases w.r.t. time, so that
  values stored in the Datastore will be sorted from newest to oldest.
  """
  global _CURRENT_REQUEST_ID_HASH
  global _REQUEST_TIME
  request_id_hash = os.environ.get('REQUEST_ID_HASH', '')

  if _CURRENT_REQUEST_ID_HASH != request_id_hash:
    _CURRENT_REQUEST_ID_HASH = request_id_hash
    _REQUEST_TIME = time.time()

  return str(int((_FUTURE_TIME - _REQUEST_TIME) * 1000000))


def _flush_logs_buffer():
  """Empties all logs stored within the globally-held logs buffer."""
  logservice.logs_buffer().flush()


def _run_in_namespace(f, *args):
  """Calls 'f' while within the logs namespace.

  This is done by methods that need to read or write log data via the Datastore,
  as they operate within the LOG_NAMESPACE namespace. Utilizing this namespace
  ensures that the user doesn't accidentally receive logs in their query results
  or have their Datastore Viewer cluttered by it unless they specifically ask
  for it via that namespace.

  Args:
    f: The function that should be called within the logs namespace.
    *args: A list of arguments that f should be called with.

  Returns:
    The result of f(*args).
  """
  namespace = namespace_manager.get_namespace()
  try:
    namespace_manager.set_namespace(LOG_NAMESPACE)
    return f(*args)
  finally:
    namespace_manager.set_namespace(namespace)


class _LogLine(db.Model):
  """Representation of an application-level log line."""
  time = db.IntegerProperty()
  level = db.IntegerProperty()
  message = db.BlobProperty()


class _LogRecord(db.Model):
  """Representation of the logging information for a single web request."""
  app_id = db.StringProperty()
  version_id = db.StringProperty()
  ip = db.StringProperty()
  nickname = db.StringProperty()
  request_id = db.StringProperty()
  start_time = db.IntegerProperty()
  end_time = db.IntegerProperty()
  latency = db.IntegerProperty()
  mcycles = db.IntegerProperty()
  method = db.StringProperty()
  resource = db.TextProperty()
  status = db.IntegerProperty()
  response_size = db.IntegerProperty()
  http_version = db.StringProperty()
  host = db.StringProperty()
  user_agent = db.StringProperty()
  finished = db.BooleanProperty()
  app_logs = db.ListProperty(db.Key)

  @classmethod
  def get_or_create(cls):
    """Returns the LogRecord for this request, creating it if needed."""
    return cls.get_or_insert(str(_get_request_id()))

  def fill_in_log(self, request, log, app_logs):
    """Fills in fields in a given RequestLog from a LogReadRequest's fields.

    Application-level logs are stored in the Datastore as _LogLines, so this
    method also grabs those items, resolves them, and stores them in the given
    RequestLog.

    Args:
      request: A LogReadRequest, containing the filters that the user has
        specified to use for their request.
      log: A RequestLog whose fields will be overriden with those from request.
      app_logs: The application-level logs associated with the given log.
    """
    log.set_app_id(self.app_id)
    log.set_version_id(self.version_id)
    log.set_ip(self.ip)
    log.set_nickname(self.nickname)
    log.set_request_id(str(self.key()))
    log.set_start_time(self.start_time)
    log.set_end_time(self.end_time)
    log.set_latency(self.latency)
    log.set_mcycles(self.mcycles)
    log.set_method(self.method)
    log.set_resource(self.resource)
    log.set_status(self.status)
    log.set_response_size(self.response_size)
    log.set_http_version(self.http_version)
    if self.host is not None:
      log.set_host(self.host)
    if self.user_agent is not None:
      log.set_user_agent(self.user_agent)
    log.set_finished(self.finished)
    log.set_url_map_entry('')


    time_seconds = (self.end_time or self.start_time) / 10**6
    date_string = time.strftime('%d/%b/%Y:%T %z', time.localtime(time_seconds))
    log.set_combined('%s - %s [%s] \"%s %s %s\" %d %d - \"%s\"' %
                     (self.ip, self.nickname, date_string, self.method,
                      self.resource, self.http_version, self.status or 0,
                      self.response_size or 0, self.user_agent))

    if request.include_app_logs():
      for app_log in app_logs:
        log_line = log.add_line()
        log_line.set_time(app_log.time)
        log_line.set_level(app_log.level)
        log_line.set_log_message(app_log.message)


class RequestLogWriter(object):
  """A helper class that writes log lines to the Datastore.

  Writes log lines to the Datastore on behalf of the SDK's dev_appserver so that
  they can be queried later via fetch(). Each of three methods write the
  information for a given request:
  1) write_request_info: Writes the information found at the beginning of the
    request.
  2) write: Writes the information found at the end of the request.
  3) write_app_logs: Writes application-level logs emitted by the application
    (if any).

  Properties:
    app_id: A string representing the application ID that this request
      corresponds to.
    version_id: A string representing the version ID that this request
      corresponds to.
    request_id: An integer that represents a monotonically increasing request
      number. The actual value of the request ID doesn't matter - what is
      important is that later requests have larger request IDs than earlier
      requests.
    db_key: A string that will be used as the key for the LogRecord associated
      with this request. Requests are sorted in descending order w.r.t. time,
      so we just set the key to be computed by a function that decreases w.r.t.
      time.
    log_msgs: A list that contains the application-level logs generated by
      request. Currently this is not implemented - once we get better
      integration with the LogService API, this will be remedied.
    method: A string corresponding to the HTTP method for this request.
    resource: A string corresponding to the relative URL for this request.
    http_version: A string corresponding to the HTTP version for this request.
      Note that the entire HTTP version is stored here (e.g., "HTTP/1.1" and
      not just "1.1").
  """

  def __init__(self, persist=False):
    """Constructor.

    Args:
      persist: If true, log records should be durably persisted.
    """
    self.persist = persist

  def write_request_info(self, ip, app_id, version_id, nickname, user_agent,
                         host, start_time=None, end_time=None):
    """Writes a single request log with currently known information.

    Args:
      ip: The user's IP address.
      app_id: A string representing the application ID that this request
        corresponds to.
      version_id: A string representing the version ID that this request
        corresponds to.
      nickname: A string representing the user that has made this request (that
        is, the user's nickname, e.g., 'foobar' for a user logged in as
        'foobar@gmail.com').
      user_agent: A string representing the agent used to make this request.
      host: A string representing the host that received this request.
      start_time: If specified, a starting time that should be used instead of
        generating one internally (useful for testing).
      end_time: If specified, an ending time that should be used instead of
        generating one internally (useful for testing).
    """
    if not self.persist:
      return















    namespace_manager.set_namespace(LOG_NAMESPACE)
    log = _LogRecord.get_or_create()
    log.app_id = app_id

    major_version_id = version_id.split('.')[0]
    log.version_id = major_version_id

    log.ip = ip
    log.nickname = nickname
    log.user_agent = user_agent
    log.host = host

    now_time_usecs = self.get_time_now()
    log.request_id = str(now_time_usecs)

    if start_time:
      log.start_time = start_time
    else:
      log.start_time = now_time_usecs



    log.latency = 0
    log.mcycles = 0

    if end_time:
      log.end_time = end_time
      log.finished = True
    else:
      log.finished = False

    log.app_logs = []
    log.put()

  def get_time_now(self):
    """Get the current time in microseconds since epoch."""
    return int(time.time() * 1000000)

  def write(self, method, resource, status, size, http_version):
    """Writes all request-level information to the Datastore."""
    if self.persist:
      _run_in_namespace(self._write, method, resource, status, size,
                        http_version)

  def _write(self, method, resource, status, size, http_version):
    """Implements write if called by _run_in_namespace."""
    log = _LogRecord.get_or_create()
    log.method = method
    log.resource = resource
    log.status = status
    log.response_size = size
    log.http_version = http_version

    if not log.finished:
      log.end_time = self.get_time_now()
      log.latency = log.end_time - (log.start_time or 0)
      log.finished = True

    log.put()


class LogServiceStub(apiproxy_stub.APIProxyStub):
  """Python stub for Log Service service."""


  __DEFAULT_READ_COUNT = 20

  def __init__(self, persist=False):
    """Constructor."""
    super(LogServiceStub, self).__init__('logservice')
    self.persist = persist
    self.status = None

  def _Dynamic_Flush(self, request, unused_response):
    """Writes application-level log messages for a request to the Datastore."""
    if self.persist:
      group = log_service_pb.UserAppLogGroup(request.logs())
      new_app_logs = self.put_log_lines(group.log_line_list())
      self.write_app_logs(new_app_logs)

  def put_log_lines(self, lines):
    """Creates application-level log lines and stores them in the Datastore.

    Args:
      lines: A list of LogLines that each correspond to an application-level log
        line.
    Returns:
      A list of Keys corresponding to the newly-stored log lines.
    """
    return _run_in_namespace(self._put_log_lines, lines)

  def _put_log_lines(self, lines):
    """Implements put_log_lines if called by _run_in_namespace."""
    db_models = []

    for app_log in lines:
      db_log_line = _LogLine(time=app_log.timestamp_usec(),
                             level=app_log.level(),
                             message=app_log.message())
      db_models.append(db_log_line)

    return db.put(db_models)

  def write_app_logs(self, new_app_logs):
    """Writes application-level logs for a given request to the Datastore."""
    return _run_in_namespace(self._write_app_logs, new_app_logs)

  def _write_app_logs(self, new_app_logs):
    """Implements write_app_logs if called by _run_in_namespace."""
    log = _LogRecord.get_or_create()
    for app_log in new_app_logs:
      log.app_logs.append(app_log)
    log.put()

  def _Dynamic_SetStatus(self, request, unused_response):
    """Record the recently seen status."""
    self.status = request.status()

  def _Dynamic_Read(self, request, response):
    """Handler for LogRead RPC call.

    Our stub implementation stores and retrieves log data via the Datastore,
    but because query parameters do not persist in the cursor, we create an
    internal cursor that also contains these extra parameters. If it is
    present, we parse out these parameters, and conversely, when we create the
    cursor, we are sure to include the parameters back in for later retrieval.

    Args:
      request: A LogReadRequest object.
      response: A LogReadResponse object.
    """
    _run_in_namespace(self.__Dynamic_Read, request, response)

  def __Dynamic_Read(self, request, response):
    """Implements _Dynamic_Read if called by _run_in_namespace."""






    response.clear_offset()


    if request.version_id_size() != 1:
      raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)

    if (request.request_id_size() and
        (request.has_start_time() or request.has_end_time() or
         request.has_offset())):
      raise apiproxy_errors.ApplicationError(
          log_service_pb.LogServiceError.INVALID_REQUEST)


    if request.request_id_size():
      results = []
      try:
        results = db.get(request.request_id_list())
      except datastore_errors.BadKeyError:

        for request_id in request.request_id_list():
          try:
            results.append(db.get(request_id))
          except datastore_errors.BadKeyError:
            pass
      for result in results:
        if result.version_id != request.version_id(0):
          continue
        log = response.add_log()
        app_logs = db.get(result.app_logs)
        result.fill_in_log(request, log, app_logs)
      return

    query = db.Query(_LogRecord)

    if request.has_offset():
      query.filter('__key__ > ', db.Key(request.offset().request_id()))

    if request.has_count():
      limit = request.count()
    else:
      limit = LogServiceStub.__DEFAULT_READ_COUNT

    versions = request.version_id_list()






    index = 0
    for result in query.run(limit=limit):
      index += 1
      start = result.start_time

      if request.has_start_time():
        if request.start_time() > start:
          continue

      if request.has_end_time():
        if request.end_time() <= start:
          continue



      if not request.include_incomplete() and not result.finished:
        continue

      if result.version_id not in versions:
        continue




      app_logs = db.get(result.app_logs)
      if request.has_minimum_log_level():
        for app_log in app_logs:
          if app_log.level >= request.minimum_log_level():
            break
        else:
          continue

      log = response.add_log()
      result.fill_in_log(request, log, app_logs)
      log.mutable_offset().set_request_id(str(result.key()))

    if index == limit:
      response.mutable_offset().set_request_id(str(result.key()))

  def get_status(self):
    """Internal method for dev_appserver to read the status."""
    return self.status
