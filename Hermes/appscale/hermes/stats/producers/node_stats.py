import logging
import os
import time
from datetime import datetime

import psutil
from appscale.common import appscale_info

from appscale.hermes.stats.models import (
  NodeCPU, NodeLoadAvg, NodeMemory, NodeSwap, NodeDiskIO, NodePartition,
  NodeNetwork, NodeStatsSnapshot
)


class NodeStatsSource(object):

  @staticmethod
  def get_current():
    """ Method for building an instance of NodeStatsSnapshot.
    It collects information about usage of main resource on the machine.

    Returns:
      An object of NodeStatsSnapshot with detailed explanation of resources used
      on the machine
    """
    utc_timestamp = time.mktime(datetime.now().timetuple())
    start = time.time()
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
    logging.info("Prepared local node stats in {elapsed:.1f}s."
                 .format(elapsed=time.time()-start))
    return stats
