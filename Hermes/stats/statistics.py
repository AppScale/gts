from collections import namedtuple
from datetime import datetime
import os
import time
import sys

import psutil

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


# Lightweight data structures for describing resource usage:
_NodeCPU = namedtuple('NodeCPU', ['user', 'system', 'idle', 'percent', 'count'])
_NodeLoadAvg = namedtuple(
  'NodeLoadAvg', ['last_1min', 'last_5min', 'last_15min']
)
_NodeMemory = namedtuple('NodeMemory', ['total', 'available', 'used'])
_NodeSwap = namedtuple('NodeSwap', ['total', 'free', 'used'])
_NodeDiskIO = namedtuple(
  'NodeDiskIO', ['read_count', 'write_count', 'read_bytes', 'write_bytes',
                 'read_time', 'write_time']
)
_NodePartition = namedtuple(
  'NodePartition', ['mountpoint', 'total', 'free', 'used']
)
_NodeNetwork = namedtuple(
  'NodeNetwork', ['bytes_sent', 'bytes_recv', 'packets_sent', 'packets_recv',
                  'errin', 'errout', 'dropin', 'dropout', 'connections_num']
)


class NodeStats(object):
  """
  Object of NodeStats is kind of structured container for all info related 
  to resources used on the machine. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.
  
  Every Hermes node collects its machine statistics, but Master node also
  requests this statistics of all nodes in cluster.
  """
  def __init__(self, private_ip, timestamp, cpu, memory, swap, disk_io,
               partitions_dict, network, loadavg):
    self.private_ip = private_ip
    self.timestamp = timestamp
    self.cpu = cpu
    """ :type _NodeCPU """
    self.memory = memory
    """ :type _NodeMemory """
    self.swap = swap
    """ :type _NodeSwap """
    self.disk_io = disk_io
    """ :type _NodeDiskIO """
    self.partitions_dict = partitions_dict
    """ :type dict[str, _NodePartition] """
    self.network = network
    """ :type _NodeNetwork """
    self.loadavg = loadavg
    """ :type _NodeLoadAvg """

  @staticmethod
  def describe_node():
    """ Static method for building an instance of NodeStats.
    It collects information about usage of main resource on the machine.
    
    Returns:
      An object of NodeStats with detailed explanation of resources used
      on the machine
    """
    timestamp = time.mktime(datetime.utcnow().timetuple())

    # CPU usage
    cpu_times = psutil.cpu_times()
    cpu = _NodeCPU(
      user=cpu_times.user, system=cpu_times.system, idle=cpu_times.idle,
      percent=psutil.cpu_percent(), count=psutil.cpu_count()
    )

    # AvgLoad
    loadavg = _NodeLoadAvg(os.getloadavg())

    # Memory usage
    virtual = psutil.virtual_memory()
    memory = _NodeMemory(
      total=virtual.total, available=virtual.available, used=virtual.used)

    # Swap usage
    swap_mem = psutil.swap_memory()
    swap = _NodeSwap(
      total=swap_mem.total, free=swap_mem.free, used=swap_mem.used
    )

    # Disk usage
    partitions = psutil.disk_partitions(all=True)
    partitions_dict = {}
    for part in partitions:
      usage = psutil.disk_usage(part.mountpoint)
      partitions_dict[part.mountpoint] = _NodePartition(
        total=usage.total, used=usage.used, free=usage.free
      )
    io_counters = psutil.disk_io_counters()
    disk_io = _NodeDiskIO(
      read_count=io_counters.read_count, write_count=io_counters.write_count,
      read_bytes=io_counters.read_bytes, write_bytes=io_counters.write_bytes,
      read_time=io_counters.read_time, write_time=io_counters.write_time
    )

    # Network usage
    network_io = psutil.net_io_counters()
    network = _NodeNetwork(
      bytes_sent=network_io.bytes_sent, bytes_recv=network_io.bytes_recv,
      packets_sent=network_io.packets_sent, packets_recv=network_io.packets_recv,
      errin=network_io.errin, errout=network_io.errout, dropin=network_io.dropin,
      dropout=network_io.dropout, connections_num=len(psutil.net_connections())
    )

    return NodeStats(
      private_ip=appscale_info.get_private_ip(), timestamp=timestamp,
      cpu=cpu, memory=memory, swap=swap, disk_io=disk_io,
      partitions_dict=partitions_dict, network=network, loadavg=loadavg
    )


