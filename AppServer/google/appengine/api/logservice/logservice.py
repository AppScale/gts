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




"""
LogService API.

This module allows apps to flush logs, provide status messages, and
programmatically access their request and application logs.
"""






import base64
import cStringIO
import logging
import os
import re
import sys
import threading
import time
import warnings

from google.net.proto import ProtocolBuffer
from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.logservice import log_service_pb
from google.appengine.api.logservice import logsutil
from google.appengine.datastore import datastore_rpc
from google.appengine.runtime import apiproxy_errors


AUTOFLUSH_ENABLED = True


AUTOFLUSH_EVERY_SECONDS = 60


AUTOFLUSH_EVERY_BYTES = 4096


AUTOFLUSH_EVERY_LINES = 50


MAX_ITEMS_PER_FETCH = 1000


LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_ERROR = 3
LOG_LEVEL_CRITICAL = 4


MODULE_ID_RE_STRING = r'(?!-)[a-z\d\-]{1,63}'


MODULE_VERSION_RE_STRING = r'(?!-)[a-z\d\-]{1,100}'
_MAJOR_VERSION_ID_PATTERN = r'^(?:(?:(%s):)?)(%s)$' % (MODULE_ID_RE_STRING,
                                                       MODULE_VERSION_RE_STRING)

_MAJOR_VERSION_ID_RE = re.compile(_MAJOR_VERSION_ID_PATTERN)

_REQUEST_ID_PATTERN = r'^[\da-fA-F]+$'
_REQUEST_ID_RE = re.compile(_REQUEST_ID_PATTERN)


class Error(Exception):
  """Base error class for this module."""


class InvalidArgumentError(Error):
  """Function argument has invalid value."""


class TimeoutError(Error):
  """Requested timeout for fetch() call has expired while iterating results."""

  def __init__(self, msg, offset, last_end_time):
    Error.__init__(self, msg)
    self.__offset = offset
    self.__last_end_time = last_end_time

  @property
  def offset(self):
    """Binary offset indicating the current position in the result stream.

    May be submitted to future Log read requests to continue iterating logs
    starting exactly where this iterator left off.

    Returns:
        A byte string representing an offset into the log stream, or None.
    """
    return self.__offset

  @property
  def last_end_time(self):
    """End time of the last request examined prior to the timeout, or None.

    Returns:
        A float representing the completion time in seconds since the Unix
        epoch of the last request examined.
    """
    return self.__last_end_time


