import json
import logging
import os
import re
import subprocess
import sys

import urllib

import attr
from tornado import httpclient, gen

# Hermes imports.
import helper
import hermes_constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


class StatsMaster(object):

  _instance = None

  def __init__(self):
    self._node_resources = {}    # dict[private_ip, NodeStats]
    self._node_processes = {}    # dict[private_ip, list[ProcessStats]]
    self._lb_services = {}       # dict[lb_ip, list[ProxyStats]]
    self._is_profiling_enabled = False

  @classmethod
  def instance(cls):
    if not cls._instance:
      cls._instance = cls()
    return cls._instance

  @property
  def node_resources(self):
    return self._node_resources

  @property
  def node_processes(self):
    return self._node_processes

  @property
  def services(self):
    return self._services

  @property
  def is_profiling_enabled(self):
    return self._is_profiling_enabled

  def enable_profiling(self):
    self._is_profiling_enabled = True

  def update_stats(self):
    nodes_stats = self.get_stats_async().result()
    self._cluster_stats.nodes = nodes_stats
    logging.debug("Updated cluster stats: {}".format(nodes_stats))

  def update_services_stats(self):
    services_stats = self.get_service_stats_async().result()
    self._cluster_stats.services = services_stats
    logging.debug("Updated service stats: {}".format(services_stats))

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
