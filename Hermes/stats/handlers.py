import json
import logging
import os
import sys

from tornado.web import RequestHandler

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info


class NodeStatsHandler(RequestHandler):
  """ Handler for getting current node stats
  """
  def __init__(self, *args, **kwargs):
    super(NodeStatsHandler, self).__init__(*args, **kwargs)
    self.stats_collector = StatsManager.instance()
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get('Appscale-Secret') != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
    else:
      self.write(json.dumps(self.stats_collector.cluster_stats.my_node))


class ClusterStatsHandler(RequestHandler):
  """ Handler for getting cluster stats:
      Nodes stats + Services stats
  """
  def __init__(self, *args, **kwargs):
    super(ClusterStatsHandler, self).__init__(*args, **kwargs)
    self.stats_collector = StatsManager.instance()
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.request.headers.get('Appscale-Secret') != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
    else:
      self.write(json.dumps({
        'nodes': self.stats_collector.cluster_stats.nodes,
        'services': self.stats_collector.cluster_stats.services
      }))