class LogsBuffer(object):
  """Threadsafe buffer for storing and periodically flushing app logs."""

  _MAX_FLUSH_SIZE = int(1e6)
  _MAX_LINE_SIZE = _MAX_FLUSH_SIZE
  assert _MAX_LINE_SIZE <= _MAX_FLUSH_SIZE

  def __init__(self, stream=None, stderr=False):
    """Initializes the buffer, which wraps the given stream or sys.stderr.

    The state of the LogsBuffer is protected by a separate lock.  The lock is
    acquired before any variables are mutated or accessed, and released
    afterward.  A recursive lock is used so that a single thread can acquire the
    lock multiple times, and release it only when an identical number of
    'unlock()' calls have been performed.

    Args:
      stream: A file-like object to store logs. Defaults to a cStringIO object.
      stderr: If specified, use sys.stderr as the underlying stream.
    """
    self._stderr = stderr
    if self._stderr:
      assert stream is None
    else:
      self._stream = stream or cStringIO.StringIO()
    self._lock = threading.RLock()
    self._reset()

  def _lock_and_call(self, method, *args):
    """Calls 'method' while holding the buffer lock."""
    self._lock.acquire()
    try:
      return method(*args)
    finally:
      self._lock.release()

  def stream(self):
    """Returns the underlying file-like object used to buffer logs."""
    if self._stderr:


      return sys.stderr
    else:
      return self._stream

  def lines(self):
    """Returns the number of log lines currently buffered."""
    return self._lock_and_call(lambda: self._lines)

  def bytes(self):
    """Returns the size of the log buffer, in bytes."""
    return self._lock_and_call(lambda: self._bytes)

  def age(self):
    """Returns the number of seconds since the log buffer was flushed."""
    return self._lock_and_call(lambda: time.time() - self._flush_time)

  def flush_time(self):
    """Returns last time that the log buffer was flushed."""
    return self._lock_and_call(lambda: self._flush_time)

  def contents(self):
    """Returns the contents of the logs buffer."""
    return self._lock_and_call(self._contents)

  def _contents(self):
    """Internal version of contents() with no locking."""
    try:
      return self.stream().getvalue()
    except AttributeError:


      return ''

  def reset(self):
    """Resets the buffer state, without clearing the underlying stream."""
    self._lock_and_call(self._reset)

  def _reset(self):
    """Internal version of reset() with no locking."""
    contents = self._contents()
    self._bytes = len(contents)
    self._lines = len(contents.split('\n')) - 1
    self._flush_time = time.time()
    self._request = logsutil.RequestID()

  def clear(self):
    """Clears the contents of the logs buffer, and resets autoflush state."""
    self._lock_and_call(self._clear)

  def _clear(self):
    """Internal version of clear() with no locking."""
    if self._bytes > 0:
      self.stream().truncate(0)
    self._reset()

  def close(self):
    """Closes the underlying stream, flushing the current contents."""
    self._lock_and_call(self._close)

  def _close(self):
    """Internal version of close() with no locking."""
    self._flush()
    self.stream().close()

  def parse_logs(self):
    """Parse the contents of the buffer and return an array of log lines."""
    return logsutil.ParseLogs(self.contents())

  def write(self, line):
    """Writes a line to the logs buffer."""
    return self._lock_and_call(self._write, line)

  def writelines(self, seq):
    """Writes each line in the given sequence to the logs buffer."""
    for line in seq:
      self.write(line)

  def _write(self, line):
    """Writes a line to the logs buffer."""
    if self._request != logsutil.RequestID():


      self._reset()
    self.stream().write(line)

    self._lines += 1
    self._bytes += len(line)
    self._autoflush()

  @staticmethod
  def _truncate(line, max_length=_MAX_LINE_SIZE):
    """Truncates a potentially long log down to a specified maximum length."""
    if len(line) > max_length:
      original_length = len(line)
      suffix = '...(length %d)' % original_length
      line = line[:max_length - len(suffix)] + suffix
    return line

  def flush(self):
    """Flushes the contents of the logs buffer.

    This method holds the buffer lock until the API call has finished to ensure
    that flush calls are performed in the correct order, so that log messages
    written during the flush call aren't dropped or accidentally wiped, and so
    that the other buffer state variables (flush time, lines, bytes) are updated
    synchronously with the flush.
    """
    self._lock_and_call(self._flush)

  def _flush(self):
    """Internal version of flush() with no locking."""
    logs = self.parse_logs()
    self._clear()

    first_iteration = True
    while logs or first_iteration:
      first_iteration = False
      request = log_service_pb.FlushRequest()
      group = log_service_pb.UserAppLogGroup()
      byte_size = 0
      n = 0
      for entry in logs:


        if len(entry[2]) > LogsBuffer._MAX_LINE_SIZE:
          entry = list(entry)
          entry[2] = self._truncate(entry[2], LogsBuffer._MAX_LINE_SIZE)


        if byte_size + len(entry[2]) > LogsBuffer._MAX_FLUSH_SIZE:
          break
        line = group.add_log_line()
        line.set_timestamp_usec(entry[0])
        line.set_level(entry[1])
        line.set_message(entry[2])
        byte_size += 1 + group.lengthString(line.ByteSize())
        n += 1
      assert n > 0 or not logs
      logs = logs[n:]
      request.set_logs(group.Encode())
      response = api_base_pb.VoidProto()
      apiproxy_stub_map.MakeSyncCall('logservice', 'Flush', request, response)

  def autoflush(self):
    """Flushes the buffer if certain conditions have been met."""
    self._lock_and_call(self._autoflush)

  def _autoflush(self):
    """Internal version of autoflush() with no locking."""
    if not self.autoflush_enabled():
      return

    if ((AUTOFLUSH_EVERY_SECONDS and self.age() >= AUTOFLUSH_EVERY_SECONDS) or
        (AUTOFLUSH_EVERY_LINES and self.lines() >= AUTOFLUSH_EVERY_LINES) or
        (AUTOFLUSH_EVERY_BYTES and self.bytes() >= AUTOFLUSH_EVERY_BYTES)):
      self._flush()

  def autoflush_enabled(self):
    """Indicates if the buffer will periodically flush logs during a request."""
    return AUTOFLUSH_ENABLED



