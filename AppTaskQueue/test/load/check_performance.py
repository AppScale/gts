import argparse
import csv
import logging
import os
import sys

import attr
from tabulate import tabulate


@attr.s(cmp=False, hash=False, slots=True)
class MethodStats(object):
  """
  Represents performance statistics for a particular
  TaskQueue API method (according to locust log).
  """
  succeeded = attr.ib(default=None)
  min_response_time = attr.ib(default=None)
  avg_response_time = attr.ib(default=None)
  max_response_time = attr.ib(default=None)
  max_for_best_50_pct = attr.ib(default=None)
  max_for_best_66_pct = attr.ib(default=None)
  max_for_best_75_pct = attr.ib(default=None)
  max_for_best_80_pct = attr.ib(default=None)
  max_for_best_90_pct = attr.ib(default=None)
  max_for_best_95_pct = attr.ib(default=None)
  max_for_best_98_pct = attr.ib(default=None)
  max_for_best_99_pct = attr.ib(default=None)
  avg_content_size = attr.ib(default=None)
  req_s = attr.ib(default=None)
  failed = attr.ib(default=None)    # It seems that locust doesn't count
                                    # failed requests in min/avg/max/.. stats

  @property
  def total(self):
    return self.succeeded + self.failed

  @property
  def failed_pct(self):
    return self.failed / self.total * 100


@attr.s(cmp=False, hash=False, slots=True)
class SummaryStats(object):
  """
  Represents summarized performance statistics for a TaskQueue.
  """
  succeeded = attr.ib()
  min_response_time = attr.ib()
  avg_response_time = attr.ib()
  max_response_time = attr.ib()
  req_s = attr.ib()
  failed = attr.ib()

  @property
  def total(self):
    return self.succeeded + self.failed

  @property
  def failed_pct(self):
    return self.failed / self.total * 100


class IncorrectLogs(ValueError):
  pass


