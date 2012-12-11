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




"""Compute statistics on Appstats data and prepare data for UI.

Appstats data is processed to compute information necessary for
charts. For e.g., for the main page, request counts in different
latency bins are computed, and the information is summarized in
a manner convenient for the UI.
"""


try:
  import json
except ImportError:
  import simplejson as json
import math


class _ExponentialBinner(object):
  """Bins data in intervals with exponentially increasing sizes.

    Helps with preparation of histograms. E.g., histograms that
    plot number of requests within each latency range.
  """

  def __init__(self, start, exponent):
    """Initialize parameters for histograms.

    E.g., start = 10, and exponent = 2 will bin data using intervals
    [0, 10], [11, 20], [21, 40], and so on.

    Args:
      start: upper bound of first interval
      exponent: ratio of upper bounds of two consecutive intervals.
    """
    self.start = start
    self.exponent = exponent

  def Bin(self, data):
    """Compute counts of data items in various bins.

    Args:
      data: sorted list of integer or long data items.
    Returns:
      A list, with each element being count of data items in each bin
    """
    bincounts = []

    numbins = self._BinIndex(data[-1]) + 1

    for bin_index in range(numbins):
      bincounts.append(0)
    for item in data:
      bin_index = self._BinIndex(item)
      bincounts[bin_index] += 1
    return bincounts

  def Intervals(self, numbins):
    """Returns the upper bounds of intervals under exponential binning.

    E.g., if intervals are [0, 10], [11, 20], [21, 40], [41, 80], this
    function returns the list [10, 20, 40, 80].

    Args:
      numbins: Number of bins.
    Returns:
      A list which contains upper bounds of each interval range.
    """
    if numbins < 1:
      return []
    intervals = [self.start]
    for _ in range(1, numbins):
      intervals.append(intervals[-1] * self.exponent)
    return intervals

  def _BinIndex(self, item):
    """Get bin to which item belongs.

    E.g., if intervals are [0, 10], [10, 20], [20, 40], [40, 80],
    _BinIndex(25) is 2, and _BinIndex(50) is 3.
    Bin numbers are 0-based.

    Args:
      item: data item

    Returns:
      bin to which item belongs, assuming 0-based binning.
    """



    if item <= self.start:

      return 0
    else:





      itembin = math.ceil(math.log(float(item)/self.start, self.exponent))
      return int(itembin)


def URLFreqRespTime(urlstatsdict):
  """Computes request counts in different response time ranges for histograms.

  Args:
    urlstatsdict: A dictionary. Key is url path. Value is appropriate
        URLStats object which contains appstats statistics for the path.

  Returns:
    resptime_byfreq: A list of 3-tuples, one per URL, sorted in descending
        order of the number of requests seen by each URL. The elements of each
        tuple are (i) URL path; (ii) sorted list of response times of all
        requests corresponding to that URL; and (iii) a list of request counts
        in each latency bin for that URL.
    intervals: A list of latency ranges that requests of each URL are
        binned into. Each latency range is represented by the upper end of the
        range. E.g., if we are binning requests into latency ranges
        [0, 10], [11, 20], [21, 40], ... [1601, 3200]. Then, intervals is
        represented by the list [10, 20, 40,...,3200]
  """
  resptime = []


  binner = _ExponentialBinner(10, 2)
  maxbins = 0
  for url, urlstats in urlstatsdict.iteritems():
    urlresptime = sorted(urlstats.GetResponseTimeList())
    urlbin = binner.Bin(urlresptime)


    maxbins = max(maxbins, len(urlbin))
    resptime.append((url, urlresptime, urlbin))

  resptime.sort(key=lambda triple: len(triple[1]), reverse=True)
  intervals = binner.Intervals(maxbins)
  return resptime, intervals


def _GetPercentile(sortedlist, percent):
  """Returns a desired percentile value of a sorted list of numbers.

  E.g., if a list of request latencies is
  [1, 4, 7, 14, 34, 89, 100, 123, 149, 345], and percent is 0.9, the result
  is 149. If percent is 0.5 (median), result is 34.

  Args:
    sortedlist: A sorted list of integers, longs or floats.
    percent: A fraction between 0 and 1 that indicates desired
      percentile value. E.g., 0.9 means 90th percentile is desired.
  Returns:
    None if list is empty. Else, the desired percentile value.
  """
  if not sortedlist:
    return None




  k = int(math.ceil(len(sortedlist) * percent)) - 1
  if k < 0:


    k = 0
  return sortedlist[k]