_global_buffer = LogsBuffer(stderr=True)


def logs_buffer():
  """Returns the LogsBuffer used by the current request."""




  return _global_buffer


def write(message):
  """Adds 'message' to the logs buffer, and checks for autoflush.

  Args:
    message: A message (string) to be written to application logs.
  """
  logs_buffer().write(message)


def clear():
  """Clear the logs buffer and reset the autoflush state."""
  logs_buffer().clear()


def autoflush():
  """If AUTOFLUSH conditions have been met, performs a Flush API call."""
  logs_buffer().autoflush()


def flush():
  """Flushes log lines that are currently buffered."""
  logs_buffer().flush()


def flush_time():
  """Returns last time that the logs buffer was flushed."""
  return logs_buffer().flush_time()


def log_buffer_age():
  """Returns the number of seconds since the logs buffer was flushed."""
  return logs_buffer().age()


def log_buffer_contents():
  """Returns the contents of the logs buffer."""
  return logs_buffer().contents()


def log_buffer_bytes():
  """Returns the size of the logs buffer, in bytes."""
  return logs_buffer().bytes()


def log_buffer_lines():
  """Returns the number of log lines currently buffered."""
  return logs_buffer().lines()


class _LogQueryResult(object):
  """A container that holds a log request and provides an iterator to read logs.

  A _LogQueryResult object is the standard returned item for a call to fetch().
  It is iterable - each value returned is a log that the user has queried for,
  and internally, it holds a cursor that it uses to fetch more results once the
  current, locally held set, are exhausted.

  Properties:
    _request: A LogReadRequest that contains the parameters the user has set for
      the initial fetch call, which will be updated with a more current cursor
      if more logs are requested.
    _logs: A list of RequestLogs corresponding to logs the user has asked for.
    _read_called: A boolean that indicates if a Read call has even been made
      with the request stored in this object.
  """

  def __init__(self, request, timeout=None):
    """Constructor.

    Args:
      request: A LogReadRequest object that will be used for Read calls.
    """
    self._request = request
    self._logs = []
    self._read_called = False
    self._last_end_time = None
    self._end_time = None
    if timeout is not None:
      self._end_time = time.time() + timeout

  def __iter__(self):
    """Provides an iterator that yields log records one at a time."""
    while True:
      for log_item in self._logs:
        yield RequestLog(log_item)
      if not self._read_called or self._request.has_offset():
        if self._end_time and time.time() >= self._end_time:
          offset = None
          if self._request.has_offset():
            offset = self._request.offset().Encode()
          raise TimeoutError('A timeout occurred while iterating results',
                             offset=offset, last_end_time=self._last_end_time)
        self._read_called = True
        self._advance()
      else:
        break

  def _advance(self):
    """Acquires additional logs via cursor.

    This method is used by the iterator when it has exhausted its current set of
    logs to acquire more logs and update its internal structures accordingly.
    """
    response = log_service_pb.LogReadResponse()

    try:
      apiproxy_stub_map.MakeSyncCall('logservice', 'Read', self._request,
                                     response)
    except apiproxy_errors.ApplicationError, e:
      if e.application_error == log_service_pb.LogServiceError.INVALID_REQUEST:
        raise InvalidArgumentError(e.error_detail)
      raise Error(e.error_detail)

    self._logs = response.log_list()
    self._request.clear_offset()
    if response.has_offset():
      self._request.mutable_offset().CopyFrom(response.offset())
    self._last_end_time = None
    if response.has_last_end_time():
      self._last_end_time = response.last_end_time() / 1e6


