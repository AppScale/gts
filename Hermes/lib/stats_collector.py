#!/usr/bin/env python


# General-purpose Python library imports.
import json
import logging
import os
import re
import subprocess
import sys

import urllib
from tornado import httpclient, gen

# Hermes imports.
import helper
import hermes_constants
from lib.infrastructure_manager_client import InfrastructureManagerClient

# AppServer imports.
sys.path.append(os.path.join(os.path.dirname(__file__), '../AppServer'))
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.api.datastore import datastore_pb

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


class AppScaleStats(object):
  def __init__(self):
    self.nodes = {}
    self.services = {}

  @property
  def my_node(self):
    return self.nodes.get(appscale_info.get_private_ip(), {})

  @my_node.setter
  def my_node(self, new_stats):
    self.nodes[appscale_info.get_private_ip()] = new_stats


class StatsCollector(object):

  _instance = None

  def __init__(self):
    self._cluster_stats = AppScaleStats()
    self._services = {
      'datastore_stats': TaskQueueStatsCollector(),
      'taskqueue_stats': DatastoreStatsCollector()
    }

  @classmethod
  def instance(cls):
    if not cls._instance:
      cls._instance = cls()
    return cls._instance

  @property
  def cluster_stats(self):
    return self._cluster_stats

  def update_node_stats(self):
    acc = appscale_info.get_appcontroller_client(head_node=False)
    stats = acc.get_node_stats()
    secret = appscale_info.get_secret()
    my_priv_ip = appscale_info.get_private_ip()
    imc = InfrastructureManagerClient(my_priv_ip, secret)
    sys = imc.get_system_stats()
    stats.update(sys)
    self._cluster_stats.my_node = stats
    logging.debug("Updated stats of my node: {}".format(stats))

  def update_cluster_stats(self):
    nodes_stats = self.get_cluster_stats_async().result()
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
    cluster_stats = yield [
      self.get_node_stats_async(ip)
      for ip in appscale_info.get_all_ips() if ip != my_private
    ]
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


class ServiceStatsCollector(object):
  def __init__(self, service_name):
    self.service_name = service_name

  @gen.coroutine
  def get_all_servers_stats_async(self):
    """Makes a request to each server to get their stats.

    Returns:
      Future object which will have a result with
      dicts hierarchy containing statistics about service performance:
      > { serverIP-Port: {
      >       method: {
      >           SUCCESS/ErrorName: (totalReqsSeen, totalTimeTaken) }}}
    """
    # Do multiple requests asynchronously and wait for all results
    servers_stats_dict = yield {
      ip_port: self.get_server_stats_async(ip_port)
      for ip_port in self.list_servers()
    }
    raise gen.Return(servers_stats_dict)

  def list_servers(self):
    haproxy_stats_socket = "/etc/haproxy/stats"
    servers = subprocess.check_output(
      "echo 'show stat' | socat stdio unix-connect:{} | grep {}"
      .format(haproxy_stats_socket, self.service_name), shell=True
    )
    # Match all IP:port and return as a list of strings
    pattern = r"{server}-([\d.]+:\d+)".format(server=self.service_name)
    return re.findall(pattern, str(servers))

  @gen.coroutine
  def get_server_stats_async(self, server_ip_port):
    url = "http://{ip_port}".format(ip_port=server_ip_port)
    request = helper.create_request(url, method='GET')
    async_client = httpclient.AsyncHTTPClient()

    try:
      # Send Future object to coroutine and suspend till result is ready
      response = yield async_client.fetch(request)
    except httpclient.HTTPError as err:
      logging.error("Error while trying to fetch {}: {}".format(url, err))
      # Return nothing but don't raise an error
      raise gen.Return({})

    db_info = json.loads(response.body)
    # Return node stats (e.g.:{'Commit': {'Success': (235, 12.53), ..}, ...})
    raise gen.Return({
      method: {
        self.error_name(error_code): (total_req, total_time)
        for error_code, (total_req, total_time) in stats.iteritems()
      }
      for method, stats in db_info.iteritems()
    })

  @staticmethod
  def error_name(error_code):
    raise NotImplemented


class TaskQueueStatsCollector(ServiceStatsCollector):
  def __init__(self):
    super(TaskQueueStatsCollector, self).__init__("TaskQueue")

  @staticmethod
  def error_name(error_code):
    if error_code == '0':
      return 'SUCCESS'
    return taskqueue_service_pb.Error.ErrorCode_Name(error_code)


class DatastoreStatsCollector(ServiceStatsCollector):
  def __init__(self):
    super(DatastoreStatsCollector, self).__init__("appscale-datastore_server")

  @staticmethod
  def error_name(error_code):
    if error_code == '0':
      return 'SUCCESS'
    return datastore_pb.Error.ErrorCode_Name(error_code)