""" This module is responsible for writing cluster statistics to CSV files. """
import collections
import csv
import time
from datetime import datetime
from os import path, rename

import attr

from appscale.hermes import helper
from appscale.hermes.stats import converter
from appscale.hermes.stats.constants import PROFILE_LOG_DIR
from appscale.hermes.stats.producers import node_stats, process_stats, \
  proxy_stats


class NodesProfileLog(object):

  def __init__(self, include_lists=None):
    """ Initializes profile log for cluster node stats.
    Renders header according to include_lists in advance and
    creates base directory for node stats profile log.

    Args:
      include_lists: An instance of IncludeLists describing which fields
        of node stats should be written to CSV log.
    """
    self._include_lists = include_lists
    self._header = (
      converter.get_stats_header(node_stats.NodeStatsSnapshot,
                                 self._include_lists)
    )
    helper.ensure_directory(PROFILE_LOG_DIR)

  def write(self, nodes_stats_dict):
    """ Saves newly produced cluster node stats
    to a list of CSV files (file per node).

    Args:
      nodes_stats_dict: A dict with node IP as key and list of
        NodeStatsSnapshot as value.
    """
    for node_ip, snapshot in nodes_stats_dict.iteritems():
      with self._prepare_file(node_ip) as csv_file:
        row = converter.stats_to_list(snapshot, self._include_lists)
        csv.writer(csv_file).writerow(row)

  def _prepare_file(self, node_ip):
    """ Prepares CSV file with name node/<node-IP>.csv
    for appending new lines.

    Args:
      node_ip: A string representation of node IP.
    Returns:
      A file object opened for appending new data.
    """
    node_dir = path.join(PROFILE_LOG_DIR, node_ip)
    file_name = path.join(node_dir, 'node.csv')
    if not path.isfile(file_name):
      helper.ensure_directory(node_dir)
      # Create file and write header
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    # Open table for appending data
    return open(file_name, 'a')


