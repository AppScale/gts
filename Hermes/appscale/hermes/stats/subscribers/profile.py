import csv
import errno
from os import path, makedirs

from appscale.hermes.stats import converter
from appscale.hermes.stats.producers import node_stats
from appscale.hermes.stats.pubsub_base import StatsSubscriber
from appscale.hermes.stats.constants import PROFILE_LOG_DIR


class ClusterNodesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    """ Initializes profile log for cluster node stats.
    Renders header according to include_lists in advance and
    creates base directory for node stats profile log.

    Args:
      include_lists: an instance of IncludeLists describing which fields
          of node stats should be written to CSV log.
    """
    self._header = converter.get_stats_header(
      node_stats.NodeStatsSnapshot, include_lists)
    self._include_lists = include_lists
    self._directory = path.join(PROFILE_LOG_DIR, 'node')
    try:
      makedirs(self._directory)
    except OSError as os_error:
      if os_error.errno == errno.EEXIST and path.isdir(self._directory):
        pass
      else:
        raise

  def receive(self, nodes_stats_dict):
    """ Implements receive method of base class. Saves newly produced
    cluster node stats to a list of CSV files (file per node).

    Args:
      nodes_stats_dict: a dict with node IP as key and list of
          NodeStatsSnapshot as value
    """
    for node_ip, snapshots in nodes_stats_dict.iteritems():
      with self._prepare_file(node_ip) as csv_file:
        writer = csv.writer(csv_file)
        for snapshot in snapshots:
          row = converter.stats_to_list(snapshot, self._include_lists)
          writer.writerow(row)

  def _prepare_file(self, node_ip):
    file_name = path.join(self._directory, '{}.csv'.format(node_ip))
    if not path.isfile(file_name):
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    return open(file_name, 'a')


class ClusterProcessesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    # TODO
    pass

  def receive(self, processes_stats_dict):
    # TODO
    pass


class ClusterProxiesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    # TODO
    pass

  def receive(self, proxies_stats_dict):
    # TODO
    pass
