""" Implementation of stats sources for cluster stats
(node, processes, proxies). """
import json
import logging
import sys
import time

from appscale.common import appscale_info
from tornado import gen, httpclient
from tornado.options import options

from appscale.hermes import constants
from appscale.hermes.constants import SECRET_HEADER
from appscale.hermes.stats import converter
from appscale.hermes.stats.constants import STATS_REQUEST_TIMEOUT
from appscale.hermes.stats.producers import (
  proxy_stats, node_stats, process_stats
)


class BadStatsListFormat(ValueError):
  """ Is used when Hermes slave responds with improperly formatted stats. """
  pass


class ClusterStatsSource(object):
  """
  Base class for current cluster stats sources.
  Gets new node/processes/proxies stats from all nodes in the cluster.
  """
  ips_getter = None
  method_path = None
  stats_model = None
  local_stats_source = None

  @gen.coroutine
  def get_current_async(self, newer_than=None, include_lists=None,
                        exclude_nodes=None):
    """ Makes concurrent asynchronous http calls to cluster nodes
    and collects current stats. Local stats is got from local stats source.

    Args:
      newer_than: UTC timestamp, allow to use cached snapshot if it's newer.
      include_lists: An instance of IncludeLists.
      exclude_nodes: A list of node IPs to ignore when fetching stats.
    Returns:
      A Future object which wraps a dict with node IP as key and
      an instance of stats snapshot as value.
    """
    exclude_nodes = exclude_nodes or []
    start = time.time()

    # Do multiple requests asynchronously and wait for all results
    stats_per_node = yield {
      node_ip: self._stats_from_node_async(node_ip, newer_than, include_lists)
      for node_ip in self.ips_getter() if node_ip not in exclude_nodes
    }
    logging.info("Fetched {stats} from {nodes} nodes in {elapsed:.1f}s."
                 .format(stats=self.stats_model.__name__,
                         nodes=len(stats_per_node),
                         elapsed=time.time() - start))
    raise gen.Return(stats_per_node)

  @gen.coroutine
  def _stats_from_node_async(self, node_ip, newer_than, include_lists):
    if node_ip == appscale_info.get_private_ip():
      snapshot = self.local_stats_source.get_current()
    else:
      snapshot = yield self._fetch_remote_stats_async(
        node_ip, newer_than, include_lists)
    raise gen.Return(snapshot)

  @gen.coroutine
  def _fetch_remote_stats_async(self, node_ip, newer_than, include_lists):
    # Security header
    headers = {SECRET_HEADER: options.secret}
    # Build query arguments
    arguments = {}
    if include_lists is not None:
      arguments['include_lists'] = include_lists.asdict()
    if newer_than:
      arguments['newer_than'] = newer_than

    url = "http://{ip}:{port}/{path}".format(
      ip=node_ip, port=constants.HERMES_PORT, path=self.method_path)
    request = httpclient.HTTPRequest(
      url=url, method='GET', body=json.dumps(arguments), headers=headers,
      request_timeout=STATS_REQUEST_TIMEOUT, allow_nonstandard_methods=True
    )
    async_client = httpclient.AsyncHTTPClient()

    # Send Future object to coroutine and suspend till result is ready
    response = yield async_client.fetch(request, raise_error=False)
    if response.code >= 400:
      if response.body:
        logging.error(
          "Failed to get stats from {url} ({code} {reason})"
          .format(url=url, code=response.code, reason=response.reason)
        )
      else:
        logging.error(
          "Failed to get stats from {url} ({code} {reason}, BODY: {body})"
          .format(url=url, code=response.code, reason=response.reason,
                  body=response.body)
        )
      raise gen.Return(None)

    try:
      snapshot = json.loads(response.body)
      raise gen.Return(converter.stats_from_dict(self.stats_model, snapshot))
    except TypeError as err:
      msg = u"Can't parse stats snapshot ({})".format(err)
      raise BadStatsListFormat(msg), None, sys.exc_info()[2]


class ClusterNodesStatsSource(ClusterStatsSource):
  ips_getter = staticmethod(appscale_info.get_all_ips)
  method_path = 'stats/local/node'
  stats_model = node_stats.NodeStatsSnapshot
  local_stats_source = node_stats.NodeStatsSource


class ClusterProcessesStatsSource(ClusterStatsSource):
  ips_getter = staticmethod(appscale_info.get_all_ips)
  method_path = 'stats/local/processes'
  stats_model = process_stats.ProcessesStatsSnapshot
  local_stats_source = process_stats.ProcessesStatsSource


class ClusterProxiesStatsSource(ClusterStatsSource):
  ips_getter = staticmethod(appscale_info.get_load_balancer_ips)
  method_path = 'stats/local/proxies'
  stats_model = proxy_stats.ProxiesStatsSnapshot
  local_stats_source = proxy_stats.ProxiesStatsSource
