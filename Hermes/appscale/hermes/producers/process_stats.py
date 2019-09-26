import logging
import re
import subprocess
import time
from datetime import datetime

import attr
import psutil
from appscale.admin.service_manager import ServiceManager
from appscale.common import appscale_info

from appscale.hermes.converter import Meta, include_list_name
from appscale.hermes.unified_service_names import (
    find_service_by_external_name, systemd_mapper)

logger = logging.getLogger(__name__)


@include_list_name('process.cpu')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessCPU(object):
  user = attr.ib()
  system = attr.ib()
  percent = attr.ib()


@include_list_name('process.memory')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessMemory(object):
  resident = attr.ib()
  virtual = attr.ib()
  unique = attr.ib()


@include_list_name('process.disk_io')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()


@include_list_name('process.network')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessNetwork(object):
  connections_num = attr.ib()


@include_list_name('process.children_stats_sum')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessChildrenSum(object):
  cpu = attr.ib(metadata={Meta.ENTITY: ProcessCPU})
  memory = attr.ib(metadata={Meta.ENTITY: ProcessMemory})
  disk_io = attr.ib(metadata={Meta.ENTITY: ProcessDiskIO})
  network = attr.ib(metadata={Meta.ENTITY: ProcessNetwork})
  threads_num = attr.ib()


@include_list_name('process')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessStats(object):
  """
  Object of ProcessStats is kind of structured container for all info related
  to resources used by specific process. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its processes statistics, but Master node also
  requests this statistics of all nodes in cluster.
  AppScale services started by systemd should be profiled.
  """
  pid = attr.ib()
  monit_name = attr.ib()  # Monit / external name

  unified_service_name = attr.ib()  #| These 4 fields are primary key
  application_id = attr.ib()        #| for an instance of appscale service
  private_ip = attr.ib()            #| - Application ID can be None if
  port = attr.ib()                  #|   process is not related to specific app
                                    #| - port can be missed if it is not
                                    #|   mentioned in the external name
  cmdline = attr.ib()
  cpu = attr.ib(metadata={Meta.ENTITY: ProcessCPU})
  memory = attr.ib(metadata={Meta.ENTITY: ProcessMemory})
  disk_io = attr.ib(metadata={Meta.ENTITY: ProcessDiskIO})
  network = attr.ib(metadata={Meta.ENTITY: ProcessNetwork})
  threads_num = attr.ib()
  children_stats_sum = attr.ib(metadata={Meta.ENTITY: ProcessChildrenSum})
  children_num = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  processes_stats = attr.ib(metadata={Meta.ENTITY_LIST: ProcessStats})


SYSTEMCTL_SHOW = (
    'systemctl', '--type=service', '--state=active', '--property=Id,MainPID',
    'show', '*.service'
)
SYSTEMCTL_SHOW_PATTERN = re.compile(
  r"^MainPID=(?P<pid>\d+)\n"
  r"^Id=(?P<name>[a-zA-Z0-9@_-]+\.service)\n",
  re.MULTILINE
)
PROCESS_ATTRS = (
  'cpu_times', 'cpu_percent', 'memory_full_info', 'io_counters',
  'connections', 'threads', 'cmdline'
)


class ProcessesStatsSource(object):

  @staticmethod
  def get_current():
    """ Method for building a list of ProcessStats.
    It parses output of `systemctl show` and generates ProcessStats object
    for each service of interest.

    Returns:
      An instance ofProcessesStatsSnapshot.
    """
    start = time.time()
    systemctl_show = subprocess.check_output(SYSTEMCTL_SHOW).decode()
    processes_stats = []
    private_ip = appscale_info.get_private_ip()
    for match in SYSTEMCTL_SHOW_PATTERN.finditer(systemctl_show):
      systemd_name = match.group('name')
      pid = int(match.group('pid'))
      service = find_service_by_external_name(systemd_name,
                                              default_mapper=systemd_mapper)
      if service is None:
        continue
      try:
        stats = _process_stats(pid, service, systemd_name, private_ip)
        processes_stats.append(stats)
      except psutil.Error as err:
        logger.warning("Unable to get process stats for {name} ({err})"
                       .format(name=service.name, err=err))

    # Add processes managed by the ServiceManager.
    for server in ServiceManager.get_state():
      service = find_service_by_external_name(server.monit_name)
      try:
        stats = _process_stats(server.process.pid, service, server.monit_name,
                               private_ip)
        processes_stats.append(stats)
      except psutil.Error as error:
        logger.warning('Unable to get process stats for '
                       '{} ({})'.format(server, error))

    stats = ProcessesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.now().timetuple()),
      processes_stats=processes_stats
    )
    logger.info("Prepared stats about {proc} processes in {elapsed:.1f}s."
                .format(proc=len(processes_stats), elapsed=time.time()-start))
    return stats


def _process_stats(pid, service, ext_name, private_ip):
  """ Static method for building an instance of ProcessStats.
  It summarize stats of the specified process and its children.

  Args:
    pid: A string representing Process ID to describe.
    service: An instance of unified_service_names.Service which corresponds to
      this process.
    ext_name: A string, name of corresponding external service/process.
  Returns:
    An object of ProcessStats with detailed explanation of resources used by
    the specified process and its children.
  """
  # Get information about processes hierarchy (the process and its children)
  process = psutil.Process(pid)
  children_info = [child.as_dict(PROCESS_ATTRS)
                   for child in process.children()]
  process_info = process.as_dict(PROCESS_ATTRS)

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
    pid=pid, monit_name=ext_name, unified_service_name=service.name,
    application_id=service.get_application_id_by_external_name(ext_name),
    port=service.get_port_by_external_name(ext_name), private_ip=private_ip,
    cmdline=process_info['cmdline'], cpu=cpu, memory=memory, disk_io=disk_io,
    network=network, threads_num=threads_num, children_stats_sum=children_sum,
    children_num=len(children_info)
  )
