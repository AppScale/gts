from appscale.hermes.stats.pubsub_base import StatsSubscriber


class ClusterNodesProfileLog(StatsSubscriber):

  def receive(self, nodes_stats_dict):
    pass


class ClusterProcessesProfileLog(StatsSubscriber):

  def receive(self, nodes_stats_dict):
    pass


class ClusterProxiesProfileLog(StatsSubscriber):

  def receive(self, nodes_stats_dict):
    pass