from appscale.hermes.stats.pubsub_base import StatsSubscriber


class ClusterNodesProfileLog(StatsSubscriber):

  def __init__(self, include_lists):
    pass

  def receive(self, nodes_stats_dict):
    pass


class ClusterProcessesProfileLog(StatsSubscriber):

  def receive(self, processes_stats_dict):
    pass


class ClusterProxiesProfileLog(StatsSubscriber):

  def receive(self, proxies_stats_dict):
    pass