def _GetPercentileList(items, percentilelist):
  """Given a list, returns a list of desired percentile values.

  Args:
    items: A list of integers, longs or floats.
    percentilelist: A list of fractions, each  between 0 and 1 that indicates
      desired percentile value. E.g., [0.1, 0.9] means 10th and 90th
      percentiles are desired.
  Returns:
    None if list is empty. Else, the list of desired percentile values.

  """
  if not items:
    return None
  sortedlist = sorted(items)
  return [_GetPercentile(sortedlist, p) for p in percentilelist]


class RequestSummary(object):
  """Summarizes request statistics for UI.

    The class summarizes the timestamps, latencies and total rpc time of all
    requests of a given URL path. An object of this class will then be passed
    to the UI for display of the page that drills into specific a URL path.
  """

  def __init__(self):
    self.timestamps = []
    self.totaltimes = []
    self.totalrpctimes = []


def Summary(urlstats):
  """Summarize relevant statistics for requests.

  Args:
    urlstats: A list of URLStat objects, which provide statistics for
      each request of a given URL path.

  Returns:
    A RequestSummary object which provides the timestamps, latencies
    and total rpc times for all requests of a given URL path. Each list
    is ordered in chronological order.
  """
  summary = RequestSummary()

  for request in reversed(urlstats.urlrequestlist):
    summary.timestamps.append(request.timestamp)
    summary.totaltimes.append(request.totalresponsetime)
    summary.totalrpctimes.append(request.totalrpctime)
  return summary


class RPCSummary(object):
  """Summarize RPC statistics for UI.

    The class summarizes information relevant to each RPC category
    such as the number of requests, number of calls, time spent in
    each RPC etc. There is one object per RPC category.  Objects of
    this class will be passed to the UI for display of the page that
    drills into specific a URL path.
  """

  def __init__(self):

    self.requests = 0

    self.calls = 0

    self.times = []

    self.indices = []

    self.stats = []

    self.summary_time = 0


def SortedRPCSummaries(urlstats, summary_percentile):
  """Summarize RPC statistics of requests for UI.

  Args:
    urlstats: A list of URLStat objects, which provide statistics for
      each request of a given URL path.
    summary_percentile: Summarize the time spent in an RPC across
      different requests by this percentile value. RPCs are sorted in
      the decreasing order of this percentile value. E.g., 0.5 indicates
      RPC times are summarized and sorted by the median.

  Returns:
    A list of tuples. The first element of each tuple is an RPC category
    label. The second element is an RPCSummary object which summarizes
    statistics about that RPC category. Summarizing data in this form is
    convenient for rendering UI on the drill page, particularly for bar
    charts showing times spent in various RPCs across different requests.
    The list is sorted in decreasing order of the summary_percentile of time
    spent in that RPC. This is the order in which RPCs will be rendered in
    the UI.
  """
  rpcsummary = {}

  for (index, request) in enumerate(reversed(urlstats.urlrequestlist)):
    for rpc in request.rpcstatslist:
      label = rpc.GetLabel()
      if label not in rpcsummary:
        rpcsummary[label] = RPCSummary()
      summary = rpcsummary[label]
      summary.requests += 1
      summary.calls += rpc.numcalls
      summary.times.append(rpc.time)
      summary.indices.append(index)
      successful_reads = len(rpc.keys_read) - len(rpc.keys_failed_get)
      summary.stats.append((rpc.numcalls,
                            successful_reads,
                            len(rpc.keys_written),
                            len(rpc.keys_failed_get)))


  for label in rpcsummary:
    summary = _GetPercentile(sorted(rpcsummary[label].times),
                             summary_percentile)
    rpcsummary[label].summary_time = summary
  rpcsummary_sort = sorted(rpcsummary.iteritems(),
                           key=lambda pair: pair[1].summary_time,
                           reverse=True)
  return rpcsummary_sort


def RPCVariation(reqsummary, rpcsummaries):
  """Generates desired percentiles of times spent in each RPC.

  Produces results useful for a candlestick chart that shows variation
  in time spent across different RPCs. Currently, the candlestick chart
  shows the 10th, 25th, 75th and 90th percentiles of RPC times.

  Args:
    reqsummary: A reqsummary object.
    rpcsummaries: a list of tuples generated by the SortedRPCSummaries
        function. In each tuple, the first element is an RPC category name
        and the second element is a dictionary containing information
        about the RPC category, particularly time spent in that RPC category
        across URL requests.

  Returns:
    A list of lists. Each inner list contains delay percentiles for each RPC.
  """
  rpc_variation = []

  markers = [0.1, 0.25, 0.75, 0.9]
  percentiles = _GetPercentileList(reqsummary.totaltimes, markers)
  percentiles.insert(0, 'Total')
  rpc_variation.append(percentiles)

  percentiles = _GetPercentileList(reqsummary.totalrpctimes, markers)
  percentiles.insert(0, 'TotalRPCTime')
  rpc_variation.append(percentiles)

  for pair in rpcsummaries:
    percentiles = _GetPercentileList(pair[1].times, markers)
    percentiles.insert(0, pair[0])
    rpc_variation.append(percentiles)
  return rpc_variation


