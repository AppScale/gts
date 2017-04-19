import time
from datetime import datetime
import re

import attr
import psutil


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
  unified_service_name = attr.ib()
  unified_server_name = attr.ib()
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

  @staticmethod
  def current_processes():
    """ Static method for building a list of ProcessStats.
    It parses output of `monit status` and generates ProcessStats object
    for each monitored service

    Returns:
      A list of ProcessStats
    """
    # TODO parse monit status and get stats for each process

  @staticmethod
  def _process_stats(pid, service_name, server_name):
    """ Static method for building an instance of ProcessStats.
    It summarize stats of the specified process and its children.

    Args:
      pid: Process ID to describe
      service_name: unified name of a service it corresponds to
                    (e.g. app___guestbook27, taskqueue, cassandra, ..)
      server_name: unified name of a server it corresponds to
                    (e.g. app___appscaledashboard-<IP>-<PORT>,
                     taskqueue-<IP>-<PORT>, ...)
    Returns:
      An object of ProcessStats with detailed explanation of resources used by 
      the specified process and its children
    """
    # Get information about processes hierarchy (the process and its children)
    process = psutil.Process(pid)
    children_info = [child.oneshot() for child in process.children()]
    process_info = process.oneshot()

    utc_timestamp = time.mktime(datetime.utcnow().timetuple())

    # CPU usage
    raw_cpu = process_info.cpu_times()
    cpu = ProcessCPU(user=raw_cpu.user, system=raw_cpu.system)
    children_cpu = ProcessCPU(user=raw_cpu.children_user,
                              system=raw_cpu.children_system)

    # Memory usage
    raw_mem = process_info.memory_full_info()
    memory = ProcessMemory(resident=raw_mem.rss, virtual=raw_mem.vms,
                           unique=raw_mem.uss)
    children_raw_mem = [child.memory_full_info() for child in children_info]
    children_memory = ProcessMemory(
      resident=sum(m.rss for m in children_raw_mem),
      virtual=sum(m.vms for m in children_raw_mem),
      unique=sum(m.uss for m in children_raw_mem)
    )

    # Summarized values of DiskIO usage
    raw_disk = process_info.io_counters()
    disk_io = ProcessDiskIO(read_count=raw_disk.read_count,
                            write_count=raw_disk.write_count,
                            read_bytes=raw_disk.read_bytes,
                            write_bytes=raw_disk.write_bytes)
    children_raw_disk = [child.io_counters() for child in children_info]
    children_disk_io = ProcessDiskIO(
      read_count=sum(d.read_count for d in children_raw_disk),
      write_count=sum(d.write_count for d in children_raw_disk),
      read_bytes=sum(d.read_bytes for d in children_raw_disk),
      write_bytes=sum(d.write_bytes for d in children_raw_disk)
    )

    # Summarized values of Network usage
    network = ProcessNetwork(connections_num=len(process_info.connections()))
    children_network = ProcessNetwork(
      connections_num=sum(len(child.connections()) for child in children_info)
    )

    # Summarized values about Threading
    threads_num = len(process_info.thread())
    children_threads_num = sum(len(child.threads()) for child in children_info)

    children_sum = ProcessChildrenSum(
      cpu=children_cpu, memory=children_memory, disk_io=children_disk_io,
      network=children_network, threads_num=children_threads_num
    )

    return ProcessStats(
      pid=pid, unified_service_name=service_name,
      unified_server_name=server_name, cmdline=process_info.cmdline(),
      utc_timestamp=utc_timestamp, cpu=cpu, memory=memory, disk_io=disk_io,
      network=network, threads_num=threads_num, children_stats_sum=children_sum,
      children_num=len(children_info)
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
