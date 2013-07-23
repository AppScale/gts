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


def _to_micropennies_per_op(pennies, per):
  """The price of a single op in micropennies."""

  return (pennies * 1000000) / per


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



  SHELL_OK = os.getenv('SERVER_SOFTWARE', '').startswith('Dev')


  DEFAULT_SCRIPT = "print 'Hello, world.'"


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





  DATASTORE_DETAILS = False


  CALC_RPC_COSTS = False








  DATASTORE_READ_OP_COST = _to_micropennies_per_op(7, 100000)


  DATASTORE_WRITE_OP_COST = _to_micropennies_per_op(10, 100000)


  DATASTORE_SMALL_OP_COST = _to_micropennies_per_op(1, 100000)


  MAIL_RECIPIENT_COST = _to_micropennies_per_op(1, 1000)


  CHANNEL_CREATE_COST = _to_micropennies_per_op(1, 100)



  CHANNEL_PRESENCE_COST = _to_micropennies_per_op(10, 100000)


  XMPP_STANZA_COST = _to_micropennies_per_op(10, 100000)



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

  def record_datastore_details(self, call, request, response, trace):
    """Records additional information relating to datastore RPCs.

    Parses requests and responses of datastore related RPCs, and records
    the primary keys of entities that are put into the datastore or
    fetched from the datastore. Non-datastore RPCs are ignored. Keys are
    recorded in the form of Reference protos. Currently the information
    is logged for the following calls: Get, Put, RunQuery and Next. The
    code may be extended in the future to cover more RPC calls. In
    addition to the entity keys, useful information specific to each
    call is recorded. E.g., for queries, the entity kind and cursor
    information is recorded; For gets, a flag indicating if the
    requested entity key is present or not is recorded.

    Also collects RPC costs.

    Args:
      call: The call name, e.g. 'Get'.
      request: The request protocol message corresponding to the call.
      response: The response protocol message corresponding to the call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if call == 'Put':
      self.record_put_details(response, trace)
    elif call == 'Delete':
      self.record_delete_details(response, trace)
    elif call == 'Commit':
      self.record_commit_details(response, trace)
    elif call in ('RunQuery', 'Next'):
      self.record_query_details(call, request, response, trace)
    elif call == 'Get':
      self.record_get_details(request, response, trace)
    elif call == 'AllocateIds':
      self.record_allocate_ids_details(trace)


  def record_put_details(self, response, trace):
    """Records additional put details based on config options.

    Details include: Keys of entities written and cost
    information for the Put RPC.

    Args:
      response: The response protocol message of the Put RPC call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if config.DATASTORE_DETAILS:
      details = trace.mutable_datastore_details()
      for key in response.key_list():
        newent = details.add_keys_written()
        newent.CopyFrom(key)
    if config.CALC_RPC_COSTS:
      writes = response.cost().entity_writes() + response.cost().index_writes()
      trace.set_call_cost_microdollars(writes * config.DATASTORE_WRITE_OP_COST)
      _add_billed_op_to_trace(trace, writes,
                              datamodel_pb.BilledOpProto.DATASTORE_WRITE)

  def record_delete_details(self, response, trace):
    """Records cost information for the Delete RPC.

    Args:
      response: The response protocol message of the Delete RPC call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if config.CALC_RPC_COSTS:
      writes = response.cost().entity_writes() + response.cost().index_writes()
      trace.set_call_cost_microdollars(writes * config.DATASTORE_WRITE_OP_COST)
      _add_billed_op_to_trace(trace, writes,
                              datamodel_pb.BilledOpProto.DATASTORE_WRITE)

  def record_commit_details(self, response, trace):
    """Records cost information for the Commit RPC.

    Args:
      response: The response protocol message of the Commit RPC call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if config.CALC_RPC_COSTS:
      cost = response.cost()
      writes = (cost.commitcost().requested_entity_puts() +
                cost.commitcost().requested_entity_deletes() +
                cost.index_writes())
      trace.set_call_cost_microdollars(writes * config.DATASTORE_WRITE_OP_COST)
      _add_billed_op_to_trace(trace, writes,
                              datamodel_pb.BilledOpProto.DATASTORE_WRITE)

  def record_get_details(self, request, response, trace):
    """Records additional get details based on config options.

    Details include: Keys of entities requested, whether or not the requested
    key was successfully fetched, and cost information for the Get RPC.

    Args:
      request: The request protocol message of the Get RPC call.
      response: The response protocol message of the Get RPC call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if config.DATASTORE_DETAILS:
      details = trace.mutable_datastore_details()
      for key in request.key_list():
        newent = details.add_keys_read()
        newent.CopyFrom(key)
      for entity_present in response.entity_list():
        details.add_get_successful_fetch(entity_present.has_entity())
    if config.CALC_RPC_COSTS:
      keys_to_read = len(request.key_list())

      trace.set_call_cost_microdollars(
          keys_to_read * config.DATASTORE_READ_OP_COST)
      _add_billed_op_to_trace(trace, keys_to_read,
                              datamodel_pb.BilledOpProto.DATASTORE_READ)

  def record_query_details(self, call, request, response, trace):
    """Records additional query details based on config options.

    Details include: Keys of entities fetched by a datastore query and cost
    information.

    Information is recorded for both the RunQuery and Next calls.
    For RunQuery calls, we record the entity kind and ancestor (if
    applicable) and cursor information (which can help correlate
    the RunQuery with a subsequent Next call). For Next calls, we
    record cursor information of the Request (which helps associate
    this call with the previous RunQuery/Next call), and the Response
    (which helps associate this call with the subsequent Next call).
    For key only queries, entity keys are not recorded since entities
    are not actually fetched. In the future, we might want to record
    the entities but also record a flag indicating whether this is a
    key only query.

    Args:
      call: The call name, e.g. 'RunQuery' or 'Next'
      request: The request protocol message of the RPC call.
      response: The response protocol message of the RPC call.
      trace: IndividualStatsProto where information must be recorded.
    """
    details = trace.mutable_datastore_details()
    if not response.keys_only():


      for entity in response.result_list():
        newent = details.add_keys_read()
        newent.CopyFrom(entity.key())
    if call == 'RunQuery':

      if config.DATASTORE_DETAILS:
        if request.has_kind():
          details.set_query_kind(request.kind())
        if request.has_ancestor():
          ancestor = details.mutable_query_ancestor()
          ancestor.CopyFrom(request.ancestor())


        if response.has_cursor():
          details.set_query_nextcursor(response.cursor().cursor())

      baseline_reads = 1
    elif call == 'Next':



      if config.DATASTORE_DETAILS:
        details.set_query_thiscursor(request.cursor().cursor())
        if response.has_cursor():
          details.set_query_nextcursor(response.cursor().cursor())
      baseline_reads = 0

    if config.CALC_RPC_COSTS:
      num_results = len(response.result_list()) + response.skipped_results()
      cost_micropennies = config.DATASTORE_READ_OP_COST * baseline_reads
      if response.keys_only():

        cost_micropennies += config.DATASTORE_SMALL_OP_COST * num_results
        trace.set_call_cost_microdollars(cost_micropennies)
        _add_billed_op_to_trace(trace, baseline_reads,
                                datamodel_pb.BilledOpProto.DATASTORE_READ)
        _add_billed_op_to_trace(trace, num_results,
                                datamodel_pb.BilledOpProto.DATASTORE_SMALL)
      else:

        cost_micropennies += config.DATASTORE_READ_OP_COST * num_results
        trace.set_call_cost_microdollars(cost_micropennies)
        _add_billed_op_to_trace(trace, num_results + baseline_reads,
                                datamodel_pb.BilledOpProto.DATASTORE_READ)

  def record_allocate_ids_details(self, trace):
    """Records cost information for the AllocateIds RPC.

    Args:
      trace: IndividualStatsProto where information must be recorded.
    """

    trace.set_call_cost_microdollars(config.DATASTORE_SMALL_OP_COST)
    _add_billed_op_to_trace(trace, 1,
                            datamodel_pb.BilledOpProto.DATASTORE_SMALL)

  def record_xmpp_details(self, call, request, trace):
    """Records information relating to xmpp RPCs.

    Args:
      call: The call name, e.g. 'SendMessage'.
      request: The request protocol message corresponding to the call.
      trace: IndividualStatsProto where information must be recorded.
    """
    stanzas = 0
    if call == 'SendMessage':
      stanzas = request.jid_size()
    elif call in ('GetPresence', 'SendPresence', 'SendInvite'):
      stanzas = 1
    trace.set_call_cost_microdollars(stanzas * config.XMPP_STANZA_COST)
    _add_billed_op_to_trace(trace, stanzas,
                            datamodel_pb.BilledOpProto.XMPP_STANZA)

  def record_channel_details(self, call, trace):
    """Records information relating to channel RPCs.

    Args:
      call: The call name, e.g. 'CreateChannel'.
      trace: IndividualStatsProto where information must be recorded.
    """
    if call == 'CreateChannel':
      trace.set_call_cost_microdollars(config.CHANNEL_CREATE_COST)
      _add_billed_op_to_trace(trace, 1,
                              datamodel_pb.BilledOpProto.CHANNEL_OPEN)
    elif call == 'GetPresence':
      trace.set_call_cost_microdollars(config.CHANNEL_PRESENCE_COST)
      _add_billed_op_to_trace(trace, 1,
                              datamodel_pb.BilledOpProto.CHANNEL_PRESENCE)

  def record_mail_details(self, call, request, trace):
    """Records information relating to mail RPCs.

    Args:
      call: The call name, e.g. 'Send'.
      request: The request protocol message corresponding to the call.
      trace: IndividualStatsProto where information must be recorded.
    """
    if call in ('Send', 'SendToAdmin'):
      num_recipients = (request.to_size() + request.cc_size() +
                        request.bcc_size())
      trace.set_call_cost_microdollars(
          config.MAIL_RECIPIENT_COST * num_recipients)
      _add_billed_op_to_trace(trace, num_recipients,
                              datamodel_pb.BilledOpProto.MAIL_RECIPIENT)

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
    if rpc is not None:


      with self._lock:
        index = self.pending.get(rpc)
        if index is not None:
          del self.pending[rpc]
          if 0 <= index < len(self.traces):
            trace = self.traces[index]
            trace.set_response_data_summary(sresp)
            duration = delta - trace.start_offset_milliseconds()
            trace.set_duration_milliseconds(duration)
            if (config.CALC_RPC_COSTS or
                config.DATASTORE_DETAILS) and service == 'datastore_v3':
              self.record_datastore_details(call, request, response, trace)
            elif config.CALC_RPC_COSTS and service == 'xmpp':
              self.record_xmpp_details(call, request, trace)
            elif config.CALC_RPC_COSTS and service == 'channel':
              self.record_channel_details(call, trace)
            elif config.CALC_RPC_COSTS and service == 'mail':
              self.record_mail_details(call, request, trace)
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

    This constructs the full proto and calls its .Encode() method;
    if the resulting string is too large, it tries a number of
    increasingly aggressive strategies for chopping the data down.
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
        logging.info('Full proto too large to save, cleared variables.')
        return part_encoded, full_encoded
    if config.MAX_STACK > 0:

      for trace in proto.individual_stats_list():
        trace.clear_call_stack()
      full_encoded = proto.Encode()
      if len(full_encoded) <= memcache.MAX_VALUE_SIZE:
        logging.info('Full proto way too large to save, cleared frames.')
        return part_encoded, full_encoded

    logging.info('Full proto WAY too large to save, clipped to 100 traces.')
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
      proto.individual_stats_list().extend(self.traces)

  def get_full_proto(self):
    """Return the full protobuf, wrapped in a StatsProto."""
    proto = self.get_summary_proto()
    self.add_full_info_to_proto(proto)
    return StatsProto(proto)

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
    summary.set_overhead_walltime_milliseconds(int(self.overhead * 1000))
    rpc_stats = self.get_rpcstats().items()
    rpc_stats.sort(key=lambda x: (-x[1][0], x[0]))
    for key, value in rpc_stats:
      x = summary.add_rpc_stats()
      x.set_service_call_name(key)
      x.set_total_amount_of_calls(value[0])
      x.set_total_cost_of_calls_microdollars(value[1])
      for billed_op in value[2].itervalues():
        x.total_billed_ops_list().append(billed_op)
    return summary

  def get_rpcstats(self):
    """Compute RPC statistics (how often each RPC endpoint is called).

    Returns:
      A dict mapping 'service.call' keys to an array of objects giving call
      counts (int), call costs (int), and billed ops (dict from op to pb).
    """
    rpcstats = {}
    with self._lock:
      values = [[trace.service_call_name(), trace.call_cost_microdollars(),
                 trace.billed_ops_list()] for trace in self.traces]
    for value in values:
      if value[0] in rpcstats:
        stats_for_rpc = rpcstats[value[0]]

        stats_for_rpc[0] += 1

        stats_for_rpc[1] += value[1]
      else:
        rpcstats[value[0]] = [1, value[1], {}]

      _add_billed_ops_to_map(rpcstats[value[0]][2], value[2])
    return rpcstats

  def get_total_api_mcycles(self):
    """Compute the total amount of API time for all RPCs.

    Deprecated. This value is no longer meaningful.

    Returns:
      An integer expressing megacycles.
    """
    warnings.warn('get_total_api_mcycles does not return a meaningful value',
                  UserWarning,
                  stacklevel=2)
    return 0

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
        logging.info('  TRACE  : [%s, %s, %s]',
                     trace.start_offset_milliseconds(),
                     trace.service_call_name(),
                     trace.duration_milliseconds())
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


def billed_ops_to_str(billed_ops_list):
  """Formats a list of BilledOpProtos for display in the appstats UI."""
  ops_as_strs = []
  for op in billed_ops_list:
    op_name = datamodel_pb.BilledOpProto.BilledOp_Name(op.op())
    ops_as_strs.append('%s:%s' % (op_name, op.num_ops()))
  return ', '.join(ops_as_strs)


def total_billed_ops_to_str(self):
  """Formats a list of BilledOpProtos for display in the appstats UI.

  We attach this method to AggregateRpcStatsProto, which keeps the
  django-templates we use to render the appstats UI simpler and multi-language
  friendly.

  Args:
    self: the linter is harrassing me, what am I supposed to put here?
  Returns:
    A display-friendly string representation of a list of BilledOpsProtos
  """
  return billed_ops_to_str(self.total_billed_ops_list())


def individual_billed_ops_to_str(self):
  """Formats a list of BilledOpProtos for display in the appstats UI.

  We attach this method to IndividualRpcStatsProto, which keeps the
  django-templates we use to render the appstats UI simpler and multi-language
  friendly.

  Args:
    self: the linter is harrassing me, what am I supposed to put here?
  Returns:
    A display-friendly string representation of a list of BilledOpsProtos
  """
  return billed_ops_to_str(self.billed_ops_list())


class StatsProto(object):
  """A wrapper for RequestStatProto with a number of extra attributes.

  This exists mainly so that ui.py can pass an instance of this class
  directly to a Django template, and give the Django template access
  to formatted times and megacycles converted to milliseconds without
  using custom tags.  (Though arguably the latter would be more
  convenient for the Java version of Appstats.)

  This adds the following methods:

  - .start_time_formatted(): .start_time_milliseconds() nicely formatted.
  - .processor_milliseconds(): .processor_mcycles() converted to milliseconds.
  - .combined_rpc_count(): total number of RPCs, computed from
      .rpc_stats_list().  (This is cached as .__combined_rpc_count.)
  - .combined_rpc_cost(): total cost of RPCs, computed from
      .rpc_stats_list().  (This is cached as .__combined_rpc_cost.)
  - .combined_rpc_billed_ops(): total billed ops for RPCs, computed from
      .rpc_stats_list().  (This is cached as .__combined_rpc_billed_ops.)

  All these are methods to remain close in style to the protobuffer
  access methods.
  """

  def __init__(self, proto=None):
    if not isinstance(proto, datamodel_pb.RequestStatProto):
      proto = datamodel_pb.RequestStatProto(proto)
    self._proto = proto

  def __getattr__(self, key):
    return getattr(self._proto, key)

  def start_time_formatted(self):
    """Return a string representing .start_timestamp_milliseconds()."""
    return format_time(self.start_timestamp_milliseconds() * 0.001)

  def api_milliseconds(self):
    """Return an int giving .api_mcycles() converted to milliseconds.

    Deprecated. This value is no longer meaningful.

    Returns:
      An integer expressing milliseconds.
    """
    warnings.warn('api_milliseconds does not return a meaningful value',
                  UserWarning,
                  stacklevel=2)
    return 0

  def processor_mcycles(self):
    warnings.warn('processor_mcycles does not return correct values',
                  UserWarning,
                  stacklevel=2)
    return self._proto.processor_mcycles()

  def processor_milliseconds(self):
    """Return an int giving .processor_mcycles() converted to milliseconds."""
    warnings.warn('processor_milliseconds does not return correct values',
                  UserWarning,
                  stacklevel=2)
    return mcycles_to_msecs(self._proto.processor_mcycles())

  __combined_rpc_count = None

  def combined_rpc_count(self):
    """Return the total number of RPCs across .rpc_stats_list()."""
    if self.__combined_rpc_count is None:
      self.__combined_rpc_count = sum(x.total_amount_of_calls()
                                      for x in self.rpc_stats_list())
    return self.__combined_rpc_count

  __combined_rpc_cost_micropennies = None

  def combined_rpc_cost_micropennies(self):
    """Return the total cost of RPCs across .rpc_stats_list()."""
    if self.__combined_rpc_cost_micropennies is None:
      self.__combined_rpc_cost_micropennies = (
          sum(x.total_cost_of_calls_microdollars()
              for x in self.rpc_stats_list()))
    return self.__combined_rpc_cost_micropennies

  __combined_rpc_billed_ops = None

  def combined_rpc_billed_ops(self):
    """Return the total billed ops for RPCs across .rpc_stats_list()."""
    if self.__combined_rpc_billed_ops is None:
      combined_ops_dict = {}
      for stats in self.rpc_stats_list():
        _add_billed_ops_to_map(combined_ops_dict,
                               stats.total_billed_ops_list())
      self.__combined_rpc_billed_ops = billed_ops_to_str(
          combined_ops_dict.itervalues())
    return self.__combined_rpc_billed_ops


def load_summary_protos(java_application=False):
  """Load all valid summary records from memcache.

  Args:
    java_application: Boolean. If true, this function is being invoked
      by the download_appstats tool on a java application.

  Returns:
    A list of StatsProto instances, in reverse chronological order
    (i.e. most recent first).

  NOTE: This is limited to returning at most config.KEY_MODULUS records,
  since there are only that many distinct keys.  See also make_key().
  """
  tmpl = config.KEY_PREFIX + config.KEY_TEMPLATE + config.PART_SUFFIX
  if java_application:

    tmpl = '"' + tmpl + '"'
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
  logging.info('Loaded %d raw summary records, %d valid',
               len(results), len(records))

  records.sort(key=lambda pb: -pb.start_timestamp_milliseconds())
  return records


def load_full_proto(timestamp, java_application=False):
  """Load the full record for a given timestamp.

  Args:
    timestamp: The start_timestamp of the record, as a float in seconds
      (see make_key() for details).
    java_application: Boolean. If true, this function is being invoked
      by the download_appstats tool on a java application.
  Returns:
    A StatsProto instance if the record exists and can be loaded;
    None otherwise.
  """
  full_key = make_key(timestamp) + config.FULL_SUFFIX
  if java_application:

    full_key = '"' + full_key + '"'
  full_binary = memcache.get(full_key, namespace=config.KEY_NAMESPACE)
  if full_binary is None:

    logging.debug('No full record at %s', full_key)
    return None
  try:
    full = StatsProto(full_binary)
  except Exception, err:
    logging.warn('Bad full record at %s: %s', full_key, err)
    return None
  if full.start_timestamp_milliseconds() != int(timestamp * 1000):

    logging.debug('Hash collision, record at %d has timestamp %d',
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
  """

  def process_request(self, request):
    """Called by Django before deciding which view to execute."""
    start_recording()

  def process_response(self, request, response):
    """Called by Django just before returning a response."""
    end_recording(response.status_code)
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



    datamodel_pb.AggregateRpcStatsProto.total_billed_ops_str = (
        total_billed_ops_to_str)
    datamodel_pb.IndividualRpcStatsProto.billed_ops_str = (
        individual_billed_ops_to_str)

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
      end_recording(500)
      raise
    if result is not None:
      for value in result:
        yield value
    status = save_status[-1]
    if status is not None:
      status = status[:3]
    end_recording(status)

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
  """
  if firepython_set_extension_data is not None:
    warnings.warn('Firepython is no longer supported')
  rec = recorder_proxy.get_for_current_request()
  recorder_proxy.clear_for_current_request()
  if config.DEBUG:
    logging.debug('Cleared recorder')
  if rec is not None:
    try:
      rec.record_http_status(status)
      rec.save()
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


def _add_billed_ops_to_map(billed_ops_dict, billed_ops_list):
  """Add the BilledOpProtos in billed_ops_list to the given dict."""
  for billed_op in billed_ops_list:
    if billed_op.op() not in billed_ops_dict:
      update_me = datamodel_pb.BilledOpProto()
      update_me.set_op(billed_op.op())
      update_me.set_num_ops(0)
      billed_ops_dict[billed_op.op()] = update_me
    update_me = billed_ops_dict[billed_op.op()]
    update_me.set_num_ops(update_me.num_ops() + billed_op.num_ops())


def _add_billed_op_to_trace(trace, num_ops, op):
  """Adds a billed op to the given trace."""
  if num_ops:
    billed_op = trace.add_billed_ops()
    billed_op.set_num_ops(num_ops)
    billed_op.set_op(op)



apiproxy_stub_map.apiproxy.GetPreCallHooks().Append('appstats', pre_call_hook)
apiproxy_stub_map.apiproxy.GetPostCallHooks().Append('appstats', post_call_hook)
