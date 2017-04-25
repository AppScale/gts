import json
import logging
import os
import sys

import attr
from tornado.web import RequestHandler

from hermes_constants import SECRET_HEADER

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info


class Respond404Handler(RequestHandler):
  def initialize(self, reason):
    self.reason = reason
    
  def get(self):
    self.set_status(404, self.reason)


class NodeStatsHandler(RequestHandler):
  """ Handler for getting node stats
  """
  def initialize(self, node_stats_buffer):
    self.stats_buffer = node_stats_buffer
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    last_utc_timestamp = self.request.get_argument('last_utc_timestamp', 0)
    limit = self.request.get_argument('limit', None)
    include = self.request.get_arguments('include', None)

    self.write(json.dumps(self.stats_collector.cluster_stats.my_node))

    attr.asdict(filter=attr.filters.)


class ProcessesStatsHandler(RequestHandler):
  """ Handler for getting processes stats
  """
  def initialize(self, processes_stats_buffer):
    self.stats_buffer = processes_stats_buffer
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    self.write(json.dumps(self.stats_collector.cluster_stats.my_node))


class ProxiesStatsHandler(RequestHandler):
  """ Handler for getting proxies stats
  """
  def initialize(self, proxies_stats_buffer):
    self.stats_buffer = proxies_stats_buffer
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    self.write(json.dumps(self.stats_collector.cluster_stats.my_node))


class ClusterStatsHandler(RequestHandler):
  """ Handler for getting cluster stats:
      Node stats, Processes stats and Proxies stats for all nodes
  """
  def initialize(self, current_cluster_stats):
    self.current_cluster_stats = current_cluster_stats
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    self.write(json.dumps({
      'nodes': self.stats_collector.cluster_stats.nodes,
      'services': self.stats_collector.cluster_stats.services
    }))
