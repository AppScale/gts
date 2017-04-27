from appscale.hermes.stats.pubsub_base import StatsSubscriber


class ClusterNodesProfileLog(StatsSubscriber):
  def __init__(self):
    super(ClusterNodesProfileLog, self).__init__("ClusterNodesProfileLog")

  def receive(self, nodes_stats_dict):
    print()


class ClusterProcessesProfileLog(StatsSubscriber):
  def __init__(self):
    super(ClusterProcessesProfileLog, self).__init__("ClusterProcessesProfileLog")

  def receive(self, nodes_stats_dict):
    pass


class ClusterProxiesProfileLog(StatsSubscriber):
  def __init__(self):
    super(ClusterProxiesProfileLog, self).__init__("ClusterProxiesProfileLog")

  def receive(self, nodes_stats_dict):
    pass