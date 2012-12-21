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




"""Data structures to represent statistics used by analysis library.

Appstats data is loaded into data structures defined in this code.
URLStats holds information about all requests of an URL path,
URLRequestStats holds information about a specific request,
RPCStats holds data about a specific RPC category for each request.
"""


import logging
import entity


def _RPCCategory(rpcstatsproto):
  """Categorize Datastore RPCs by entity kind and other information.

  The analysis tool presents a breakdown of the request latency into
  different RPCs. Simply grouping RPCs with the same service and call name
  together is too coarse-grained. E.g., consider a request that
  involves two different types of datastore queries on different
  entity kinds. More meaningful information to the developer can be
  conveyed by presenting time spent in query_kind1, and query_kind2
  separately. To handle this, we identify the "category" of an RPC,
  and summarize results based on the service name, call name, and
  category. At this point, the category field is only relevant for
  datastore related RPCs, and is simply '' for all non-datastore RPCs.
  For the datastore RPCs, category information usually includes the
  relevant entity kind and other information, but the details are
  very specific to the individual call.

  Args:
    rpcstatsproto: IndividualRPCStatsProto from Appstats recording which
        represents statistics for a single RPC in a request.

  Returns:
    A string which indicates category to which the RPC belongs.
    Returns '' if category information is not relevant to this RPC.
  """
  category = ''
  if not rpcstatsproto.has_datastore_details():
    return category
  servicecallname = rpcstatsproto.service_call_name()
  if servicecallname == 'datastore_v3.Put':

    category = entity.EntityListKind(
        rpcstatsproto.datastore_details().keys_written_list())
  elif servicecallname == 'datastore_v3.Get':

    category = entity.EntityListKind(
        rpcstatsproto.datastore_details().keys_read_list())
  elif servicecallname == 'datastore_v3.Next':




    category = entity.EntityListKind(
        rpcstatsproto.datastore_details().keys_read_list())
  elif servicecallname == 'datastore_v3.RunQuery':



    if rpcstatsproto.datastore_details().has_query_kind():
      kind = rpcstatsproto.datastore_details().query_kind()
    else:
      kind = 'NoKind'
    if rpcstatsproto.datastore_details().has_query_ancestor():

      ancestor = '_ANC'
    else:
      ancestor = ''
    category = '%s%s' %(kind, ancestor)
  return category


class RPCStats(object):
  """Statistics associated with each RPC call category for a request.

  For each RPC call category associated with a URL request, track the number of
  calls, and total time spent summed across all calls. For datastore related
  RPCs, track list of entities accessed (fetched/written/failed get requests).
  """


  _ABBRV = {
      'datastore_v3.Put': 'ds.Put',
      'datastore_v3.RunQuery': 'ds.Query',
      'datastore_v3.Get': 'ds.Get',
      'datastore_v3.Next': 'ds.Next',
      }

  def __init__(self, rpcstatsproto):
    """Initialize stats first time RPC called for that URL request.

    Args:
      rpcstatsproto: IndividualRPCStatsProto from Appstats recording which
          represents statistics for a single RPC in a request.
    """

    self.servicecallname = rpcstatsproto.service_call_name()
    self.category = _RPCCategory(rpcstatsproto)
    self.time = 0
    self.numcalls = 0
    self.keys_read = []
    self.keys_written = []

    self.keys_failed_get = []
    self.Incr(rpcstatsproto)

  def Incr(self, rpcstatsproto):
    """Update stats every time RPC called for that URL request.

    Increment number of calls to RPCs in this category by 1 and increment
    total time spent in this RPC category by time taken by this particular
    RPC. Augment the entities read, written and missed by this RPC category
    with the entities read, written and missed by the RPC.

    Args:
      rpcstatsproto: IndividualRPCStatsProto from Appstats recording which
          represents statistics for a single RPC in a request.
    """






    self.time += int(rpcstatsproto.duration_milliseconds())
    self.numcalls += 1
    if rpcstatsproto.has_datastore_details():
      self.keys_read.extend(
          rpcstatsproto.datastore_details().keys_read_list())
      self.keys_written.extend(
          rpcstatsproto.datastore_details().keys_written_list())
      if self.servicecallname == 'datastore_v3.Get':
        hits = rpcstatsproto.datastore_details().get_successful_fetch_list()
        entities = rpcstatsproto.datastore_details().keys_read_list()
        for index in range(len(hits)):
          if not hits[index]:
            self.keys_failed_get.append(entities[index])

  def GetLabel(self):
    """Get label used to refer to RPC category in graphs."""
    label = RPCStats._ABBRV.get(self.servicecallname, self.servicecallname)
    if self.category:

      label = '%s_%s' %(label, self.category)
    return label

  def Match(self, rpcstatsproto):
    """Checks if an RPC belongs to the same category as current.

    Args:
      rpcstatsproto: IndividualRPCStatsProto from Appstats recording which
          represents statistics for a single RPC in a request.

    Returns:
      True or False. True indicates the RPC belongs to same category
          as current one. False indicates otherwise.
    """
    if rpcstatsproto.service_call_name() != self.servicecallname:
      return False
    category = _RPCCategory(rpcstatsproto)
    if category != self.category:
      return False
    return True


