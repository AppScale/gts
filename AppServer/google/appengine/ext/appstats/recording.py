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




"""Userland RPC instrumentation for App Engine."""

from __future__ import with_statement


import datetime
import logging
import os
import random
import re
import sys
import threading
import time
import warnings

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import lib_config
from google.appengine.api import memcache
from google.appengine.api import quota
from google.appengine.api import users

from google.appengine.ext.appstats import datamodel_pb
from google.appengine.ext.appstats import formatting


class ConfigDefaults(object):
  """Configurable constants.

  To override appstats configuration valuess, define values like this
  in your appengine_config.py file (in the root of your app):

    appstats_MAX_STACK = 5
    appstats_MAX_LOCALS = 0

  More complete documentation for all configurable constants can be
  found in the file sample_appengine_config.py.
  """

  DEBUG = False
  DUMP_LEVEL = -1


  KEY_DISTANCE = 100
  KEY_MODULUS = 1000


  KEY_NAMESPACE = '__appstats__'
  KEY_PREFIX = '__appstats__'
  KEY_TEMPLATE = ':%06d'
  PART_SUFFIX = ':part'
  FULL_SUFFIX = ':full'
  LOCK_SUFFIX = '<lock>'


  MAX_STACK = 10
  MAX_LOCALS = 10
  MAX_REPR = 100
  MAX_DEPTH = 10



  RE_STACK_BOTTOM = r'dev_appserver\.py'
  RE_STACK_SKIP = r'recording\.py|apiproxy_stub_map\.py'


  LOCK_TIMEOUT = 1



  TZOFFSET = 8*3600


  stats_url = '/_ah/stats'


  RECORD_FRACTION = 1.0










  FILTER_LIST = []



  def should_record(env):
    """Return a bool indicating whether we should record this request.

    Args:
      env: The CGI or WSGI environment dict.

    Returns:
      True if this request should be recorded, False if not.

    The default implementation returns True iff the request matches
    FILTER_LIST (see above) *and* random.random() < RECORD_FRACTION.
    """
    if config.FILTER_LIST:
      if config.DEBUG:
        logging.debug('FILTER_LIST: %r', config.FILTER_LIST)
      for filter_dict in config.FILTER_LIST:
        for key, regex in filter_dict.iteritems():
          negated = isinstance(regex, str) and regex.startswith('!')
          if negated:
            regex = regex[1:]
          value = env.get(key, '')
          if bool(re.match(regex, value)) == negated:
            if config.DEBUG:
              logging.debug('No match on %r for %s=%r', regex, key, value)
            break
        else:
          if config.DEBUG:
            logging.debug('Match on %r', filter_dict)
          break
      else:
        if config.DEBUG:
          logging.debug('Non-empty FILTER_LIST, but no filter matches')
        return False
    if config.RECORD_FRACTION >= 1.0:
      return True
    return random.random() < config.RECORD_FRACTION

  def normalize_path(path):
    """Transform a path to a canonical key for that path.

    Args:
      path: A string, e.g. '/foo/bar/12345'.

    Returns:
      A string derived from path, e.g. '/foo/bar/X'.
    """
    return path

  def extract_key(request):
    """Extract a canonical key from a StatsProto instance.

    This default implementation calls config.normalize_path() on the
    path returned by request.http_path(), and then prepends the HTTP
    method and a space, unless the method is 'GET', in which case the
    method and the space are omitted (so as to display a more compact
    key in the user interface).

    Args:
      request: a StatsProto instance.

    Returns:
      A string, typically something like '/foo/bar/X' or 'POST /foo/bar'.
    """
    key = config.normalize_path(request.http_path())
    if request.http_method() != 'GET':
      key = '%s %s' % (request.http_method(), key)
    return key



config = lib_config.register('appstats', ConfigDefaults.__dict__)