class ProcessesProfileLog(object):

  @attr.s(cmp=False, hash=False, slots=True)
  class ServiceProcessesSummary(object):
    """
    This data structure is a service summary accumulator.
    When new stats are received, ServiceProcessesSummary is created
    for each service and then cpu time and memory usage of each process
    running this service is added to the summary.
    Separate CSV summary file is created for each attribute of this model,
    so we can compare services regarding usage of the specific resource.
    """
    cpu_time = attr.ib(default=0)
    resident_mem = attr.ib(default=0)
    unique_mem = attr.ib(default=0)
    children_resident_mem = attr.ib(default=0)
    children_unique_mem = attr.ib(default=0)

  def __init__(self, include_lists=None, write_detailed_stats=False):
    """ Initializes profile log for cluster processes stats.
    Renders header according to include_lists in advance and
    creates base directory for processes stats profile log.
    It also reads header of summary file (if it exists) to identify
    order of columns.

    Args:
      include_lists: An instance of IncludeLists describing which fields
        of processes stats should be written to CSV log.
      write_detailed_stats: A boolean determines if detailed stats about
        each process should be written.
    """
    self._include_lists = include_lists
    self._header = (
      ['utc_timestamp']
      + converter.get_stats_header(process_stats.ProcessStats,
                                   self._include_lists)
    )
    self._write_detailed_stats = write_detailed_stats
    helper.ensure_directory(PROFILE_LOG_DIR)
    self._summary_file_name_template = 'summary-{resource}.csv'
    self._summary_columns = self._get_summary_columns()

  def write(self, processes_stats_dict):
    """ Saves newly produced cluster processes stats to a list of CSV files.
    One detailed file for each process on every node and 3 summary files.

    Args:
      processes_stats_dict: A dict with node IP as key and list of
        ProcessesStatsSnapshot as value.
    """
    services_summary = collections.defaultdict(self.ServiceProcessesSummary)

    for node_ip, snapshot in processes_stats_dict.iteritems():

      # Add info to the summary
      for proc in snapshot.processes_stats:
        # Add this process stats to service summary
        service_name = proc.unified_service_name
        if proc.application_id:
          service_name = '{}-{}'.format(service_name, proc.application_id)
        summary = services_summary[service_name]
        summary.cpu_time += (
          proc.cpu.system + proc.cpu.user
          + proc.children_stats_sum.cpu.system
          + proc.children_stats_sum.cpu.user
        )
        summary.resident_mem += proc.memory.resident
        summary.unique_mem += proc.memory.unique
        summary.children_resident_mem += proc.children_stats_sum.memory.resident
        summary.children_unique_mem += proc.children_stats_sum.memory.unique

      if not self._write_detailed_stats:
        continue

      # Write detailed process stats
      for proc in snapshot.processes_stats:
        # Write stats of the specific process to its CSV file
        with self._prepare_file(node_ip, proc.monit_name) as csv_file:
          row = (
            [snapshot.utc_timestamp]
             + converter.stats_to_list(proc, self._include_lists)
          )
          csv.writer(csv_file).writerow(row)

    # Update self._summary_columns ordered dict (set)
    for service_name in services_summary:
      if service_name not in self._summary_columns:
        self._summary_columns.append(service_name)

    # Write summary
    self._save_summary(services_summary)

  def _prepare_file(self, node_ip, monit_name):
    """ Prepares CSV file with name processes/<node-IP>/<monit-name>.csv
    for appending new lines.

    Args:
      node_ip: A string representation of node IP.
      monit_name: A string name of process as it's shown in monit status.
    Returns:
      A file object opened for appending new data.
    """
    processes_dir = path.join(PROFILE_LOG_DIR, node_ip, 'processes')
    file_name = path.join(processes_dir, '{}.csv'.format(monit_name))
    if not path.isfile(file_name):
      helper.ensure_directory(processes_dir)
      # Create file and write header
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    # Open file for appending new data
    return open(file_name, 'a')

  def _get_summary_columns(self):
    """ Opens summary-cpu-time.csv file (other summary file would be fine)
    and reads its header. Profiler needs to know order of columns previously
    written to the summary.

    Returns:
      A list of column names: ['utc_timestamp', <service1>, <service2>, ..].
    """
    cpu_summary_file_name = self._get_summary_file_name('cpu_time')
    if not path.isfile(cpu_summary_file_name):
      return ['utc_timestamp']
    with open(cpu_summary_file_name, 'r') as summary_file:
      reader = csv.reader(summary_file)
      return reader.next()  # First line is a header

  def _save_summary(self, services_summary):
    """ Saves services summary for each resource (cpu, resident memory and
    unique memory). Output is 3 files (one for each resource) which
    have a column for each service + utc_timestamp column.

    Args:
      services_summary: A dict where key is name of service and value is
        an instance of ServiceProcessesSummary.
    """
    old_summary_columns = self._get_summary_columns()

    for attribute in attr.fields(self.ServiceProcessesSummary):
      # For each kind of resource (cpu, resident_mem, unique_mem)

      summary_file_name = self._get_summary_file_name(attribute.name)

      if len(old_summary_columns) == 1:
        # Summary wasn't written yet - write header line to summary file
        with open(summary_file_name, 'w') as new_summary:
          csv.writer(new_summary).writerow(self._summary_columns)

      if len(old_summary_columns) < len(self._summary_columns):
        # Header need to be updated - add new services columns
        with open(summary_file_name, 'r') as old_summary:
          old_summary.readline()  # Skip header
          new_summary_file_name = '{}.new'.format(summary_file_name)
          with open(new_summary_file_name, 'w') as new_summary:
            # Write new header
            csv.writer(new_summary).writerow(self._summary_columns)
            # Recover old data
            new_summary.writelines(old_summary)
        rename(new_summary_file_name, summary_file_name)

      with open(summary_file_name, 'a') as summary_file:
        # Append line with the newest summary
        row = [time.mktime(datetime.utcnow().timetuple())]
        columns_iterator = self._summary_columns.__iter__()
        columns_iterator.next()  # Skip timestamp column
        for service_name in columns_iterator:
          service_summary = services_summary.get(service_name)
          if service_summary:
            row.append(getattr(service_summary, attribute.name))
          else:
            row.append('')
        csv.writer(summary_file).writerow(row)

  def _get_summary_file_name(self, resource_name):
    name = self._summary_file_name_template.format(resource=resource_name)
    name = name.replace('_', '-')
    return path.join(PROFILE_LOG_DIR, name)