class RequestLog(object):
  """Complete log information about a single request to an application."""

  def __init__(self, request_log=None):
    if type(request_log) is str:
      self.__pb = log_service_pb.RequestLog(base64.b64decode(request_log))
    elif request_log.__class__ == log_service_pb.RequestLog:
      self.__pb = request_log
    else:
      self.__pb = log_service_pb.RequestLog()
    self.__lines = []

  def __repr__(self):
    return 'RequestLog(\'%s\')' % base64.b64encode(self.__pb.Encode())

  def __str__(self):
    if self.module_id == 'default':
      return ('<RequestLog(app_id=%s, version_id=%s, request_id=%s)>' %
              (self.app_id, self.version_id, base64.b64encode(self.request_id)))
    else:
      return ('<RequestLog(app_id=%s, module_id=%s, version_id=%s, '
              'request_id=%s)>' %
              (self.app_id, self.module_id, self.version_id,
               base64.b64encode(self.request_id)))

  @property
  def _pb(self):
    return self.__pb

  @property
  def app_id(self):
    """Application id that handled this request, as a string."""
    return self.__pb.app_id()

  @property
  def server_id(self):
    """Module id that handled this request, as a string."""
    logging.warning('The server_id property is deprecated, please use '
                    'the module_id property instead.')
    return self.__pb.module_id()

  @property
  def module_id(self):
    """Module id that handled this request, as a string."""
    return self.__pb.module_id()

  @property
  def version_id(self):
    """Version of the application that handled this request, as a string."""
    return self.__pb.version_id()

  @property
  def request_id(self):
    """Globally unique identifier for a request, based on request start time.

    Request ids for requests which started later will compare greater as
    binary strings than those for requests which started earlier.

    Returns:
        A byte string containing a unique identifier for this request.
    """
    return self.__pb.request_id()

  @property
  def offset(self):
    """Binary offset indicating current position in the result stream.

    May be submitted to future Log read requests to continue immediately after
    this request.

    Returns:
        A byte string representing an offset into the active result stream.
    """
    if self.__pb.has_offset():
      return self.__pb.offset().Encode()
    return None

  @property
  def ip(self):
    """The origin IP address of the request, as a string."""
    return self.__pb.ip()

  @property
  def nickname(self):
    """Nickname of the user that made the request if known and logged in.

    Returns:
        A string representation of the logged in user's nickname, or None.
    """
    if self.__pb.has_nickname():
      return self.__pb.nickname()
    return None

  @property
  def start_time(self):
    """Time at which request was known to have begun processing.

    Returns:
        A float representing the time this request began processing in seconds
        since the Unix epoch.
    """
    return self.__pb.start_time() / 1e6

  @property
  def end_time(self):
    """Time at which request was known to have completed.

    Returns:
        A float representing the request completion time in seconds since the
        Unix epoch.
    """
    return self.__pb.end_time() / 1e6

  @property
  def latency(self):
    """Time required to process request in seconds, as a float."""
    return self.__pb.latency() / 1e6

  @property
  def mcycles(self):
    """Number of machine cycles used to process request, as an integer."""
    return self.__pb.mcycles()

  @property
  def method(self):
    """Request method (GET, PUT, POST, etc), as a string."""
    return self.__pb.method()

  @property
  def resource(self):
    """Resource path on server requested by client.

    For example, http://nowhere.com/app would have a resource string of '/app'.

    Returns:
        A string containing the path component of the request URL.
    """
    return self.__pb.resource()

  @property
  def http_version(self):
    """HTTP version of request, as a string."""
    return self.__pb.http_version()

  @property
  def status(self):
    """Response status of request, as an int."""
    return self.__pb.status()

  @property
  def response_size(self):
    """Size in bytes sent back to client by request, as a long."""
    return self.__pb.response_size()

  @property
  def referrer(self):
    """Referrer URL of request as a string, or None."""
    if self.__pb.has_referrer():
      return self.__pb.referrer()
    return None

  @property
  def user_agent(self):
    """User agent used to make the request as a string, or None."""
    if self.__pb.has_user_agent():
      return self.__pb.user_agent()
    return None

  @property
  def url_map_entry(self):
    """File or class within URL mapping used for request.

    Useful for tracking down the source code which was responsible for managing
    request, especially for multiply mapped handlers.

    Returns:
        A string containing a file or class name.
    """
    return self.__pb.url_map_entry()

  @property
  def combined(self):
    """Apache combined log entry for request.

    The information in this field can be constructed from the rest of
    this message, however, this field is included for convenience.

    Returns:
        A string containing an Apache-style log line in the form documented at
        http://httpd.apache.org/docs/1.3/logs.html.
    """
    return self.__pb.combined()

  @property
  def api_mcycles(self):
    """Number of machine cycles spent in API calls while processing request.

    Deprecated. This value is no longer meaningful.

    Returns:
       Number of API machine cycles used as a long, or None if not available.
    """
    warnings.warn('api_mcycles does not return a meaningful value.',
                  DeprecationWarning, stacklevel=2)
    if self.__pb.has_api_mcycles():
      return self.__pb.api_mcycles()
    return None

  @property
  def host(self):
    """The Internet host and port number of the resource being requested.

    Returns:
        A string representing the host and port receiving the request, or None
        if not available.
    """
    if self.__pb.has_host():
      return self.__pb.host()
    return None

  @property
  def cost(self):
    """The estimated cost of this request, in fractional dollars.

    Returns:
        A float representing an estimated fractional dollar cost of this
        request, or None if not available.
    """
    if self.__pb.has_cost():
      return self.__pb.cost()
    return None

  @property
  def task_queue_name(self):
    """The request's queue name, if generated via the Task Queue API.

    Returns:
        A string containing the request's queue name if relevant, or None.
    """
    if self.__pb.has_task_queue_name():
      return self.__pb.task_queue_name()
    return None

  @property
  def task_name(self):
    """The request's task name, if generated via the Task Queue API.

    Returns:
       A string containing the request's task name if relevant, or None.
    """
    if self.__pb.has_task_name():
      return self.__pb.task_name()

  @property
  def was_loading_request(self):
    """Returns whether this request was a loading request for an instance.

    Returns:
        A bool indicating whether this request was a loading request.
    """
    return bool(self.__pb.was_loading_request())

  @property
  def pending_time(self):
    """Time this request spent in the pending request queue.

    Returns:
        A float representing the time in seconds that this request was pending.
    """
    return self.__pb.pending_time() / 1e6

  @property
  def replica_index(self):
    """The module replica that handled the request as an integer, or None."""
    if self.__pb.has_replica_index():
      return self.__pb.replica_index()
    return None

  @property
  def finished(self):
    """Whether or not this log represents a finished request, as a bool."""
    return bool(self.__pb.finished())

  @property
  def instance_key(self):
    """Mostly-unique identifier for the instance that handled the request.

    Returns:
        A string encoding of an instance key if available, or None.
    """
    if self.__pb.has_clone_key():
      return self.__pb.clone_key()
    return None

  @property
  def app_logs(self):
    """Logs emitted by the application while serving this request.

    Returns:
       A list of AppLog objects representing the log lines for this request, or
       an empty list if none were emitted or the query did not request them.
    """
    if not self.__lines and self.__pb.line_size():
      self.__lines = [AppLog(time=line.time() / 1e6, level=line.level(),
                             message=line.log_message())
                      for line in self.__pb.line_list()]
    return self.__lines

  @property
  def app_engine_release(self):
    """App Engine Infrastructure release that served this request.

    Returns:
       A string containing App Engine version that served this request, or None
       if not available.
    """
    if self.__pb.has_app_engine_release():
      return self.__pb.app_engine_release()
    return None


