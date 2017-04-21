import os
import sys
import time
from datetime import datetime

import attr
import psutil

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeCPU(object):
  user = attr.ib()
  system = attr.ib()
  idle = attr.ib()
  percent = attr.ib()
  count = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeLoadAvg(object):
  last_1min = attr.ib()
  last_5min = attr.ib()
  last_15min = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeMemory(object):
  total = attr.ib()
  available = attr.ib()
  used = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeSwap(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()
  read_time = attr.ib()
  write_time = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodePartition(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeNetwork(object):
  bytes_sent = attr.ib()
  bytes_recv = attr.ib()
  packets_sent = attr.ib()
  packets_recv = attr.ib()
  errin = attr.ib()
  errout = attr.ib()
  dropin = attr.ib()
  dropout = attr.ib()
  connections_num = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeStats(object):
  """
  Object of NodeStats is kind of structured container for all info related 
  to resources used on the machine. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its machine statistics, but Master node also
  requests this statistics of all nodes in cluster.
  """
  utc_timestamp = attr.ib()
  private_ip = attr.ib()
  cpu = attr.ib()  # NodeCPU
  memory = attr.ib()  # NodeMemory
  swap = attr.ib()  # NodeSwap
  disk_io = attr.ib()  # NodeDiskIO
  partitions_dict = attr.ib()  # dict[str, NodePartition]
  network = attr.ib()  # NodeNetwork
  loadavg = attr.ib()  # NodeLoadAvg

  @staticmethod
  def current():
    """ Static method for building an instance of NodeStats.
    It collects information about usage of main resource on the machine.

    Returns:
      An object of NodeStats with detailed explanation of resources used
      on the machine
    """
    utc_timestamp = time.mktime(datetime.utcnow().timetuple())
    private_ip = appscale_info.get_private_ip()

    # CPU usage
    cpu_times = psutil.cpu_times()
    cpu = NodeCPU(
      user=cpu_times.user, system=cpu_times.system, idle=cpu_times.idle,
      percent=psutil.cpu_percent(), count=psutil.cpu_count()
    )

    # AvgLoad
    loadavg = NodeLoadAvg(*os.getloadavg())

    # Memory usage
    virtual = psutil.virtual_memory()
    memory = NodeMemory(
      total=virtual.total, available=virtual.available, used=virtual.used)

    # Swap usage
    swap_mem = psutil.swap_memory()
    swap = NodeSwap(
      total=swap_mem.total, free=swap_mem.free, used=swap_mem.used
    )

    # Disk usage
    partitions = psutil.disk_partitions()
    partitions_dict = {}
    for part in partitions:
      usage = psutil.disk_usage(part.mountpoint)
      partitions_dict[part.mountpoint] = NodePartition(
        total=usage.total, used=usage.used, free=usage.free
      )
    io_counters = psutil.disk_io_counters()
    disk_io = NodeDiskIO(
      read_count=io_counters.read_count, write_count=io_counters.write_count,
      read_bytes=io_counters.read_bytes, write_bytes=io_counters.write_bytes,
      read_time=io_counters.read_time, write_time=io_counters.write_time
    )

    # Network usage
    network_io = psutil.net_io_counters()
    network = NodeNetwork(
      bytes_sent=network_io.bytes_sent, bytes_recv=network_io.bytes_recv,
      packets_sent=network_io.packets_sent,
      packets_recv=network_io.packets_recv,
      errin=network_io.errin, errout=network_io.errout,
      dropin=network_io.dropin,
      dropout=network_io.dropout, connections_num=len(psutil.net_connections())
    )

    return NodeStats(
      utc_timestamp=utc_timestamp, private_ip=private_ip, cpu=cpu,
      memory=memory, swap=swap, disk_io=disk_io,
      partitions_dict=partitions_dict, network=network, loadavg=loadavg
    )

  @staticmethod
  def fromdict(dictionary):
    """ Addition to attr.asdict function.
    Args:
      dictionary: a dict containing all fields required to build NodeStats obj. 
    Returns:
      an instance of NodeStats
    """

