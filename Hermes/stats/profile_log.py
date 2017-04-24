from stats.tools import stats_subscriber


class NodeStatsProfileLog(object):
  @stats_subscriber("NodeStatsProfileLog")
  def write_snapshot(self, stats_snapshot):
    pass


class ProcessesStatsProfileLog(object):
  @stats_subscriber("ProcessesStatsProfileLog")
  def write_snapshot(self, stats_snapshot):
    pass


class ProxiesStatsProfileLog(object):
  @stats_subscriber("ProxiesStatsProfileLog")
  def write_snapshot(self, stats_snapshot):
    pass


class ClusterProfileLog(object):
  pass