class Recorder(object):
  """In-memory state for the current request.

  An instance is created soon after the request is received, and
  set as the Recorder for the current request in the
  RequestLocalRecorderProxy in the global variable 'recorder_proxy'.  It
  collects information about the request and about individual RPCs
  made during the request, until just before the response is sent out,
  when the recorded information is saved to memcache by calling the
  save() method.
  """

  def __init__(self, env):
    """Constructor.

    Args:
      env: A dict giving the CGI or WSGI environment.
    """
    self.env = dict(kv for kv in env.iteritems() if isinstance(kv[1], str))
    self.start_timestamp = time.time()
    self.http_status = 0
    self.end_timestamp = self.start_timestamp
    self.traces = []
    self.pending = {}
    self.overhead = (time.time() - self.start_timestamp)
    self._lock = threading.Lock()



  def http_method(self):
    """Return the request method, e.g. 'GET' or 'POST'."""
    return self.env.get('REQUEST_METHOD', 'GET')

  def http_path(self):
    """Return the request path, e.g. '/' or '/foo/bar', excluding the query."""
    return self.env.get('PATH_INFO', '')

  def http_query(self):
    """Return the query string, if any, with '?' prefix.

    If there is no query string, an empty string is returned (i.e. not '?').
    """
    query_string = self.env.get('QUERY_STRING', '')
    if query_string:
      query_string = '?' + query_string
    return query_string

  def record_custom_event(self, label, data=None):
    """Record a custom event.

    Args:
      label: A string to use as event label; a 'custom.' prefix will be added.
      data: Optional value to record.  This can be anything; the value
        will be formatted using format_value() before it is recorded.
    """

    pre_now = time.time()
    sreq = format_value(data)
    now = time.time()
    delta = int(1000 * (now - self.start_timestamp))
    trace = datamodel_pb.IndividualRpcStatsProto()
    self.get_call_stack(trace)
    trace.set_service_call_name('custom.' + label)
    trace.set_request_data_summary(sreq)
    trace.set_start_offset_milliseconds(delta)
    with self._lock:
      self.traces.append(trace)
      self.overhead += (now - pre_now)

  def record_rpc_request(self, service, call, request, response, rpc):
    """Record the request of an RPC call.

    Args:
      service: The service name, e.g. 'memcache'.
      call: The call name, e.g. 'Get'.
      request: The request object.
      response: The response object (ignored).
      rpc: The RPC object; may be None.
    """
    pre_now = time.time()
    sreq = format_value(request)
    now = time.time()
    delta = int(1000 * (now - self.start_timestamp))
    trace = datamodel_pb.IndividualRpcStatsProto()
    self.get_call_stack(trace)
    trace.set_service_call_name('%s.%s' % (service, call))
    trace.set_request_data_summary(sreq)
    trace.set_start_offset_milliseconds(delta)
    with self._lock:
      if rpc is not None:

        self.pending[rpc] = len(self.traces)
      self.traces.append(trace)
      self.overhead += (now - pre_now)

  def record_rpc_response(self, service, call, request, response, rpc):
    """Record the response of an RPC call.

    Args:
      service: The service name, e.g. 'memcache'.
      call: The call name, e.g. 'Get'.
      request: The request object.
      response: The response object (ignored).
      rpc: The RPC object; may be None.

    This first tries to match the request with an unmatched request trace.
    If no matching request trace is found, this is logged as a new trace.
    """
    now = time.time()
    key = '%s.%s' % (service, call)
    delta = int(1000 * (now - self.start_timestamp))
    sresp = format_value(response)
    api_mcycles = 0
    if rpc is not None:
      api_mcycles = rpc.cpu_usage_mcycles


      with self._lock:
        index = self.pending.get(rpc)
        if index is not None:
          del self.pending[rpc]
          if 0 <= index < len(self.traces):
            trace = self.traces[index]
            trace.set_response_data_summary(sresp)
            trace.set_api_mcycles(api_mcycles)
            duration = delta - trace.start_offset_milliseconds()
            trace.set_duration_milliseconds(duration)
            self.overhead += (time.time() - now)
            return
    else:

      with self._lock:
        for trace in reversed(self.traces):
          if (trace.service_call_name() == key and
              not trace.response_data_summary()):
            if config.DEBUG:
              logging.debug('Matched RPC response without rpc object')
            trace.set_response_data_summary(sresp)
            duration = delta - trace.start_offset_milliseconds()
            trace.set_duration_milliseconds(duration)
            self.overhead += (time.time() - now)
            return


    logging.warn('RPC response without matching request')
    trace = datamodel_pb.IndividualRpcStatsProto()
    self.get_call_stack(trace)
    trace.set_service_call_name(key)
    trace.set_request_data_summary(sresp)
    trace.set_start_offset_milliseconds(delta)
    with self._lock:
      self.traces.append(trace)
      self.overhead += (time.time() - now)

  def record_http_status(self, status):
    """Record the HTTP status code and the end time of the HTTP request."""
    try:
      self.http_status = int(status)
    except (ValueError, TypeError):
      self.http_status = 0
    self.end_timestamp = time.time()

  def save(self):
    """Save the recorded data to memcache and log some info.

    This wraps the _save() method, which does the actual work; this
    function just logs the total time it took and some other statistics.
    """
    t0 = time.time()
    with self._lock:
      num_pending = len(self.pending)
    if num_pending:
      logging.warn('Found %d RPC request(s) without matching response '
                   '(presumably due to timeouts or other errors)',
                   num_pending)
    self.dump()
    try:
      key, len_part, len_full = self._save()
    except Exception:
      logging.exception('Recorder.save() failed')
      return
    t1 = time.time()
    link = 'http://%s%s/details?time=%s' % (
      self.env.get('HTTP_HOST', ''),
      config.stats_url,
      int(self.start_timestamp * 1000))
    logging.info('Saved; key: %s, part: %s bytes, full: %s bytes, '
                 'overhead: %.3f + %.3f; link: %s',
                 key, len_part, len_full, self.overhead, t1-t0, link)

  def _save(self):
    """Internal function to save the recorded data to memcache.

    Returns:
      A tuple (key, summary_size, full_size).
    """
    part, full = self.get_both_protos_encoded()
    key = make_key(self.start_timestamp)
    errors = memcache.set_multi({config.PART_SUFFIX: part,
                                 config.FULL_SUFFIX: full},
                                time=36*3600, key_prefix=key,
                                namespace=config.KEY_NAMESPACE)
    if errors:
      logging.warn('Memcache set_multi() error: %s', errors)
    return key, len(part), len(full)

  def get_both_protos_encoded(self):
    """Return a string representing all recorded info an encoded protobuf.

    This calls self.get_full_proto() and calls the .Encode() method of
    the resulting object; if the resulting string is too large, it
    tries a number of increasingly aggressive strategies for chopping
    the data down.
    """
    proto = self.get_summary_proto()
    part_encoded = proto.Encode()
    self.add_full_info_to_proto(proto)
    full_encoded = proto.Encode()
    if len(full_encoded) <= memcache.MAX_VALUE_SIZE:
      return part_encoded, full_encoded
    if config.MAX_LOCALS > 0:

      for trace in proto.individual_stats_list():
        for frame in trace.call_stack_list():
          frame.clear_variables()
      full_encoded = proto.Encode()
      if len(full_encoded) <= memcache.MAX_VALUE_SIZE:
        logging.warn('Full proto too large to save, cleared variables.')
        return part_encoded, full_encoded
    if config.MAX_STACK > 0:

      for trace in proto.individual_stats_list():
        trace.clear_call_stack()
      full_encoded = proto.Encode()
      if len(full_encoded) <= memcache.MAX_VALUE_SIZE:
        logging.warn('Full proto way too large to save, cleared frames.')
        return part_encoded, full_encoded

    logging.warn('Full proto WAY too large to save, clipped to 100 traces.')
    del proto.individual_stats_list()[100:]
    full_encoded = proto.Encode()
    return part_encoded, full_encoded

  def add_full_info_to_proto(self, proto):
    """Update a protobuf representing with additional data."""
    user_email = self.env.get('USER_EMAIL')
    if user_email:
      proto.set_user_email(user_email)
    if self.env.get('USER_IS_ADMIN') == '1':
      proto.set_is_admin(True)
    for key, value in sorted(self.env.iteritems()):
      x = proto.add_cgi_env()
      x.set_key(key)
      x.set_value(value)
    with self._lock:
      proto.individual_stats_list()[:] = self.traces

  def json(self):
    """Return a JSON-ifyable representation of the pertinent data.

    This is for FirePython/FireLogger so we must limit the volume by
    omitting stack traces and environment.  Also, times and megacycles
    are converted to integers representing milliseconds.
    """
    traces = []
    with self._lock:
      for t in self.traces:
        d = {'start': t.start_offset_milliseconds(),
             'call': t.service_call_name(),
             'request': t.request_data_summary(),
             'response': t.response_data_summary(),
             'duration': t.duration_milliseconds(),
             'api': mcycles_to_msecs(t.api_mcycles()),
             }
        traces.append(d)
    data = {
      'start': int(self.start_timestamp * 1000),
      'duration': int((self.end_timestamp - self.start_timestamp) * 1000),
      'overhead': int(self.overhead * 1000),
      'traces': traces,
      }
    return data

  def get_summary_proto_encoded(self):
    """Return a string representing a summary an encoded protobuf.

    This calls self.get_summary_proto() and calls the .Encode()
    method of the resulting object.
    """
    return self.get_summary_proto().Encode()

  def get_summary_proto(self):
    """Return a protobuf representing a summary of this recorder."""
    summary = datamodel_pb.RequestStatProto()
    summary.set_start_timestamp_milliseconds(int(self.start_timestamp * 1000))
    method = self.http_method()
    if method != 'GET':
      summary.set_http_method(method)
    path = self.http_path()
    if path != '/':
      summary.set_http_path(path)
    query = self.http_query()
    if query:
      summary.set_http_query(query)
    status = int(self.http_status)
    if status != 200:
      summary.set_http_status(status)
    duration = int(1000 * (self.end_timestamp - self.start_timestamp))
    summary.set_duration_milliseconds(duration)
    api_mcycles = self.get_total_api_mcycles()
    if api_mcycles:
      summary.set_api_mcycles(api_mcycles)
    summary.set_overhead_walltime_milliseconds(int(self.overhead * 1000))
    rpc_stats = self.get_rpcstats().items()
    rpc_stats.sort(key=lambda x: (-x[1], x[0]))
    for key, value in rpc_stats:
      x = summary.add_rpc_stats()
      x.set_service_call_name(key)
      x.set_total_amount_of_calls(value)
    return summary

  def get_rpcstats(self):
    """Compute RPC statistics (how often each RPC endpoint is called).

    Returns:
      A dict mapping 'service.call' keys to integers giving call counts.
    """
    rpcstats = {}
    with self._lock:
      keys = [trace.service_call_name() for trace in self.traces]
    for key in keys:
      if key in rpcstats:
        rpcstats[key] += 1
      else:
        rpcstats[key] = 1
    return rpcstats

  def get_total_api_mcycles(self):
    """Compute the total amount of API time for all RPCs.

    Returns:
      An integer expressing megacycles.
    """
    with self._lock:
      traces_mc = [trace.api_mcycles() for trace in self.traces]
    mcycles = 0
    for trace_mc in traces_mc:
      if isinstance(trace_mc, int):
        mcycles += trace_mc
    return mcycles

  def dump(self, level=None):
    """Log the recorded data, for debugging.

    This logs messages using logging.info().  The amount of data
    logged is controlled by the level argument, which defaults to
    config.DUMP_LEVEL; if < 0 (the default) nothing is logged.
    """
    if level is None:
      level = config.DUMP_LEVEL
    if level < 0:
      return

    logging.info('APPSTATS: %s "%s %s%s" %s %.3f',
                 format_time(self.start_timestamp),
                 self.http_method(),
                 self.http_path(),
                 self.http_query(),
                 self.http_status,
                 self.end_timestamp - self.start_timestamp)
    for key, value in sorted(self.get_rpcstats().iteritems()):
      logging.info('  %s : %s', key, value)
    if level <= 0:
      return
    with self._lock:
      for trace in self.traces:
        start = trace.start_offset_milliseconds()
        logging.info('  TRACE  : [%s, %s, %s, %s]',
                     trace.start_offset_milliseconds(),
                     trace.service_call_name(),
                     trace.duration_milliseconds(),
                     trace.api_mcycles())
        logging.info('    REQ  : %s', trace.request_data_summary())
        logging.info('    RESP : %s', trace.response_data_summary())
        if level <= 1:
          continue
        for entry in trace.call_stack_list():
          logging.info('    FRAME: %s:%s %s()',
                       entry.class_or_file_name(),
                       entry.line_number(),
                       entry.function_name())
          for variable in entry.variables_list():
            logging.info('      VAR: %s = %s', variable.key(), variable.value())

  def get_call_stack(self, trace):
    """Extract the current call stack.

    The stack is limited to at most config.MAX_STACK frames; frames
    recognized by config.RE_STACK_SKIP are skipped; a frame recognized
    by config.RE_STACK_BOTTOM terminates the stack search.

    Args:
      trace: An IndividualRpcStatsProto instance that will be updated.
    """
    frame = sys._getframe(0)
    while frame is not None and trace.call_stack_size() < config.MAX_STACK:
      if not self.get_frame_summary(frame, trace):
        break
      frame = frame.f_back

  sys_path_entries = None

  @classmethod
  def init_sys_path_entries(cls):
    """Initialize the class variable path_entries.

    The variable will hold a list of (i, entry) tuples where
    entry == sys.path[i], sorted from shortest to longest entry.
    """
    cls.sys_path_entries = sorted(enumerate(sys.path),
                                  key=lambda x: (-len(x[1]), x[0]))

  def get_frame_summary(self, frame, trace):
    """Return a frame summary.

    Args:
      frame: A Python stack frame object.
      trace: An IndividualRpcStatsProto instance that will be updated.

    Returns:
      False if this stack frame matches config.RE_STACK_BOTTOM.
      True otherwise.
    """
    if self.sys_path_entries is None:
      self.init_sys_path_entries()
    filename = frame.f_code.co_filename

    if filename and not (filename.startswith('<') and filename.endswith('>')):
      for i, entry in self.sys_path_entries:
        if filename.startswith(entry):
          filename = '<path[%s]>' % i + filename[len(entry):]
          break
      else:
        logging.info('No prefix for %s', filename)
    funcname = frame.f_code.co_name
    lineno = frame.f_lineno

    code_key = '%s:%s:%s' % (filename, funcname, lineno)
    if re.search(config.RE_STACK_BOTTOM, code_key):
      return False
    if re.search(config.RE_STACK_SKIP, code_key):
      return True
    entry = trace.add_call_stack()
    entry.set_class_or_file_name(filename)
    entry.set_line_number(lineno)
    entry.set_function_name(funcname)
    if frame.f_globals is frame.f_locals:
      return True

    max_locals = config.MAX_LOCALS
    if max_locals <= 0:
      return True

    for name, value in sorted(frame.f_locals.iteritems()):
      x = entry.add_variables()
      x.set_key(name)
      x.set_value(format_value(value))
      max_locals -= 1
      if max_locals <= 0:
        break

    return True