class ProxiesProfileLog(object):

  @attr.s(cmp=False, hash=False, slots=True)
  class ServiceProxySummary(object):
    """
    This data structure holds a list of useful proxy stats attributes.
    Separate CSV summary file is created for each attribute of this model,
    so we can easily compare services regarding important properties.
    """
    requests_rate = attr.ib(default=0)
    bytes_in_out = attr.ib(default=0)
    errors = attr.ib(default=0)

  def __init__(self, include_lists=None, write_detailed_stats=False):
    """ Initializes profile log for cluster processes stats.
    Renders header according to include_lists in advance and
    creates base directory for processes stats profile log.
    It also reads header of summary file (if it exists) to identify
    order of columns.

    Args:
      include_lists: An instance of IncludeLists describing which fields
        of processes stats should be written to CSV log.
      write_detailed_stats: A boolean determines if detailed stats about
        each proxy should be written.
    """
    self._include_lists = include_lists
    self._header = (
      ['utc_timestamp']
       + converter.get_stats_header(proxy_stats.ProxyStats, self._include_lists)
    )
    self._write_detailed_stats = write_detailed_stats
    helper.ensure_directory(PROFILE_LOG_DIR)
    self._summary_file_name_template = 'summary-{property}.csv'
    self._summary_columns = self._get_summary_columns()

  def write(self, proxies_stats_dict):
    """ Saves newly produced cluster proxies stats to a list of CSV files.
    One detailed file for each proxy on every load balancer node
    (if detailed stats is enabled) and three additional files
    which summarize info about all cluster proxies.

    Args:
      proxies_stats_dict: A dict with node IP as key and list of
        ProxyStatsSnapshot as value.
    """
    services_summary = collections.defaultdict(self.ServiceProxySummary)

    for node_ip, snapshot in proxies_stats_dict.iteritems():

      # Add info to the summary
      for proxy in snapshot.proxies_stats:
        # Add this proxy stats to service summary
        service_name = proxy.unified_service_name
        if proxy.application_id:
          service_name = '{}-{}'.format(service_name, proxy.application_id)
        summary = services_summary[service_name]
        summary.requests_rate += proxy.frontend.req_rate
        summary.bytes_in_out += proxy.frontend.bin + proxy.frontend.bout
        summary.errors += proxy.frontend.hrsp_4xx + proxy.frontend.hrsp_5xx

      if not self._write_detailed_stats:
        continue

      # Write detailed proxy stats
      for proxy in snapshot.proxies_stats:
        # Write stats of the specific proxy to its CSV file
        with self._prepare_file(node_ip, proxy.name) as csv_file:
          row = (
            [snapshot.utc_timestamp]
            + converter.stats_to_list(proxy, self._include_lists)
          )
          csv.writer(csv_file).writerow(row)

    # Update self._summary_columns list
    for service_name in services_summary:
      if service_name not in self._summary_columns:
        self._summary_columns.append(service_name)

    # Write summary
    self._save_summary(services_summary)

  def _prepare_file(self, node_ip, pxname):
    """ Prepares CSV file with name <node-IP>/<pxname>.csv
    for appending new lines.

    Args:
      node_ip: A string representation of load balancer node IP.
      pxname: A string name of proxy as it's shown haproxy stats.
    Returns:
      A file object opened for appending new data.
    """
    proxies_dir = path.join(PROFILE_LOG_DIR, node_ip, 'proxies')
    file_name = path.join(proxies_dir, '{}.csv'.format(pxname))
    if not path.isfile(file_name):
      helper.ensure_directory(proxies_dir)
      # Create file and write header
      with open(file_name, 'w') as csv_file:
        csv.writer(csv_file).writerow(self._header)
    # Open file for appending new data
    return open(file_name, 'a')

  def _get_summary_columns(self):
    """ Opens summary file and reads its header.
    Profiler needs to know order of columns previously written to the summary.

    Returns:
      A list of column names: ['utc_timestamp', <service1>, <service2>, ..].
    """
    reqs_summary_file_name = self._get_summary_file_name('requests_rate')
    if not path.isfile(reqs_summary_file_name):
      return ['utc_timestamp']
    with open(reqs_summary_file_name, 'r') as summary_file:
      reader = csv.reader(summary_file)
      return reader.next()  # First line is a header

  def _save_summary(self, services_summary):
    """ Saves services summary for each property (requests rate, errors and
    sum of bytes in & out). Output is 3 files (one for each property) which
    have a column for each service + utc_timestamp column.

    Args:
      services_summary: A dict where key is name of service and value is
        an instance of ServiceProxySummary.
    """
    old_summary_columns = self._get_summary_columns()

    for attribute in attr.fields(self.ServiceProxySummary):
      # For each property (requests_rate, errors, bytes_in_out)

      summary_file_name = self._get_summary_file_name(attribute.name)

      if len(old_summary_columns) == 1:
        # Summary wasn't written yet - write header line to summary file
        with open(summary_file_name, 'w') as new_summary:
          csv.writer(new_summary).writerow(self._summary_columns)

      if len(old_summary_columns) < len(self._summary_columns):
        # Header need to be updated - add new services columns
        with open(summary_file_name, 'r') as old_summary:
          old_summary.readline()  # Skip header
          new_summary_file_name = '{}.new'.format(summary_file_name)
          with open(new_summary_file_name, 'w') as new_summary:
            # Write new header
            csv.writer(new_summary).writerow(self._summary_columns)
            # Recover old data
            new_summary.writelines(old_summary)
        rename(new_summary_file_name, summary_file_name)

      with open(summary_file_name, 'a') as summary_file:
        # Append line with the newest summary
        row = [time.mktime(datetime.utcnow().timetuple())]
        columns_iterator = self._summary_columns.__iter__()
        columns_iterator.next()  # Skip timestamp column
        for service_name in columns_iterator:
          service_summary = services_summary.get(service_name)
          if service_summary:
            row.append(getattr(service_summary, attribute.name))
          else:
            row.append('')
        csv.writer(summary_file).writerow(row)

  def _get_summary_file_name(self, property_name):
    name = self._summary_file_name_template.format(property=property_name)
    name = name.replace('_', '-')
    return path.join(PROFILE_LOG_DIR, name)
