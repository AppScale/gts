import json
import sys

from appscale.common import appscale_info
from hermes_constants import REQUEST_TIMEOUT, HERMES_PORT, SECRET_HEADER
from tornado import gen, httpclient

from appscale.hermes.stats import StatsSource
from appscale.hermes.stats import proxy_stats, node_stats, process_stats


class BadStatsListFormat(ValueError):
  pass


class ClusterNodesStatsSource(StatsSource):

  def __init__(self, local_cache, include_lists=None, limit=None):
    super(ClusterNodesStatsSource, self).__init__('ClusterNodesStats')
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit

  def get_current(self):
    return self.new_nodes_stats_async().result()

  @gen.coroutine
  def new_nodes_stats_async(self):
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
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/node/cache',
        fromdict_convertor=node_stats.node_stats_snapshot_from_dict,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists,
        limit=self._limit
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


class ClusterProcessesStatsSource(StatsSource):

  def __init__(self, local_cache, include_lists=None, limit=None):
    super(ClusterProcessesStatsSource, self).__init__('ClusterProcessesStats')
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit

  def get_current(self):
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
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/processes/cache',
        fromdict_convertor=process_stats.processes_stats_snapshot_from_dict,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists,
        limit=self._limit
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


class ClusterProxiesStatsReader(StatsSource):

  def __init__(self, local_cache, include_lists=None, limit=None):
    super(ClusterProxiesStatsReader, self).__init__('ClusterProxiesStats')
    self._utc_timestamp_cursors = {}
    self._local_cache = local_cache
    self._include_lists = include_lists
    self._limit = limit

  def get_current(self):
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
    if node_ip == appscale_info.get_private_ip():
      new_snapshots = self._local_cache.get_stats_after(last_utc_timestamp)
    else:
      new_snapshots = yield _fetch_remote_stats_cache_async(
        node_ip=node_ip, method_path='stats/local/proxies/cache',
        fromdict_convertor=proxy_stats.proxies_stats_snapshot_from_dict,
        last_utc_timestamp=last_utc_timestamp,
        include_lists=self._include_lists,
        limit=self._limit
      )
    if new_snapshots:
      self._utc_timestamp_cursors[node_ip] = new_snapshots[-1].utc_timestamp
    raise gen.Return(new_snapshots)


def _fetch_remote_stats_cache_async(node_ip, method_path, fromdict_convertor,
                                    last_utc_timestamp=None, limit=None,
                                    include_lists=None):
  # Security header
  headers = {SECRET_HEADER: appscale_info.get_secret()}
  # Build query arguments
  arguments = {}
  if last_utc_timestamp is not None:
    arguments['last_utc_timestamp'] = last_utc_timestamp
  if limit is not None:
    arguments['limit'] = limit
  if include_lists is not None:
    arguments['include_lists'] = include_lists

  url = "http://{ip}:{port}/{path}".format(
    ip=node_ip, port=HERMES_PORT, path=method_path)
  request = httpclient.HTTPRequest(
    url=url, method='GET', body=json.dumps(arguments), headers=headers,
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
