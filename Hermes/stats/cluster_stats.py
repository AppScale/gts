import json
import logging
import os
import sys
import urllib

import attr
from tornado import httpclient, gen

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


SHOULD_NOT_READ = object()


@attr.s(cmp=False, hash=False, slots=True)
class StatsCursors(object):
  """ A container for utc timestamps for latest known snapshots """
  node_stats_utc_timestamp = attr.ib(default=0)
  processes_stats_utc_timestamp = attr.ib(default=0)
  haproxy_stats_utc_timestamp = attr.ib(default=0)


class ClusterStatsReader(object):

  def __init__(self):
    self._stats_cursors = {}

  def _update_stats_cursors(self):
    all_ips = appscale_info.get_all_ips()
    lb_ips = appscale_info.get_load_balancer_ips()
    new_cursors_dict = {}
    for ip in all_ips:
      stats_cursor = self._stats_cursors.get(ip)
      if not stats_cursor:
        stats_cursor = StatsCursors()
      if ip not in lb_ips:
        stats_cursor.haproxy_stats_utc_timestamp = SHOULD_NOT_READ
      new_cursors_dict[ip] = stats_cursor
    self._stats_cursors = new_cursors_dict

  def new_node_stats(self):
    return self.new_node_stats_async().result()

  def new_processes_stats(self):
    return self.new_processes_stats_async().result()

  def new_proxies_stats(self):
    return self.new_proxies_stats_async().result()

  @gen.coroutine
  def new_node_stats_async(self):
    self._update_stats_cursors()
    # Do multiple requests asynchronously and wait for all results
    per_node_node_stats_dict = yield {
      node_ip: self._new_node_stats_from_node_async(node_ip, stats_cursor)
      for node_ip, stats_cursor in self._stats_cursors.iteritems()
    }
    raise gen.Return(per_node_node_stats_dict)

  @gen.coroutine
  def new_processes_stats_async(self):
    self._update_stats_cursors()
    # Do multiple requests asynchronously and wait for all results
    per_node_processes_stats_dict = yield {
      node_ip: self._new_processes_stats_from_node_async(node_ip, stats_cursor)
      for node_ip, stats_cursor in self._stats_cursors.iteritems()
    }
    raise gen.Return(per_node_processes_stats_dict)

  @gen.coroutine
  def new_proxies_stats_async(self):
    self._update_stats_cursors()
    # Do multiple requests asynchronously and wait for all results
    per_node_proxies_stats_dict = yield {
      node_ip: self._new_proxies_stats_from_node_async(node_ip, stats_cursor)
      for node_ip, stats_cursor in self._stats_cursors.iteritems()
    }
    raise gen.Return(per_node_proxies_stats_dict)

  @gen.coroutine
  def _new_node_stats_from_node_async(self, node_ip, stats_cursor):
    pass

  @gen.coroutine
  def _new_processes_stats_from_node_async(self, node_ip, stats_cursor):
    pass

  @gen.coroutine
  def _new_proxies_stats_from_node_async(self, node_ip, stats_cursor):
    pass


  @gen.coroutine
  def get_service_stats_async(self):
    """Collects stats from all services asynchronously

    Returns:
      Future object which will have a result with
      dicts hierarchy containing statistics about services performance
      > { serviceName: {
      >       serverIP-Port: {
      >           method: {
      >               SUCCESS/errorName: (totalReqsSeen, totalTimeTaken) }}}
    """
    # Do multiple requests asynchronously and wait for all results
    servers_stats_dict = yield {
      service_name: stats_collector.get_all_servers_stats_async()
      for service_name, stats_collector in self._services.iteritems()
    }
    raise gen.Return(servers_stats_dict)

  @gen.coroutine
  def get_cluster_stats_async(self):
    """ Collects stats from all deployment nodes.

    Returns:
      A dictionary containing all the monitoring stats, for all nodes that are
      accessible.
    """
    my_private = appscale_info.get_private_ip()
    cluster_stats = yield {
      ip: self.get_node_stats_async(ip)
      for ip in appscale_info.get_all_ips() if ip != my_private
    }
    cluster_stats[my_private] = self._cluster_stats.my_node
    raise gen.Return(cluster_stats)

  @gen.coroutine
  def get_node_stats_async(self, appscale_node_ip):
    secret = {'secret': appscale_info.get_secret()}
    url = "http://{ip}:{port}/stats/node".format(
      ip=appscale_node_ip, port=hermes_constants.HERMES_PORT)
    request = helper.create_request(
      url, method='GET', body=urllib.urlencode(secret)
    )
    async_client = httpclient.AsyncHTTPClient()

    try:
      # Send Future object to coroutine and suspend till result is ready
      response = yield async_client.fetch(request)
    except httpclient.HTTPError as err:
      logging.error("Error while trying to fetch {}: {}".format(url, err))
      # Return nothing but don't raise an error
      raise gen.Return({})

    raise gen.Return(json.loads(response.body))
