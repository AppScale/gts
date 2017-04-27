import json
import logging

from appscale.common import appscale_info
from tornado.web import RequestHandler

from appscale.hermes.constants import SECRET_HEADER


class Respond404Handler(RequestHandler):
  def initialize(self, reason):
    self.reason = reason
    
  def get(self):
    self.set_status(404, self.reason)


class CachedStatsHandler(RequestHandler):
  """ Handler for reading node/processes/proxies stats history
  """

  def initialize(self, stats_cache):
    self._stats_cache = stats_cache
    self._secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self._secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    payload = json.loads(self.request.body)
    last_utc_timestamp = payload.get('last_utc_timestamp')
    limit = payload.get('limit')
    include_lists = payload.get('include_lists')

    snapshots = self._stats_cache.get_stats_after(last_utc_timestamp)
    if limit:
      snapshots = snapshots[:limit]

    rendered_dictionaries = [
      snapshot.todict(include_lists) for snapshot in snapshots
    ]
    json.dump(rendered_dictionaries, self)


class CurrentStatsHandler(RequestHandler):
  """ Handler for getting node/processes/proxies current stats
  """
  def initialize(self, stats_source):
    self._stats_source = stats_source
    self._secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self._secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    payload = json.loads(self.request.body)
    include_lists = payload.get('include_lists')

    snapshot = self._stats_source.get_current()

    json.dump(snapshot.todict(include_lists), self)


class ClusterStatsHandler(RequestHandler):
  """ Handler for getting cluster stats:
      Node stats, Processes stats and Proxies stats for all nodes
  """
  def initialize(self, cluster_stats_cache):
    self._cluster_stats_cache = cluster_stats_cache
    self._secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get(SECRET_HEADER) != self._secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
      return
    payload = json.loads(self.request.body)
    include_lists = payload.get('include_lists')

    nodes_stats = self._cluster_stats_cache.get_latest()

    rendered_dictionaries = {
      node_ip: snapshot.todict(include_lists)
      for node_ip, snapshot in nodes_stats.iteritems()
    }
    json.dump(rendered_dictionaries, self)
