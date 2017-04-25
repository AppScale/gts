import os
import sys

import attr
import urllib

import json
from tornado import gen, httpclient

from hermes_constants import REQUEST_TIMEOUT, HERMES_PORT, SECRET_HEADER
from stats import node_stats, process_stats, proxy_stats
from stats.tools import stats_reader

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


@attr.s(cmp=False, hash=False, slots=True)
class ClusterStats(object):
  latest_node_stats = attr.ib(default=attr.Factory(dict))
  latest_processes_stats = attr.ib(default=attr.Factory(dict))
  latest_proxies_stats = attr.ib(default=attr.Factory(dict))

  def set_latest_node_stats(self, snapshots_from_nodes):
    self.latest_node_stats = {
      ip: (snapshots[-1] if snapshots else None)
      for ip, snapshots in snapshots_from_nodes.iteritems()
    }

  def set_latest_processes_stats(self, snapshots_from_nodes):
    self.latest_node_stats = {
      ip: (snapshots[-1] if snapshots else None)
      for ip, snapshots in snapshots_from_nodes.iteritems()
    }

  def set_latest_proxies_stats(self, snapshots_from_lb_nodes):
    self.latest_node_stats = {
      ip: (snapshots[-1] if snapshots else None)
      for ip, snapshots in snapshots_from_lb_nodes.iteritems()
    }


class BadStatsListFormat(ValueError):
  pass


class ClusterNodeStatsReader(object):

  def __init__(self, include_fields=None, limit=None):
    self._utc_timestamp_cursors = {}
    self._include_fields = include_fields
    self._limit = limit

  @stats_reader("ClusterNodesStats")
  def new_node_stats(self):
    return self.new_node_stats_async().result()

  @gen.coroutine
  def new_node_stats_async(self):
    all_ips = appscale_info.get_all_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_node_stats_dict = yield {
      node_ip: self._new_node_stats_from_node_async(node_ip)
      for node_ip in all_ips
    }
    raise gen.Return(per_node_node_stats_dict)

  @gen.coroutine
  def _new_node_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    new_snapshots = yield _fetch_remote_stats_async(
      node_ip=node_ip, method_path='stats/node',
      fromdict_convertor=node_stats.NodeStatsSnapshot.fromdict,
      last_utc_timestamp=last_utc_timestamp,
      include_fields=self._include_fields,
      limit=self._limit
    )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


class ClusterProcessesStatsReader(object):

  def __init__(self, include_fields=None, limit=None):
    self._utc_timestamp_cursors = {}
    self._include_fields = include_fields
    self._limit = limit

  @stats_reader("ClusterProcessesStats")
  def new_processes_stats(self):
    return self.new_processes_stats_async().result()

  @gen.coroutine
  def new_processes_stats_async(self):
    all_ips = appscale_info.get_all_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_processes_stats_dict = yield {
      node_ip: self._new_processes_stats_from_node_async(node_ip)
      for node_ip in all_ips
    }
    raise gen.Return(per_node_processes_stats_dict)

  @gen.coroutine
  def _new_processes_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    new_snapshots = yield _fetch_remote_stats_async(
      node_ip=node_ip, method_path='stats/processes',
      fromdict_convertor=process_stats.ProcessesStatsSnapshot.fromdict,
      last_utc_timestamp=last_utc_timestamp,
      include_fields=self._include_fields,
      limit=self._limit
    )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)



class ClusterProxiesStatsReader(object):

  def __init__(self, include_fields=None, limit=None):
    self._utc_timestamp_cursors = {}
    self._include_fields = include_fields
    self._limit = limit

  @stats_reader("ClusterProxiesStats")
  def new_proxies_stats(self):
    return self.new_proxies_stats_async().result()

  @gen.coroutine
  def new_proxies_stats_async(self):
    lb_ips = appscale_info.get_load_balancer_ips()
    # Do multiple requests asynchronously and wait for all results
    per_node_proxies_stats_dict = yield {
      node_ip: self._new_proxies_stats_from_node_async(node_ip)
      for node_ip in lb_ips
    }
    raise gen.Return(per_node_proxies_stats_dict)

  @gen.coroutine
  def _new_proxies_stats_from_node_async(self, node_ip):
    last_utc_timestamp = self._utc_timestamp_cursors.get(node_ip)
    new_snapshots = yield _fetch_remote_stats_async(
      node_ip=node_ip, method_path='stats/proxies',
      fromdict_convertor=proxy_stats.ProxiesStatsSnapshot.fromdict,
      last_utc_timestamp=last_utc_timestamp,
      include_fields=self._include_fields,
      limit=self._limit
    )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


def _fetch_remote_stats_async(node_ip, method_path, fromdict_convertor,
                              last_utc_timestamp=None, limit=None,
                              include_fields=None):
  # Security header
  headers = {SECRET_HEADER: appscale_info.get_secret()}
  # Build query arguments
  arguments = {}
  if last_utc_timestamp is not None:
    arguments['last_utc_timestamp'] = last_utc_timestamp
  if limit is not None:
    arguments['limit'] = limit
  if include_fields is not None:
    arguments['include'] = include_fields

  url = "http://{ip}:{port}/{path}".format(
    ip=node_ip, port=HERMES_PORT, path=method_path)
  request = httpclient.HTTPRequest(
    url=url, method='GET', body=urllib.urlencode(arguments), headers=headers,
    validate_cert=False, request_timeout=REQUEST_TIMEOUT
  )
  async_client = httpclient.AsyncHTTPClient()

  # Send Future object to coroutine and suspend till result is ready
  response = yield async_client.fetch(request)

  try:
    stats_dictionaries = json.loads(response.body)
    snapshots = [
      fromdict_convertor(stats_dict)
      for stats_dict in stats_dictionaries
    ]
  except (ValueError, TypeError, IndexError) as err:
    msg = u"Can parse stats snapshot ({})".format(err)
    raise BadStatsListFormat(msg), None, sys.exc_info()[2]

  raise gen.Return(snapshots)
