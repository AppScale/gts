from datetime import datetime
import logging

import argparse
import requests
import time
import threading

from appscale.hermes.stats import converter, models
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
  'proxy.frontend': ['bin', 'bout', 'scur', 'smax', 'rate',
                     'req_rate', 'req_tot', 'hrsp_4xx', 'hrsp_5xx'],
  'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
})

APPSCALE_PORT = 17441

requests.packages.urllib3.disable_warnings()


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
    self.models_dict = {
      'nodes': models.NodeStatsSnapshot,
      'processes': models.ProcessesStatsSnapshot,
      'proxies': models.ProxiesStatsSnapshot,
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
      },
      verify=False
    )
    response.raise_for_status()
    result_dict = response.json()
    raw_stats = result_dict['stats']
    failures = result_dict['failures']
    try:
      stats_model = self.models_dict[stats_type]
      stats = {
        ip: converter.stats_from_dict(stats_model, snapshot)
        for ip, snapshot in raw_stats.iteritems()
      }
    except TypeError as err:
      msg = u"Can't parse stats snapshot ({})".format(err)
      logging.error(msg)
      stats = {ip: msg for ip in raw_stats}
    return stats, failures

  def pull_periodically(self, stats_type, period):
    if self.running:
      logging.info('Pulling {stats_type} stats now and in {period} seconds'
                   .format(stats_type=stats_type, period=period))
      timer = threading.Timer(
        period, self.pull_periodically, args=[stats_type, period]
      )
      timer.start()
    else:
      logging.info('Pulling {stats_type} stats now and stopping'
                   .format(stats_type=stats_type, period=period))

    # Pull and process data
    try:
      start_time = time.time()
      stats, failures = self.fetch_stats(stats_type)
      logging.debug(
        'Fetched {stats_type} stats from {ok} nodes in {elapsed:.1f}'
        .format(stats_type=stats_type, ok=len(stats),
                elapsed=time.time()-start_time))

      # Report errors if there are any
      if failures:
        details = u'\n'.join(
          u'  {ip}: {msg}'.format(ip=ip, msg=msg)
          for ip, msg in failures.iteritems())
        logging.warning(
          u'Hermes master couldn\'t fetch {stats_type} stats from some nodes:'
          u'\n{details}'.format(stats_type=stats_type, details=details))
      # Write profile logs
      start_time = time.time()
      profiler = self.loggers_dict[stats_type]
      profiler.write(stats)
      logging.debug(
        'Saved latest {stats_type} stats snapshots in {elapsed:.1f}'
        .format(stats_type=stats_type, elapsed=time.time()-start_time))

    except requests.HTTPError as err:
      logging.error(u'Failed to get nodes stats ({err})'.format(err=err))
    except Exception as err:
      logging.exception(err)

  def start(self, nodes_stats_period, processes_stats_period,
            proxies_stats_period):
    self.running = True
    logging.info('Starting remote profiler...')
    if nodes_stats_period:
      self.pull_periodically('nodes', nodes_stats_period)
    if processes_stats_period:
      self.pull_periodically('processes', processes_stats_period)
    if proxies_stats_period:
      self.pull_periodically('proxies', proxies_stats_period)

  def stop(self):
    logging.info('Stopping remote profiler...')
    self.running = False


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--head-node-ip', required=True,
    help='IP address of head node')
  parser.add_argument(
    '--secret', required=True,
    help='Path to file containing deployment secret')
  parser.add_argument(
    '--output-dir', required=True,
    help='Path to directory where profile log should be saved')
  parser.add_argument(
    '--detailed-processes-stats', action='store_true',
    help='Write detailed processes stats')
  parser.add_argument(
    '--detailed-proxies-stats', action='store_true',
    help='Write detailed proxies stats')
  args = parser.parse_args()

  logging.basicConfig(
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s ',
    level=logging.INFO)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  try:
    with open(args.secret) as secret_file:
      secret = secret_file.read().strip()
  except (OSError, IOError) as err:
    logging.error(u'Couldn\'t read secret file ({err})'.format(err=err))
    exit(1)

  remote_profiler = RemoteProfiler(
    args.head_node_ip,
    secret,
    INCLUDE_LISTS,
    args.output_dir,
    args.detailed_processes_stats,
    args.detailed_proxies_stats
  )
  remote_profiler.start(
    nodes_stats_period=5,
    processes_stats_period=30,
    proxies_stats_period=10
  )