class AppLog(object):
  """Application log line emitted while processing a request."""

  def __init__(self, time=None, level=None, message=None):
    self._time = time
    self._level = level
    self._message = message

  def __eq__(self, other):
    return (self.time == other.time and self.level and other.level and
            self.message == other.message)

  def __repr__(self):
    return ('AppLog(time=%f, level=%d, message=\'%s\')' %
            (self.time, self.level, self.message))

  @property
  def time(self):
    """Time log entry was made, in seconds since the Unix epoch, as a float."""
    return self._time

  @property
  def level(self):
    """Level or severity of log, as an int."""
    return self._level

  @property
  def message(self):
    """Application-provided log message, as a string."""
    return self._message



_FETCH_KWARGS = frozenset(['prototype_request', 'timeout', 'batch_size',
                           'server_versions'])


@datastore_rpc._positional(0)
def fetch(start_time=None,
          end_time=None,
          offset=None,
          minimum_log_level=None,
          include_incomplete=False,
          include_app_logs=False,
          module_versions=None,
          version_ids=None,
          request_ids=None,
          **kwargs):
  """Returns an iterator yielding an application's request and application logs.

  Logs will be returned by the iterator in reverse chronological order by
  request end time, or by last flush time for requests still in progress (if
  requested).  The items yielded are RequestLog objects, the contents of which
  are accessible via method calls.

  All parameters are optional.

  Args:
    start_time: The earliest request completion or last-update time that
      results should be fetched for, in seconds since the Unix epoch.
    end_time: The latest request completion or last-update time that
      results should be fetched for, in seconds since the Unix epoch.
    offset: A byte string representing an offset into the log stream, extracted
      from a previously emitted RequestLog.  This iterator will begin
      immediately after the record from which the offset came.
    minimum_log_level: An application log level which serves as a filter on the
      requests returned--requests with no application log at or above the
      specified level will be omitted.  Works even if include_app_logs is not
      True.  In ascending order, the available log levels are:
      logservice.LOG_LEVEL_DEBUG, logservice.LOG_LEVEL_INFO,
      logservice.LOG_LEVEL_WARNING, logservice.LOG_LEVEL_ERROR,
      and logservice.LOG_LEVEL_CRITICAL.
    include_incomplete: Whether or not to include requests that have started but
      not yet finished, as a boolean.  Defaults to False.
    include_app_logs: Whether or not to include application level logs in the
      results, as a boolean.  Defaults to False.
    module_versions: A list of tuples of the form (module, version), that
      indicate that the logs for the given module/version combination should be
      fetched.  Duplicate tuples will be ignored.  This kwarg may not be used
      in conjunction with the 'version_ids' kwarg.
    version_ids: A list of version ids whose logs should be queried against.
      Defaults to the application's current version id only.  This kwarg may not
      be used in conjunction with the 'module_versions' kwarg.
    request_ids: If not None, indicates that instead of a time-based scan, logs
      for the specified requests should be returned.  Malformed request IDs will
      cause the entire request to be rejected, while any requests that are
      unknown will be ignored. This option may not be combined with any
      filtering options such as start_time, end_time, offset, or
      minimum_log_level.  version_ids is ignored.  IDs that do not correspond to
      a request log will be ignored.  Logs will be returned in the order
      requested.

  Returns:
    An iterable object containing the logs that the user has queried for.

  Raises:
    InvalidArgumentError: Raised if any of the input parameters are not of the
      correct type.
  """

  args_diff = set(kwargs) - _FETCH_KWARGS
  if args_diff:
    raise InvalidArgumentError('Invalid arguments: %s' % ', '.join(args_diff))

  request = log_service_pb.LogReadRequest()

  request.set_app_id(os.environ['APPLICATION_ID'])

  if start_time is not None:
    if not isinstance(start_time, (float, int, long)):
      raise InvalidArgumentError('start_time must be a float or integer')
    request.set_start_time(long(start_time * 1000000))

  if end_time is not None:
    if not isinstance(end_time, (float, int, long)):
      raise InvalidArgumentError('end_time must be a float or integer')
    request.set_end_time(long(end_time * 1000000))

  if offset is not None:
    try:
      request.mutable_offset().ParseFromString(offset)
    except (TypeError, ProtocolBuffer.ProtocolBufferDecodeError):
      raise InvalidArgumentError('offset must be a string or read-only buffer')

  if minimum_log_level is not None:
    if not isinstance(minimum_log_level, int):
      raise InvalidArgumentError('minimum_log_level must be an int')

    if not minimum_log_level in range(LOG_LEVEL_CRITICAL+1):
      raise InvalidArgumentError("""minimum_log_level must be between 0 and 4
                                 inclusive""")
    request.set_minimum_log_level(minimum_log_level)

  if not isinstance(include_incomplete, bool):
    raise InvalidArgumentError('include_incomplete must be a boolean')
  request.set_include_incomplete(include_incomplete)

  if not isinstance(include_app_logs, bool):
    raise InvalidArgumentError('include_app_logs must be a boolean')
  request.set_include_app_logs(include_app_logs)

  if 'server_versions' in kwargs:
    logging.warning('The server_versions kwarg to the fetch() method is '
                    'deprecated.  Please use the module_versions kwarg '
                    'instead.')
    module_versions = kwargs.pop('server_versions')
  if version_ids and module_versions:
    raise InvalidArgumentError('version_ids and module_versions may not be '
                               'used at the same time.')

  if version_ids is None and module_versions is None:
    module_version = request.add_module_version()
    if os.environ['CURRENT_MODULE_ID'] != 'default':

      module_version.set_module_id(os.environ['CURRENT_MODULE_ID'])
    module_version.set_version_id(
        os.environ['CURRENT_VERSION_ID'].split('.')[0])

  if module_versions:
    if not isinstance(module_versions, list):
      raise InvalidArgumentError('module_versions must be a list')

    req_module_versions = set()
    for entry in module_versions:
      if not isinstance(entry, (list, tuple)):
        raise InvalidArgumentError('module_versions list entries must all be '
                                   'tuples or lists.')
      if len(entry) != 2:
        raise InvalidArgumentError('module_versions list entries must all be '
                                   'of length 2.')
      req_module_versions.add((entry[0], entry[1]))

    for module, version in sorted(req_module_versions):
      req_module_version = request.add_module_version()


      if module != 'default':
        req_module_version.set_module_id(module)
      req_module_version.set_version_id(version)

  if version_ids:
    if not isinstance(version_ids, list):
      raise InvalidArgumentError('version_ids must be a list')
    for version_id in version_ids:
      if not _MAJOR_VERSION_ID_RE.match(version_id):
        raise InvalidArgumentError(
            'version_ids must only contain valid major version identifiers')
      request.add_module_version().set_version_id(version_id)

  if request_ids is not None:
    if not isinstance(request_ids, list):
      raise InvalidArgumentError('request_ids must be a list')
    if not request_ids:
      raise InvalidArgumentError('request_ids must not be empty')
    if len(request_ids) != len(set(request_ids)):
      raise InvalidArgumentError('request_ids must not contain duplicates')
    for request_id in request_ids:
      if not _REQUEST_ID_RE.match(request_id):
        raise InvalidArgumentError(
            '%s is not a valid request log id' % request_id)
    request.request_id_list()[:] = request_ids

  prototype_request = kwargs.get('prototype_request')
  if prototype_request:
    if not isinstance(prototype_request, log_service_pb.LogReadRequest):
      raise InvalidArgumentError('prototype_request must be a LogReadRequest')
    request.MergeFrom(prototype_request)

  timeout = kwargs.get('timeout')
  if timeout is not None:
    if not isinstance(timeout, (float, int, long)):
      raise InvalidArgumentError('timeout must be a float or integer')

  batch_size = kwargs.get('batch_size')
  if batch_size is not None:
    if not isinstance(batch_size, (int, long)):
      raise InvalidArgumentError('batch_size must be an integer')

    if batch_size < 1:
      raise InvalidArgumentError('batch_size must be greater than zero')

    if batch_size > MAX_ITEMS_PER_FETCH:
      raise InvalidArgumentError('batch_size specified is too large')
    request.set_count(batch_size)

  return _LogQueryResult(request, timeout=timeout)