def SplitByKind(freqdict):
  """Arranges entity/entity group access counts by their kind.

  Args:
    freqdict: a dict with keys corresponding to entities or entity
        groups. Value is a dict with 3 keys, 'read', 'write', 'missed',
        the values of which correspond to the appropriate counts for
        that entity.

  Returns:
    kinds_bycount: A list of <kind, entitiesOfKind> tuples, one per entity
        (group) kind sorted in decreasing order of number of entities
        (entity groups) of each kind. entitiesOfKind is a list of
        tuples, one per entity (group) of that kind, sorted in decreasing order
        of the access count of that entity (group). Each tuple consists of the
        name of the entity (group), along with read, write and miss counts.
    maxcount: The maximum access count seen by any entity of any kind.
  """



  kinds = {}
  for kind_fullname, freq in freqdict.items():
    (kind, fullname) = kind_fullname.split(',')
    if not kind in kinds:
      kinds[kind] = []
    kinds[kind].append((fullname, freq['read'],
                        freq['write'], freq['miss']))



  for kind in kinds:


    kinds[kind].sort(key=lambda ent: ent[1] + ent[2], reverse=True)

  kinds_bycount = sorted(kinds.iteritems(),
                         key=lambda pair: len(pair[1]), reverse=True)

  maxcount = 0
  for kind in kinds:
    maxcount = max(maxcount, kinds[kind][0][1] + kinds[kind][0][2])
  return kinds_bycount, maxcount


class Drill(object):
  """Data structures to be passed to UI for rendering drill page."""

  def __init__(self):
    self.reqsummary = None
    self.rpcsummaries = []
    self.groupcounts = []
    self.maxgroupcount = None
    self.entitycounts = []
    self.maxentitycount = None
    self.rpc_variation = []

  def _ToJsonDrill(self):
    """Encodes data for drill page in JSON for UI.

    Returns:
      drill_json: A dictionary representation of the class with attributes
          encoded into JSON as necessary for the UI.
    """
    drill_json = dict(self.__dict__)



    drill_json['rpcsummaries'] = [(l, s.requests, s.calls,
                                   json.dumps(s, cls=_RPCSummaryEncoder))
                                  for (l, s) in self.rpcsummaries]



    drill_json['groupcounts'] = [(k, len(v), json.dumps(v))
                                 for (k, v) in self.groupcounts]
    drill_json['entitycounts'] = [(k, len(v), json.dumps(v))
                                  for (k, v) in self.entitycounts]
    return drill_json


class _RPCSummaryEncoder(json.JSONEncoder):
  """JSON encoder for class RPCSummary."""

  def default(self, obj):
    """Arranges entity/entity group access counts by their kind.

    Args:
      obj: an object whose JSON encoding is desired.
    Returns:
      JSON encoding of obj.
    """
    if not isinstance(obj, RPCSummary):
      return json.JSONEncoder.default(self, obj)
    return obj.__dict__


def DrillURL(urlstats):
  """Analyzes URL statistics and generates data for drill page.

  Master function that calls all necessary functions to compute
  various data structures needed for rendering the drill page
  which shows details about a particular URL path.

  Args:
    urlstats: An URLStats object which holds appstats information
      about all requests of an URL path.
  Returns:
    drill: An object of class Drill with attributes encoded into JSON
      as necessary for the UI.
  """
  drill = Drill()
  drill.reqsummary = Summary(urlstats)



  drill.rpcsummaries = SortedRPCSummaries(urlstats, 0.9)
  drill.rpc_variation = RPCVariation(drill.reqsummary, drill.rpcsummaries)
  groupcounts = urlstats.EntityGroupCount()
  drill.groupcounts, drill.maxgroupcount = SplitByKind(groupcounts)
  entitycounts = urlstats.EntityCount()
  drill.entitycounts, drill.maxentitycount = SplitByKind(entitycounts)
  drill_json = drill._ToJsonDrill()
  return drill_json
