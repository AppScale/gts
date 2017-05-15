import csv
import errno
from os import path, makedirs

import collections

import attr

from appscale.hermes.stats import converter
from appscale.hermes.stats.producers import node_stats, process_stats, \
  proxy_stats
from appscale.hermes.stats.pubsub_base import StatsSubscriber
from appscale.hermes.stats.constants import PROFILE_LOG_DIR
from appscale.hermes.stats.unified_service_names import KNOWN_SERVICES_DICT, \
  Service


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

  @attr.s(cmp=False, hash=False, slots=True)
  class ServiceSummary(object):
    cpu_time = attr.ib(default=0)
    resident_mem = attr.ib(default=0)
    unique_mem = attr.ib(default=0)

  def __init__(self, include_lists=None):
    self._header = ['utc_timestamp'] + converter.get_stats_header(
      process_stats.ProcessesStatsSnapshot, include_lists)
    self._include_lists = include_lists
    self._directory = path.join(PROFILE_LOG_DIR, 'processes')
    self._summary_file_name = path.join(self._directory, 'summary.csv')
    if not path.exists(self._directory):
      makedirs(self._directory)
    self._mentioned_services = self._get_previously_mentioned_services()

  def receive(self, processes_stats_dict):
    services_summary = collections.defaultdict(self.ServiceSummary)
    for node_ip, snapshots in processes_stats_dict.iteritems():
      for snapshot in snapshots:
        for proc in snapshot.processes_stats:
          # Fill add this process stats to service summary
          summary = services_summary[proc.unified_service_name]
          summary.cpu_time += proc.cpu.system + proc.cpu.user
          summary.resident_mem += proc.memory.resident
          summary.unique_mem += proc.memory.unique
          # Write stats of the specific process to its CSV file
          with self._prepare_file(node_ip, proc.monit_name) as csv_file:
            writer = csv.writer(csv_file)
            row = [snapshot.utc_timestamp] + converter.stats_to_list(
              proc, self._include_lists)
            writer.writerow(row)

  def _prepare_file(self, node_ip, monit_name):
    node_dir = path.join(self._directory, node_ip)
    file_name = path.join(node_dir, '{}.csv'.format(monit_name))
    if not path.exists(file_name):
      if not path.exists(node_dir):
        makedirs(node_dir)
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    return open(file_name, 'a')

  def _get_previously_mentioned_services(self):
    if not path.exists(self._summary_file_name):
      return collections.OrderedDict()
    with open(self._summary_file_name, 'r') as summary_file:
      reader = csv.reader(summary_file)
      header = reader.next()
      services_dict = collections.OrderedDict()
      for column_name in header:
        service_name = column_name.split(':', 1)[0]
        service = KNOWN_SERVICES_DICT.get(service_name)
        if not service:
          service = Service(service_name)
          services_dict[service_name] = service
      return services_dict

  def _save_summary(self, services_summary):
    previously_mentioned = self._get_previously_mentioned_services()
    if len(previously_mentioned) < len(self._mentioned_services):
      # Add headers for new services


class ClusterProxiesProfileLog(StatsSubscriber):

  def __init__(self, include_lists=None):
    self._header = converter.get_stats_header(
      proxy_stats.ProxiesStatsSnapshot, include_lists)
    self._include_lists = include_lists
    self._directory = path.join(PROFILE_LOG_DIR, 'proxies')

  def receive(self, proxies_stats_dict):
    for node_ip, snapshots in processes_stats_dict.iteritems():
      with self._prepare_file(node_ip) as csv_file:
        writer = csv.writer(csv_file)
        for snapshot in snapshots:
          row = converter.stats_to_list(snapshot, self._include_lists)
          writer.writerow(row)

  def _prepare_file(self, node_ip):
    file_name = path.join(self._directory, '{}.csv'.format(node_ip))
    if not path.exists(file_name):
      if not path.exists(self._directory):
        makedirs(self._directory)
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    return open(file_name, 'a')
