import csv
from os import path, makedirs

from appscale.hermes.stats import converter
from appscale.hermes.stats.producers import node_stats
from appscale.hermes.stats.pubsub_base import StatsSubscriber
from appscale.hermes.stats.constants import PROFILE_LOG_DIR


class ClusterNodesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    self._header = converter.get_stats_header(
      node_stats.NodeStatsSnapshot, include_lists)
    self._include_lists = include_lists
    self._directory = path.join(PROFILE_LOG_DIR, 'node')
    if not path.exists(self._directory):
      makedirs(self._directory)

  def receive(self, nodes_stats_dict):
    for node_ip, snapshots in nodes_stats_dict.iteritems():
      with self._prepare_file(node_ip) as csv_file:
        writer = csv.writer(csv_file)
        for snapshot in snapshots:
          row = converter.stats_to_list(snapshot, self._include_lists)
          writer.writerow(row)

  def _prepare_file(self, node_ip):
    file_name = path.join(self._directory, '{}.csv'.format(node_ip))
    if not path.exists(file_name):
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    return open(file_name, 'a')


class ClusterProcessesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    pass

  def receive(self, processes_stats_dict):
    pass


class ClusterProxiesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    pass

  def receive(self, proxies_stats_dict):
    pass