class LocustLogChecker(object):
  """
  Class performing parsing of Locust performance log.
  """

  def __init__(self, locust_log_dir):
    self.methods = {}
    self.requests_files = []
    self.distribution_files = []
    self.find_relevant_logs(locust_log_dir)
    try:
      self.parse_requests_csvs()
      self.parse_distribution_csvs()
      self.summary_stats = self.compute_summary()
    except ValueError as err:
      # Sometimes locust failes to report stats properly (reason is unknown yet)
      msg = 'Locust logs seems to be incorrect'
      logging.error(msg)
      raise IncorrectLogs(msg) from err

  def find_relevant_logs(self, logs_dir):
    """ Walks though all files in logs_dir
    and picks locust csv files.
    """
    for root, dirs, files in os.walk(logs_dir):
      for filename in files:
        if filename.endswith('_requests.csv'):
          self.requests_files.append(os.path.join(root, filename))
        if filename.endswith('_distribution.csv'):
          self.distribution_files.append(os.path.join(root, filename))

  def parse_requests_csvs(self):
    """ Parses *_requests.csv filed. Fills MethodStats instances.
    """
    for requests_file in self.requests_files:
      with open(requests_file, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in reader:
          if row[0] == "Method" or row[0] == "None":
            continue    # Skip header and total line
          method_name = f'{row[0]} {row[1]}'
          if method_name not in self.methods:
            self.methods[method_name] = MethodStats()
          method_stats = self.methods[method_name]
          method_stats.succeeded = int(row[2])
          method_stats.failed = int(row[3])
          method_stats.avg_response_time = int(row[5])
          method_stats.min_response_time = int(row[6])
          method_stats.max_response_time = int(row[7])
          method_stats.avg_content_size = int(row[8])
          method_stats.req_s = float(row[9])

  def parse_distribution_csvs(self):
    """ Parses *_distribution.csv filed. Fills MethodStats instances.
    """
    for distribution_file in self.distribution_files:
      with open(distribution_file, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in reader:
          if row[0] == "Name" or row[0] == "Total":
            continue    # Skip header and total line
          method_name = row[0]
          if method_name not in self.methods:
            self.methods[method_name] = MethodStats()
          method_stats = self.methods[method_name]
          method_stats.max_for_best_50_pct = int(row[2])
          method_stats.max_for_best_66_pct = int(row[3])
          method_stats.max_for_best_75_pct = int(row[4])
          method_stats.max_for_best_80_pct = int(row[5])
          method_stats.max_for_best_90_pct = int(row[6])
          method_stats.max_for_best_95_pct = int(row[7])
          method_stats.max_for_best_98_pct = int(row[8])
          method_stats.max_for_best_99_pct = int(row[9])

  def compute_summary(self):
    """ Computes summary stats.

    Returns:
      an instance of SummaryStats.
    """
    total_succeeded = sum(method.succeeded for method in self.methods.values())
    return SummaryStats(
      succeeded=total_succeeded,
      min_response_time=min(
        method.min_response_time for method in self.methods.values()
      ),
      avg_response_time=int(sum(
        method.avg_response_time * method.succeeded / total_succeeded
        for method in self.methods.values()
      )),
      max_response_time=max(
        method.max_response_time for method in self.methods.values()
      ),
      req_s=sum(method.req_s for method in self.methods.values()),
      failed=sum(method.failed for method in self.methods.values())
    )

  def check_performance_and_exit(self):
    # TODO, compare it to some baseline
    sys.exit(0)


def render_stats(methods_dict, summary):
  """ Renders multi-line string containing tables
  with all performance statistics.

  Returns:
    Nicely formatted string representing performance stats.
  """
  sorted_methods = sorted(methods_dict.items(), key=lambda item: item[0])
  requests_header = [
    'API Method', 'Requests', 'Failed (%)', 'Min rtime', 'Avg rtime',
    'Max rtime', 'Avg content size', 'Req/s'
  ]
  requests_lines = []
  for method_name, stats in sorted_methods:
    requests_lines.append((
      method_name,
      stats.total,
      f'{stats.failed} ({stats.failed_pct:.2f})',
      stats.min_response_time,
      stats.avg_response_time,
      stats.max_response_time,
      stats.avg_content_size,
      stats.req_s
    ))
  requests_table = tabulate(
    tabular_data=requests_lines, headers=requests_header,
    tablefmt='simple', floatfmt=".1f", numalign="right", stralign="left"
  )

  distribution_header = [
    'API Method', 'Max rtime 100%',
    '99%', '98%', '95%', '90%', '80%', '75%', '66%', '50%'
  ]
  distribution_lines = []
  for method_name, stats in sorted_methods:
    distribution_lines.append((
      method_name,
      stats.max_response_time,
      stats.max_for_best_99_pct,
      stats.max_for_best_98_pct,
      stats.max_for_best_95_pct,
      stats.max_for_best_90_pct,
      stats.max_for_best_80_pct,
      stats.max_for_best_75_pct,
      stats.max_for_best_66_pct,
      stats.max_for_best_50_pct
    ))
  distribution_table = tabulate(
    tabular_data=distribution_lines, headers=distribution_header,
    tablefmt='simple', floatfmt=".1f", numalign="right", stralign="left"
  )

  return (
    f'Main requests statistics:\n'
    f'{requests_table}\n'
    f'\n'
    f'Response time distribution table:\n'
    f'{distribution_table}\n'
    f'\n'
    f'Total summary:\n'
    f'{summary.total:>9}   total requests\n'
    f'{summary.failed:>9}   failed requests {summary.failed_pct:.2f}\n'
    f'{summary.min_response_time:>9}   min response time\n'
    f'{summary.avg_response_time:>9}   avg response time\n'
    f'{summary.max_response_time:>9}   max response time\n'
    f'{summary.req_s:>11.1f} requests/s\n'
    f''
  )


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--locust-log", help="Directory containing locust log.")
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

  checker = LocustLogChecker(args.locust_log)
  logging.info(f'LOCUST STATS:\n'
               f'{render_stats(checker.methods, checker.summary_stats)}')
  checker.check_performance_and_exit()