# Lightweight data structures for describing resource usage:
_ProcessCPU = namedtuple('ProcessCPU', ['user', 'system', 'percent'])
_ProcessMemory = namedtuple('ProcessMemory', ['resident', 'virtual', 'unique'])
_ProcessDiskIO = namedtuple(
  'ProcessDiskIO', ['read_count', 'write_count', 'read_bytes', 'write_bytes']
)
_ProcessNetwork = namedtuple('ProcessNetwork', ['connections_num'])
_ProcessChildrenSum = namedtuple(
  'ProcessChildrenSum', ['cpu', 'memory', 'disk_io', 'network', 'threads_num']
)


class ProcessStats(object):
  """
  Object of ProcessStats is kind of structured container for all info related 
  to resources used by specific process. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.
  
  Every Hermes node collects its processes statistics, but Master node also
  requests this statistics of all nodes in cluster.
  All processes started by monit should be profiled.
  """

  def __init__(self, pid, service_name, cmdline, timestamp, cpu, memory, disk_io,
               network, threads_num, children_stats_sum, children_num):
     self.pid = pid
     self.service_name = service_name
     self.cmdline = cmdline
     self.timestamp = timestamp
     self.cpu = cpu
     """ :type _ProcessCPU """
     self.memory = memory
     """ :type _ProcessMemory """
     self.disk_io = disk_io
     """ :type _ProcessDiskIO """
     self.network = network
     """ :type _ProcessNetwork """
     self.threads_num = threads_num
     self.children_stats_sum = children_stats_sum
     """ :type _ProcessChildrenSum """
     self.children_num = children_num

  @staticmethod
  def describe_process(pid, service_name):
    """ Static method for building an instance of ProcessStats.
    It summarize stats of the specified process and its children.
    
    Args:
      pid: Process ID to describe
      service_name: descriptive name of a service it corresponds to
                    (e.g. app___appscaledashboard, taskqueue, datastore, search,
                     cassandra, zookeeper, solr, ...)
    Returns:
      An object of ProcessStats with detailed explanation of resources used by 
      the specified process and its children
    """
    # Get information about processes hierarchy (the process and its children)
    process = psutil.Process(pid)
    children_info = [child.oneshot() for child in process.children()]
    process_info = process.oneshot()

    timestamp = time.mktime(datetime.utcnow().timetuple())

    # CPU usage
    raw_cpu= process_info.cpu_times()
    cpu = _ProcessCPU(user=raw_cpu.user, system=raw_cpu.system)
    children_cpu = _ProcessCPU(user=raw_cpu.children_user,
                               system=raw_cpu.children_system)

    # Memory usage
    raw_mem = process_info.memory_full_info()
    memory = _ProcessMemory(resident=raw_mem.rss, virtual=raw_mem.vms,
                            unique=raw_mem.uss)
    children_raw_mem = [child.memory_full_info() for child in children_info]
    children_memory = _ProcessMemory(
      resident=sum(m.rss for m in children_raw_mem),
      virtual=sum(m.vms for m in children_raw_mem),
      unique=sum(m.uss for m in children_raw_mem)
    )

    # Summarized values of DiskIO usage
    raw_disk = process_info.io_counters()
    disk_io = _ProcessDiskIO(read_count=raw_disk.read_count,
                             write_count=raw_disk.write_count,
                             read_bytes=raw_disk.read_bytes,
                             write_bytes=raw_disk.write_bytes)
    children_raw_disk = [child.io_counters() for child in children_info]
    children_disk_io = _ProcessDiskIO(
      read_count=sum(d.read_count for d in children_raw_disk),
      write_count=sum(d.write_count for d in children_raw_disk),
      read_bytes=sum(d.read_bytes for d in children_raw_disk),
      write_bytes=sum(d.write_bytes for d in children_raw_disk)
    )

    # Summarized values of Network usage
    network = _ProcessNetwork(connections_num=len(process_info.connections()))
    children_network = _ProcessNetwork(
      connections_num=sum(len(child.connections()) for child in children_info)
    )

    # Summarized values about Threading
    threads_num = len(process_info.thread())
    children_threads_num = sum(len(child.threads()) for child in children_info)

    children_sum = _ProcessChildrenSum(
      cpu=children_cpu, memory=children_memory, disk_io=children_disk_io,
      network=children_network, threads_num=children_threads_num
    )

    return ProcessStats(
      pid=pid, service_name=service_name, cmdline=process_info.cmdline(),
      timestamp=timestamp, cpu=cpu, memory=memory, disk_io=disk_io,
      network=network, threads_num=threads_num, children_stats_sum=children_sum,
      children_num=len(children_info)
    )


class ServiceRequestsStats(object):
  """
  Instance of this class stores structured information about service usage.
  
  This kind of statistics is supposed to be collected only on LoadBalancer node
  where haproxy is run
  """
  def __init__(self):
    pass

  @staticmethod
  def describe_service(haproxy_backend_name):
    # TODO
    pass
