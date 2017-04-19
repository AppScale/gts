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



class _AppScaleNamesMapper(object):
  @attr.s(cmp=False, hash=False, slots=True, frozen=True)
  class Service(object):
    service_name = attr.ib()
    monit_matcher = attr.ib(default=None, convert=re.compile)
    haproxy_proxy_matcher = attr.ib(default=None, convert=re.compile)
    haproxy_server_matcher = attr.ib(default=None, convert=re.compile)

    def recognize_monit_process(self, monit_process_name):
      return self.monit_matcher.find(monit_process_name) is not None

    def recognize_haproxy_proxy(self, proxy_name):
      return self.haproxy_proxy_matcher.find(proxy_name) is not None
    
    def server_name_by_haproxy_svname(self, svname):
      match = self.haproxy_server_matcher.find(svname)
      if not match:
        return svname
      ip = match.group('ip')
      port = match.group('port')
      application = match.group('app')
      # TODO

    def server_name_by_monit_process_name(self, process_name, private_ip):
      # TODO
      pass

  services = [
    Service(service_name='zookeeper',
                 monit_pattern=),
    Service(service_name='uaserver',
                 monit_pattern=),
    Service(service_name='taskqueue',
                 monit_pattern=),
    Service(service_name='rabbitmq',
                 monit_pattern=),
    Service(service_name='nginx',
                 monit_pattern=),
    Service(service_name='log_service',
                 monit_pattern=),
    Service(service_name='iaas_manager',
                 monit_pattern=),
    Service(service_name='hermes',
                 monit_pattern=),
    Service(service_name='haproxy',
                 monit_pattern=),
    Service(service_name='groomer',
                 monit_pattern=),
    Service(service_name='flower',
                 monit_pattern=),
    Service(service_name='ejabberd',
                 monit_pattern=),
    Service(service_name='datastore',
                 monit_pattern=),
    Service(service_name='controller',
                 monit_pattern=),
    Service(service_name='celery',
                 monit_pattern=),
    Service(service_name='cassandra',
                 monit_pattern=),
    Service(service_name='backup_recovery_service',
                 monit_pattern=),
    Service(service_name='memcached',
                 monit_pattern=),
    Service(service_name='blobstore',
                 monit_pattern=),
    Service(service_name='appmanager',
                 monit_pattern=),
    Service(service_name='application',
                 monit_pattern=),
  ]
  r'(?P<prefix>uaserver)'
  r'(?P<prefix>taskqueue)-(?P<port>\d+)'
  r'(?P<prefix>rabbitmq)'
  r'(?P<prefix>nginx)'
  r'(?P<prefix>log_service)'
  r'(?P<prefix>iaas_manager)'
  r'(?P<prefix>hermes)'
  r'(?P<prefix>haproxy)'
  r'(?P<prefix>groomer_service)'
  r'(?P<prefix>flower)'
  r'(?P<prefix>ejabberd)'
  r'(?P<prefix>datastore_server)-(?P<port>\d+)'
  r'(?P<prefix>controller)'
  r'(?P<prefix>celery)-(?P<app>[a-zA-Z]\w+[a-zA-Z\d])-(?P<port>\d+)'
  r'(?P<prefix>cassandra)'
  r'(?P<prefix>backup_recovery_service)'
  r'(?P<prefix>memcached)'
  r'(?P<prefix>blobstore)'
  r'(?P<prefix>appmanagerserver)'
  r'(?P<prefix>app___)(?P<app>[a-zA-Z]\w+[a-zA-Z\d])-(?P<port>\d+)'
  'TaskQueue'
  'UserAppServer'
  'appscale-datastore_server'
  'as_blob_server'
  'gae_appscaledashboard'
  'gae_guestbook27'


class MonitNames(object):
  def get_service_name(self, ...):
    pass
  def get_server_name(self, ...):
    pass


class HAProxyNames(object):
  def get_service_name(self, ...):
    pass
  def get_server_name(self, ...):
    pass
