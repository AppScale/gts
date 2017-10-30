from datetime import datetime
import logging

import argparse
import requests
import time
import threading

from appscale.hermes.stats.converter import IncludeLists
from appscale.hermes.stats.profile import (
  NodesProfileLog, ProcessesProfileLog, ProxiesProfileLog
)

INCLUDE_LISTS = IncludeLists({
  # Node stats
  'node': ['utc_timestamp', 'cpu', 'memory',
           'partitions_dict', 'loadavg'],
  'node.cpu': ['percent', 'count'],
  'node.memory': ['available', 'total'],
  'node.partition': ['free', 'used'],
  'node.loadavg': ['last_5min'],
  # Processes stats
  'process': ['monit_name', 'unified_service_name', 'application_id',
              'port', 'cpu', 'memory', 'children_stats_sum'],
  'process.cpu': ['user', 'system', 'percent'],
  'process.memory': ['resident', 'virtual', 'unique'],
  'process.children_stats_sum': ['cpu', 'memory'],
  # Proxies stats
  'proxy': ['name', 'unified_service_name', 'application_id',
            'frontend', 'backend', 'servers_count'],
  'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
  'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
})

APPSCALE_PORT = 17441


class RemoteProfiler(object):
  def __init__(self, head_node_ip, secret, include_lists, output_dir,
               verbose_processes_log, verbose_proxies_log):
    self.head_node_ip = head_node_ip
    self.secret = secret
    self.nodes_log = NodesProfileLog(include_lists, output_dir)
    self.processes_log = ProcessesProfileLog(
      include_lists, output_dir, verbose_processes_log)
    self.proxies_log = ProxiesProfileLog(
      include_lists, output_dir, verbose_proxies_log)
    self.loggers_dict = {
      'nodes': self.nodes_log,
      'processes': self.processes_log,
      'proxies': self.proxies_log,
    }
    self.running = False

  def fetch_stats(self, stats_type):
    response = requests.get(
      'https://{ip}:{port}/stats/cluster/{stats_type}'.format(
        ip=self.head_node_ip, port=APPSCALE_PORT, stats_type=stats_type
      ),
      headers={
        'Appscale-Secret': self.secret
      },
      json={
        'include_lists': INCLUDE_LISTS.asdict(),
        'newer_than': time.mktime(datetime.now().timetuple()),
      }
    )
    response.raise_for_status()
    result_dict = response.json()
    stats = result_dict['stats']
    failures = result_dict['failures']
    return stats, failures

  def pull_periodically(self, stats_type, period):
    def periodical_job():
      if self.running:
        threading.Timer(period, periodical_job, period).start()

      # Pull and process data
      try:
        stats, failures = self.fetch_stats(stats_type)
        # Report errors if there are any
        if failures:
          details = u'\n'.join(
            u'  {ip}: {msg}'.format(ip=ip, msg=msg)
            for ip, msg in failures.iteritems()
          )
          logging.error(
            u'Hermes master couldn\'t fetch {stats_type} stats from some nodes:'
            u'\n{details}'.format(stats_type=stats_type, details=details)
          )
        # Write profile logs
        self.loggers_dict[stats_type].write(stats)

      except requests.HTTPError as err:
        logging.error(u'Failed to get nodes stats ({err})'.format(err=err))
      except Exception as err:
        logging.exception(err)

    periodical_job()

  def start(self, nodes_stats_period, processes_stats_period,
            proxies_stats_period):
    self.running = True
    if nodes_stats_period:
      self.pull_periodically('nodes', nodes_stats_period)
    if processes_stats_period:
      self.pull_periodically('processes', processes_stats_period)
    if proxies_stats_period:
      self.pull_periodically('proxies', proxies_stats_period)

  def stop(self):
    self.running = False


if __name__ == '__main__':

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  args = parser.parse_args()

  logging.basicConfig(
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s ',
    level=logging.INFO)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  # TODO