class URLRequestStats(object):
  """Statistics associated with each URL request.

  For each URL request, keep track of list of RPCs, statistics
  associated with each RPC, and total response time for that
  URL request.
  """

  def __init__(self, statsproto):
    """Constructor."""
    self.rpcstatslist = []
    self.timestamp = statsproto.start_timestamp_milliseconds() * 0.001






    self.totalresponsetime = int(statsproto.duration_milliseconds())
    for t in statsproto.individual_stats_list():
      self.AddRPCStats(t)
    self.totalrpctime = self.TotalRPCTime()

  def TotalRPCTime(self):
    """Compute total time spent in all RPCs."""
    totalrpctime = 0
    for rpc in self.rpcstatslist:
      totalrpctime += rpc.time
    return totalrpctime

  def AddRPCStats(self, rpcstatsproto):
    """Update statistics for a given RPC called for that URL request."""


    for rpc in self.rpcstatslist:
      if rpc.Match(rpcstatsproto):
        rpc.Incr(rpcstatsproto)
        return

    rpcstats = RPCStats(rpcstatsproto)
    self.rpcstatslist.append(rpcstats)

  def _IncrementCount(self, key_list, group_flag, freq, action):
    """Helper function to increment entity (group) access counts.

    Args:
      key_list: List of entity keys that were accessed.
      group_flag: Boolean. If True, entity group counts are desired.
        If False, entity counts are desired.
      freq: A dictionary keyed on entity (group) kind and name that
        holds counts for reads, writes and misses to that entity (group).
      action: Whether the access was a 'read', 'write' or 'miss'.
    """
    for key in key_list:
      if group_flag:
        name = entity.EntityGroupName(key)
        kind = entity.EntityGroupKind(key)
        kind_name = '%s,%s' %(kind, name)
      else:
        name = entity.EntityFullName(key)
        kind = entity.EntityKind(key)
        kind_name = '%s,%s' %(kind, name)
      if not kind_name in freq:
        freq[kind_name] = {'read': 0, 'write': 0, 'miss': 0}
      freq[kind_name][action] += 1

  def EntityGroupCount(self):
    """Computes reads/writes/failed gets to each entity group for that request.

    Returns:
      freq: Dictionary keyed on entity group. Key is of the form
          'entitygroupkind,entitygroupname' which allows organizing statistics
          of entity groups by their kind. Value is an inner dictionary with 3
          keys: 'read', 'write', and 'missed'. Value of each inner dictionary
          item is the number of reads/writes/failed gets to that entity group
          for the request.
    """
    freq = {}
    for rpcstats in self.rpcstatslist:
      self._IncrementCount(rpcstats.keys_read, True, freq, 'read')
      self._IncrementCount(rpcstats.keys_written, True, freq, 'write')
      self._IncrementCount(rpcstats.keys_failed_get, True, freq, 'miss')
    return freq

  def EntityCount(self):
    """Computes number of reads/writes to each entity for that request.

    Returns:
      freq: Dictionary keyed on entity, with value being number of reads,
          writes or failed gets to that entity for the request. The dictionary
          key is of the form "entitykind,entityfullname" which allows organizing
          statistics of entities by their kind.
    """
    freq = {}
    for rpcstats in self.rpcstatslist:
      self._IncrementCount(rpcstats.keys_read, False, freq, 'read')
      self._IncrementCount(rpcstats.keys_written, False, freq, 'write')
      self._IncrementCount(rpcstats.keys_failed_get, False, freq, 'miss')
    return freq


