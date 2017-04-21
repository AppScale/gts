import os
import re
import sys
import time
from datetime import datetime

import attr
import logging
import psutil
import subprocess

from unified_service_names import find_service_by_monit_name

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessCPU(object):
  user = attr.ib()
  system = attr.ib()
  percent = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessMemory(object):
  resident = attr.ib()
  virtual = attr.ib()
  unique = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessNetwork(object):
  connections_num = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessChildrenSum(object):
  cpu = attr.ib()  # ProcessCPU
  memory = attr.ib()  # ProcessMemory
  disk_io = attr.ib()  # ProcessDiskIO
  network = attr.ib()  # ProcessNetwork
  threads_num = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessStats(object):
  """
  Object of ProcessStats is kind of structured container for all info related 
  to resources used by specific process. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its processes statistics, but Master node also
  requests this statistics of all nodes in cluster.
  All processes started by monit should be profiled.
  """
  pid = attr.ib()
  monit_name = attr.ib()

  unified_service_name = attr.ib()  #| These 3 fields are primary key
  application_id = attr.ib()        #| for an instance of appscale service
  private_ip = attr.ib()            #| - Application ID can be None if
  port = attr.ib()                  #|   process is not related to specific app
                                    #| - port can be missed if it is not
                                    #|   mentioned in monit process name
  cmdline = attr.ib()
  utc_timestamp = attr.ib()
  cpu = attr.ib()  # ProcessCPU
  memory = attr.ib()  # ProcessMemory
  disk_io = attr.ib()  # ProcessDiskIO
  network = attr.ib()  # ProcessNetwork
  threads_num = attr.ib()
  children_stats_sum = attr.ib()  # ProcessChildrenSum
  children_num = attr.ib()

  MONIT_PROCESS_PATTERN = re.compile(
    r"^Process \'(?P<name>[^']+)\' *\n"
    r"(^  .*\n)*?"
    r"^  pid +(?P<pid>\d+)\n",
    re.MULTILINE
  )
  PROCESS_ATTRS = (
    'cpu_times', 'cpu_percent', 'memory_full_info', 'io_counters',
    'connections', 'threads', 'cmdline'
  )

  @staticmethod
  def current_processes():
    """ Static method for building a list of ProcessStats.
    It parses output of `monit status` and generates ProcessStats object
    for each monitored service

    Returns:
      A list of ProcessStats
    """
    monit_status = subprocess.check_output('monit status')
    processes_stats = []
    for match in ProcessStats.MONIT_PROCESS_PATTERN.finditer(monit_status):
      monit_name = match.group('name')
      pid = int(match.group('pid'))
      service = find_service_by_monit_name(monit_name)
      private_ip = appscale_info.get_private_ip()
      try:
        stats = ProcessStats._process_stats(pid, service, monit_name, private_ip)
        processes_stats.append(stats)
      except psutil.Error as err:
        logging.warn("Unable to get process stats for {monit_name} ({err})"
                     .format(monit_name=monit_name, err=err))
    return processes_stats

  @staticmethod
  def _process_stats(pid, service, monit_name, private_ip):
    """ Static method for building an instance of ProcessStats.
    It summarize stats of the specified process and its children.

    Args:
      pid: Process ID to describe
      service: an instance of unified_service_names.Service which crresponds to
               this process
      monit_name: name of corresponding monit process
    Returns:
      An object of ProcessStats with detailed explanation of resources used by 
      the specified process and its children
    """
    # Get information about processes hierarchy (the process and its children)
    process = psutil.Process(pid)
    children_info = [child.as_dict(ProcessStats.PROCESS_ATTRS)
                     for child in process.children()]
    process_info = process.as_dict(ProcessStats.PROCESS_ATTRS)

    utc_timestamp = time.mktime(datetime.utcnow().timetuple())

    # CPU usage
    raw_cpu = process_info['cpu_times']
    cpu = ProcessCPU(user=raw_cpu.user, system=raw_cpu.system,
                     percent=process_info['cpu_percent'])
    children_cpu = ProcessCPU(user=raw_cpu.children_user,
                              system=raw_cpu.children_system,
                              percent=sum(child['cpu_percent']
                                          for child in children_info))

    # Memory usage
    raw_mem = process_info['memory_full_info']
    memory = ProcessMemory(resident=raw_mem.rss, virtual=raw_mem.vms,
                           unique=raw_mem.uss)
    children_raw_mem = [child['memory_full_info'] for child in children_info]
    children_memory = ProcessMemory(
      resident=sum(m.rss for m in children_raw_mem),
      virtual=sum(m.vms for m in children_raw_mem),
      unique=sum(m.uss for m in children_raw_mem)
    )

    # Summarized values of DiskIO usage
    raw_disk = process_info['io_counters']
    disk_io = ProcessDiskIO(read_count=raw_disk.read_count,
                            write_count=raw_disk.write_count,
                            read_bytes=raw_disk.read_bytes,
                            write_bytes=raw_disk.write_bytes)
    children_raw_disk = [child['io_counters'] for child in children_info]
    children_disk_io = ProcessDiskIO(
      read_count=sum(d.read_count for d in children_raw_disk),
      write_count=sum(d.write_count for d in children_raw_disk),
      read_bytes=sum(d.read_bytes for d in children_raw_disk),
      write_bytes=sum(d.write_bytes for d in children_raw_disk)
    )

    # Summarized values of Network usage
    network = ProcessNetwork(connections_num=len(process_info['connections']))
    children_network = ProcessNetwork(
      connections_num=sum(len(child['connections']) for child in children_info)
    )

    # Summarized values about Threading
    threads_num = len(process_info['threads'])
    children_threads_num = sum(len(child['threads']) for child in children_info)

    children_sum = ProcessChildrenSum(
      cpu=children_cpu, memory=children_memory, disk_io=children_disk_io,
      network=children_network, threads_num=children_threads_num
    )

    return ProcessStats(
      pid=pid, monit_name=monit_name, unified_service_name=service.name,
      application_id=service.get_application_id_by_monit_name(monit_name),
      port=service.get_port_by_monit_name(monit_name), private_ip=private_ip,
      cmdline=process_info['cmdline'], utc_timestamp=utc_timestamp, cpu=cpu,
      memory=memory, disk_io=disk_io, network=network, threads_num=threads_num,
      children_stats_sum=children_sum, children_num=len(children_info)
    )

  @staticmethod
  def fromdict(dictionary):
    """ Addition to attr.asdict function.
    Args:
      dictionary: a dict with all fields required to build ProcessStats obj. 
    Returns:
      an instance of ProcessStats
    """
    pass
