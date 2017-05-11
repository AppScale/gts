import logging
import os
import time
from datetime import datetime

import attr
import psutil
from appscale.common import appscale_info

from appscale.hermes.stats.constants import LOCAL_STATS_DEBUG_INTERVAL
from appscale.hermes.stats.producers.converter import include_list_name, Meta
from appscale.hermes.stats.pubsub_base import StatsSource


@include_list_name('node.cpu')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeCPU(object):
  user = attr.ib()
  system = attr.ib()
  idle = attr.ib()
  percent = attr.ib()
  count = attr.ib()


@include_list_name('node.loadavg')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeLoadAvg(object):
  last_1min = attr.ib()
  last_5min = attr.ib()
  last_15min = attr.ib()


@include_list_name('node.memory')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeMemory(object):
  total = attr.ib()
  available = attr.ib()
  used = attr.ib()


@include_list_name('node.swap')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeSwap(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@include_list_name('node.disk_io')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()
  read_time = attr.ib()
  write_time = attr.ib()


@include_list_name('node.partition')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodePartition(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@include_list_name('node.network')
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


@include_list_name('node')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeStatsSnapshot(object):
  """
  Object of NodeStatsSnapshot is kind of structured container for all info related
  to resources used on the machine. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its machine statistics, but Master node also
  requests this statistics of all nodes in cluster.
  """
  utc_timestamp = attr.ib()
  private_ip = attr.ib()
  cpu = attr.ib(metadata={Meta.ENTITY: NodeCPU})
  memory = attr.ib(metadata={Meta.ENTITY: NodeMemory})
  swap = attr.ib(metadata={Meta.ENTITY: NodeSwap})
  disk_io = attr.ib(metadata={Meta.ENTITY: NodeDiskIO})
  partitions_dict = attr.ib(metadata={Meta.ENTITY_DICT: NodePartition})
  network = attr.ib(metadata={Meta.ENTITY: NodeNetwork})
  loadavg = attr.ib(metadata={Meta.ENTITY: NodeLoadAvg})


class NodeStatsSource(StatsSource):

  last_debug = 0

  def get_current(self):
    """ Method for building an instance of NodeStatsSnapshot.
    It collects information about usage of main resource on the machine.

    Returns:
      An object of NodeStatsSnapshot with detailed explanation of resources used
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

    stats = NodeStatsSnapshot(
      utc_timestamp=utc_timestamp, private_ip=private_ip, cpu=cpu,
      memory=memory, swap=swap, disk_io=disk_io,
      partitions_dict=partitions_dict, network=network, loadavg=loadavg
    )
    if time.time() - self.last_debug > LOCAL_STATS_DEBUG_INTERVAL:
      NodeStatsSource.last_debug = time.time()
      logging.debug(stats)
    return stats