def mcycles_to_seconds(mcycles):
  """Helper function to convert megacycles to seconds."""
  if mcycles is None:
    return 0
  return quota.megacycles_to_cpu_seconds(mcycles)


def mcycles_to_msecs(mcycles):
  """Helper function to convert megacycles to milliseconds."""
  return int(mcycles_to_seconds(mcycles) * 1000)


def make_key(timestamp):
  """Return the key (less suffix) to which a timestamp maps.

  Args:
    timestamp: A timestamp, expressed using the standard Python
      convention for timestamps (a float giving seconds and fractional
      seconds since the POSIX timestamp epoch).

  Returns:
    A string, formed by concatenating config.KEY_PREFIX and
    config.KEY_TEMPLATE with some of the lower digits of the timestamp
    converted to milliseconds substituted in the template (which should
    contain exactly one %-format like '%d').
  """
  distance = config.KEY_DISTANCE
  modulus = config.KEY_MODULUS
  tmpl = config.KEY_PREFIX + config.KEY_TEMPLATE
  msecs = int(timestamp * 1000)
  index = ((msecs // distance) % modulus) * distance
  return tmpl % index


def format_time(timestamp):
  """Utility to format a timestamp in UTC.

  Args:
      timestamp: A float representing a standard Python time (see make_key()).
  """
  timestamp = datetime.datetime.utcfromtimestamp(timestamp)
  timestamp -= datetime.timedelta(seconds=config.TZOFFSET)
  return timestamp.isoformat()[:-3].replace('T', ' ')


def format_value(val):
  """Format an arbitrary value as a compact string.

  This wraps formatting._format_value() passing it our config variables.
  """
  return formatting._format_value(val, config.MAX_REPR, config.MAX_DEPTH)


class StatsProto(datamodel_pb.RequestStatProto):
  """A subclass if RequestStatProto with a number of extra attributes.

  This exists mainly so that ui.py can pass an instance of this class
  directly to a Django template, and hive the Django template access
  to formatted times and megacycles converted to milliseconds without
  using custom tags.  (Though arguably the latter would be more
  convenient for the Java version of Appstats.)

  This adds the following methods:

  - .start_time_formatted(): .start_time_milliseconds() nicely formatted.
  - .api_milliseconds(): .api_mcycles() converted to milliseconds.
  - .processor_milliseconds(): .processor_mcycles() converted to milliseconds.
  - .combined_rpc_count(): total number of RPCs, computed from
      .rpc_stats_list().  (This is cached as .__combined_rpc_count.)

  All these are methods to remain close in style to the protobuffer
  access methods.

  In addition, each of the entries in .individual_stats_list() is given
  a .api_milliseconds attribute (not a method, since we cannot subclass
  the class used for these entries easily, but we can add attributes
  to the instances in our constructor).
  """

  def __init__(self, *args, **kwds):
    """Constructor.

    This exists solely so it can pre-populate the .api_milliseconds
    attributes of the entries in .individual_stats_list().
    """
    datamodel_pb.RequestStatProto.__init__(self, *args, **kwds)


    for r in self.individual_stats_list():
      r.api_milliseconds = mcycles_to_msecs(r.api_mcycles())

  def start_time_formatted(self):
    """Return a string representing .start_timestamp_milliseconds()."""
    return format_time(self.start_timestamp_milliseconds() * 0.001)

  def api_milliseconds(self):
    """Return an int giving .api_mcycles() converted to milliseconds."""
    return mcycles_to_msecs(self.api_mcycles())

  def processor_mcycles(self):
    warnings.warn('processor_mcycles does not return correct values',
                  DeprecationWarning,
                  stacklevel=2)
    return datamodel_pb.RequestStatProto.processor_mcycles(self)

  def processor_milliseconds(self):
    """Return an int giving .processor_mcycles() converted to milliseconds."""
    warnings.warn('processor_milliseconds does not return correct values',
                  DeprecationWarning,
                  stacklevel=2)

    return mcycles_to_msecs(
        datamodel_pb.RequestStatProto.processor_mcycles(self))

  __combined_rpc_count = None

  def combined_rpc_count(self):
    """Return the total number of RPCs across .rpc_stats_list()."""
    if self.__combined_rpc_count is None:
      self.__combined_rpc_count = sum(x.total_amount_of_calls()
                                      for x in self.rpc_stats_list())
    return self.__combined_rpc_count


def load_summary_protos():
  """Load all valid summary records from memcache.

  Returns:
    A list of StatsProto instances, in reverse chronological order
    (i.e. most recent first).

  NOTE: This is limited to returning at most config.KEY_MODULUS records,
  since there are only that many distinct keys.  See also make_key().
  """
  tmpl = config.KEY_PREFIX + config.KEY_TEMPLATE + config.PART_SUFFIX
  keys = [tmpl % i
          for i in
          range(0, config.KEY_DISTANCE * config.KEY_MODULUS,
                config.KEY_DISTANCE)]
  results = memcache.get_multi(keys, namespace=config.KEY_NAMESPACE)
  records = []
  for rec in results.itervalues():
    try:
      pb = StatsProto(rec)
    except Exception, err:
      logging.warn('Bad record: %s', err)
    else:
      records.append(pb)
  logging.info('Loaded %d raw records, %d valid', len(results), len(records))

  records.sort(key=lambda pb: -pb.start_timestamp_milliseconds())
  return records


def load_full_proto(timestamp):
  """Load the full record for a given timestamp.

  Args:
    timestamp: The start_timestamp of the record, as a float in seconds
      (see make_key() for details).

  Returns:
    A StatsProto instance if the record exists and can be loaded;
    None otherwise.
  """
  full_key = make_key(timestamp) + config.FULL_SUFFIX
  full_binary = memcache.get(full_key, namespace=config.KEY_NAMESPACE)
  if full_binary is None:
    logging.info('No full record at %s', full_key)
    return None
  try:
    full = StatsProto(full_binary)
  except Exception, err:
    logging.warn('Bad full record at %s: %s', full_key, err)
    return None
  if full.start_timestamp_milliseconds() != int(timestamp * 1000):
    logging.warn('Hash collision, record at %d has timestamp %d',
                 int(timestamp * 1000), full.start_timestamp_milliseconds())
    return None
  return full


class AppstatsDjangoMiddleware(object):
  """Django Middleware to install the instrumentation.

  To start recording your app's RPC statistics, add

    'google.appengine.ext.appstats.recording.AppstatsDjangoMiddleware',

  to the MIDDLEWARE_CLASSES entry in your Django settings.py file.
  It's best to insert it in front of any other middleware classes,
  since some other middleware may make RPC calls and those won't be
  recorded if that middleware is invoked before this middleware.

  See http://docs.djangoproject.com/en/dev/topics/http/middleware/.

  Special note for FirePython users: when combining FirePython and
  Appstats through Django middleware, place the FirePython middleware
  first.  IOW FirePython must wrap Appstats, not the other way around.
  """

  def process_request(self, request):
    """Called by Django before deciding which view to execute."""
    start_recording()

  def process_response(self, request, response):
    """Called by Django just before returning a response."""
    firepython_set_extension_data = getattr(
      request,
      'firepython_set_extension_data',
      None)
    end_recording(response.status_code, firepython_set_extension_data)
    return response



AppStatsDjangoMiddleware =  AppstatsDjangoMiddleware


def appstats_wsgi_middleware(app):
  """WSGI Middleware to install the instrumentation.

  Normally you specify this middleware in your appengine_config.py
  file, like this:

    def webapp_add_wsgi_middleware(app):
      from google.appengine.ext.appstats import recording
      app = recording.appstats_wsgi_middleware(app)
      return app

  See Python PEP 333, http://www.python.org/dev/peps/pep-0333/ for
  more information about the WSGI standard.
  """

  def appstats_wsgi_wrapper(environ, start_response):
    """Outer wrapper function around the WSGI protocol.

    The top-level appstats_wsgi_middleware() function returns this
    function to the caller instead of the app class or function passed
    in.  When the caller calls this function (which may happen
    multiple times, to handle multiple requests) this function
    instantiates the app class (or calls the app function), sandwiched
    between calls to start_recording() and end_recording() which
    manipulate the recording state.

    The signature is determined by the WSGI protocol.
    """
    start_recording(environ)
    save_status = [None]

    firepython_set_extension_data = environ.get('firepython.set_extension_data')

    def appstats_start_response(status, headers, exc_info=None):
      """Inner wrapper function for the start_response() function argument.

      The purpose of this wrapper is save the HTTP status (which the
      WSGI protocol only makes available through the start_response()
      function) into the surrounding scope.  This is done through a
      hack because Python 2.x doesn't support assignment to nonlocal
      variables.  If this function is called more than once, the last
      status value will be used.

      The signature is determined by the WSGI protocol.
      """
      save_status.append(status)
      return start_response(status, headers, exc_info)

    try:
      result = app(environ, appstats_start_response)
    except Exception:
      end_recording(500, firepython_set_extension_data)
      raise
    if result is not None:
      for value in result:
        yield value
    status = save_status[-1]
    if status is not None:
      status = status[:3]
    end_recording(status, firepython_set_extension_data)

  return appstats_wsgi_wrapper


def _synchronized(method):
  """A decorator that synchronizes the method call with self._lock."""

  def synchronized_wrapper(self, *args):
    with self._lock:
      return method(self, *args)
  return synchronized_wrapper


class RequestLocalRecorderProxy(object):
  """A Recorder proxy that dispatches to a Recorder for the current request."""

  def __init__(self):
    self._recorders = {}
    self._lock = threading.RLock()

  @_synchronized
  def __getattr__(self, key):
    if not self.has_recorder_for_current_request():
      raise AttributeError('No Recorder is set for this request.')
    return getattr(self.get_for_current_request(), key)

  @_synchronized
  def has_recorder_for_current_request(self):
    """Returns whether the current request has a recorder set."""
    return os.environ.get('REQUEST_ID_HASH') in self._recorders

  @_synchronized
  def set_for_current_request(self, new_recorder):
    """Sets the recorder for the current request."""
    self._recorders[os.environ.get('REQUEST_ID_HASH')] = new_recorder
    _set_global_recorder(new_recorder)

  @_synchronized
  def get_for_current_request(self):
    """Returns the recorder for the current request or None."""
    return self._recorders.get(os.environ.get('REQUEST_ID_HASH'))

  @_synchronized
  def clear_for_current_request(self):
    """Clears the recorder for the current request."""
    if os.environ.get('REQUEST_ID_HASH') in self._recorders:
      del self._recorders[os.environ.get('REQUEST_ID_HASH')]
    _clear_global_recorder()

  @_synchronized
  def _clear_all(self):
    """Clears the recorders for all requests."""
    self._recorders.clear()
    _clear_global_recorder()


def _set_global_recorder(new_recorder):
  if os.environ.get('APPENGINE_RUNTIME') != 'python27':
    global recorder
    recorder = new_recorder


def _clear_global_recorder():
  _set_global_recorder(None)



recorder_proxy = RequestLocalRecorderProxy()


if os.environ.get('APPENGINE_RUNTIME') != 'python27':
  recorder = None


def dont_record():
  """API to prevent recording of the current request.  Used by ui.py."""
  recorder_proxy.clear_for_current_request()


def lock_key():
  """Return the key name to use for the memcache lock."""
  return config.KEY_PREFIX + config.LOCK_SUFFIX


def start_recording(env=None):
  """Start recording RPC traces.

  This creates a Recorder instance and sets it for the current request
  in the global RequestLocalRecorderProxy 'recorder_proxy'.

  Args:
    env: Optional WSGI environment; defaults to os.environ.
  """
  recorder_proxy.clear_for_current_request()
  if env is None:
    env = os.environ
  if not config.should_record(env):
    return

  if memcache.add(lock_key(), 0,
                  time=config.LOCK_TIMEOUT, namespace=config.KEY_NAMESPACE):
    recorder_proxy.set_for_current_request(Recorder(env))
    if config.DEBUG:
      logging.debug('Set recorder')


def end_recording(status, firepython_set_extension_data=None):
  """Stop recording RPC traces and save all traces to memcache.

  This clears the recorder set for this request in 'recorder_proxy'.

  Args:
    status: HTTP Status, a 3-digit integer.
    firepython_set_extension_data: Optional function to be called
      to pass the recorded data to FirePython.
  """
  rec = recorder_proxy.get_for_current_request()
  recorder_proxy.clear_for_current_request()
  if config.DEBUG:
    logging.debug('Cleared recorder')
  if rec is not None:
    try:
      rec.record_http_status(status)
      rec.save()





      if (firepython_set_extension_data and
          (os.getenv('SERVER_SOFTWARE', '').startswith('Dev') or
           users.is_current_user_admin())):
        logging.info('Passing data to firepython')
        firepython_set_extension_data('appengine_appstats', rec.json())
    finally:
      memcache.delete(lock_key(), namespace=config.KEY_NAMESPACE)


def pre_call_hook(service, call, request, response, rpc=None):
  """Pre-Call hook function for apiprixy_stub_map.

  The signature is determined by the CallHooks protocol.  In certain
  cases, rpc may be omitted.

  Once registered, this fuction will be called right before any kind
  of RPC call is made through apiproxy_stub_map.  The arguments are
  passed on to the record_rpc_request() method of the global
  'recorder_proxy' variable, unless the latter does not have a Recorder set
  for this request.
  """
  if recorder_proxy.has_recorder_for_current_request():
    if config.DEBUG:
      logging.debug('pre_call_hook: recording %s.%s', service, call)
    recorder_proxy.record_rpc_request(service, call, request, response, rpc)


def post_call_hook(service, call, request, response, rpc=None, error=None):
  """Post-Call hook function for apiproxy_stub_map.

  The signature is determined by the CallHooks protocol.  In certain
  cases, rpc and/or error may be omitted.

  Once registered, this fuction will be called right after any kind of
  RPC call made through apiproxy_stub_map returns.  The call is passed
  on to the record_rpc_request() method of the global 'recorder_proxy'
  variable, unless the latter does not have a Recorder set for this
  request.
  """

  if recorder_proxy.has_recorder_for_current_request():
    if config.DEBUG:
      logging.debug('post_call_hook: recording %s.%s', service, call)
    recorder_proxy.record_rpc_response(service, call, request, response, rpc)



apiproxy_stub_map.apiproxy.GetPreCallHooks().Append('appstats', pre_call_hook)
apiproxy_stub_map.apiproxy.GetPostCallHooks().Append('appstats', post_call_hook)