class URLStats(object):
  """Statistics associated with a given URL.

  For each request of that URL, keep track of statistics associated
  with that request such as response time, RPCs called, and
  statistics associated with the RPC.
  """

  def __init__(self, url):
    """Constructor."""
    self.url = url
    self.urlrequestlist = []

  def AddRequest(self, statsproto):
    """Add stats about new request to that URL."""
    requeststats = URLRequestStats(statsproto)
    self.urlrequestlist.append(requeststats)

  def GetResponseTimeList(self):
    """Returns list of response times across all requests of URL."""
    responsetimelist = []
    for urlrequest in self.urlrequestlist:
      responsetimelist.append(urlrequest.totalresponsetime)
    return responsetimelist

  def GetTotalRPCTimes(self):
    """Returns list of response times across all requests of URL."""
    totalrpctimes = []
    for request in self.urlrequestlist:
      totalrpctimes.append(request.totalrpctime)
    return totalrpctimes

  def _Count(self, group_flag):
    """Helper function to count accesses to entities (entity groups).

    Args:
      group_flag: Boolean. If true, count entity groups. If false, count
        entities.

    Returns:
      Dictionary keyed on names of entities (entity groups) with values
      corresponding to their access counts.
    """
    freq_total = {}
    for request in self.urlrequestlist:
      if group_flag:
        freq_request = request.EntityGroupCount()
      else:
        freq_request = request.EntityCount()
      for name, freq in freq_request.items():
        if not name in freq_total:
          freq_total[name] = {'read': 0, 'write': 0, 'miss': 0}
        freq_total[name]['read'] += freq['read']
        freq_total[name]['write'] += freq['write']
        freq_total[name]['miss'] += freq['miss']
    return freq_total

  def EntityGroupCount(self):
    """Get reads/writes/failed gets to each entity group over all URL requests.

    Returns:
      freq_total: Dict keyed on entity group, with value being
          count of reads/writes/failed gets to that entity group across
          all requests.
    """
    return self._Count(True)

  def EntityCount(self):
    """Computes reads/writes/failed gets to each entity across all URL requests.

    Returns:
      freq_total: Dict keyed on entity name (in kind_fullname form), with
          value being number of reads and writes to that entity across all
          requests.
    """
    return self._Count(False)

  def Dump(self):
    """Dumps URL statistics to INFO/DEBUG logs for debugging."""
    logging.info('URL: %s', self.url)
    for urlrequest in self.urlrequestlist:
      logging.info('Resptime: %d', urlrequest.totalresponsetime)
      for rpc in urlrequest.rpcstatslist:
        logging.info('%s %s %d %d read:%d written:%d failedgets:%d',
                     rpc.servicecallname,
                     rpc.category,
                     rpc.time,
                     rpc.numcalls,
                     len(rpc.keys_read),
                     len(rpc.keys_written),
                     len(rpc.keys_failed_get))

        logging.debug('Keys Read')
        for key in rpc.keys_read:
          logging.debug('%s ', entity.EntityFullName(key))
        logging.debug('Keys Written')
        for key in rpc.keys_written:
          logging.debug('%s ', entity.EntityFullName(key))
        logging.info('Keys Failed Get')
        for key in rpc.keys_failed_get:
          logging.debug('%s ', entity.EntityFullName(key))
