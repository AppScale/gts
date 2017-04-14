import StringIO
import csv
import logging
import os
import subprocess
import sys
import time
from collections import namedtuple, defaultdict
from datetime import datetime

import psutil

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import appscale_info


# Lightweight data structures for describing resource usage:
NodeCPU = namedtuple('NodeCPU', ['user', 'system', 'idle', 'percent', 'count'])
NodeLoadAvg = namedtuple(
  'NodeLoadAvg', ['last_1min', 'last_5min', 'last_15min']
)
NodeMemory = namedtuple('NodeMemory', ['total', 'available', 'used'])
NodeSwap = namedtuple('NodeSwap', ['total', 'free', 'used'])
NodeDiskIO = namedtuple(
  'NodeDiskIO', ['read_count', 'write_count', 'read_bytes', 'write_bytes',
                 'read_time', 'write_time']
)
NodePartition = namedtuple(
  'NodePartition', ['mountpoint', 'total', 'free', 'used']
)
NodeNetwork = namedtuple(
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
    """ :type NodeCPU """
    self.memory = memory
    """ :type NodeMemory """
    self.swap = swap
    """ :type NodeSwap """
    self.disk_io = disk_io
    """ :type NodeDiskIO """
    self.partitions_dict = partitions_dict
    """ :type dict[str, NodePartition] """
    self.network = network
    """ :type NodeNetwork """
    self.loadavg = loadavg
    """ :type NodeLoadAvg """

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
    cpu = NodeCPU(
      user=cpu_times.user, system=cpu_times.system, idle=cpu_times.idle,
      percent=psutil.cpu_percent(), count=psutil.cpu_count()
    )

    # AvgLoad
    loadavg = NodeLoadAvg(os.getloadavg())

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
    partitions = psutil.disk_partitions(all=True)
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
ProcessCPU = namedtuple('ProcessCPU', ['user', 'system', 'percent'])
ProcessMemory = namedtuple('ProcessMemory', ['resident', 'virtual', 'unique'])
ProcessDiskIO = namedtuple(
  'ProcessDiskIO', ['read_count', 'write_count', 'read_bytes', 'write_bytes']
)
ProcessNetwork = namedtuple('ProcessNetwork', ['connections_num'])
ProcessChildrenSum = namedtuple(
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

  def __init__(self, pid, appscale_service_name, cmdline, timestamp, cpu,
               memory, disk_io, network, threads_num, children_stats_sum,
               children_num):
     self.pid = pid
     self.appscale_service_name = appscale_service_name
     self.cmdline = cmdline
     self.timestamp = timestamp
     self.cpu = cpu
     """ :type ProcessCPU """
     self.memory = memory
     """ :type ProcessMemory """
     self.disk_io = disk_io
     """ :type ProcessDiskIO """
     self.network = network
     """ :type ProcessNetwork """
     self.threads_num = threads_num
     self.children_stats_sum = children_stats_sum
     """ :type ProcessChildrenSum """
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
      pid=pid, appscale_service_name=service_name, cmdline=process_info.cmdline(),
      timestamp=timestamp, cpu=cpu, memory=memory, disk_io=disk_io,
      network=network, threads_num=threads_num, children_stats_sum=children_sum,
      children_num=len(children_info)
    )


# List of fields was got from HAProxy v1.5 documentation:
# https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1

HAPROXY_LISTENER_FIELDS = [
  'pxname', 'svname', 'scur', 'smax', 'slim', 'stot', 'bin', 'bout', 'dreq',
  'dresp', 'ereq', 'status', 'pid', 'iid', 'sid', 'type'
]

HAPROXY_FRONTEND_FIELDS = [
  'pxname', 'svname', 'scur', 'smax', 'slim', 'stot', 'bin', 'bout', 'dreq',
  'dresp', 'ereq', 'status', 'pid', 'iid', 'type', 'rate', 'rate_lim',
  'rate_max', 'hrsp_1xx', 'hrsp_2xx', 'hrsp_3xx', 'hrsp_4xx', 'hrsp_5xx',
  'hrsp_other', 'req_rate', 'req_rate_max', 'req_tot', 'comp_in', 'comp_out',
  'comp_byp', 'comp_rsp'
]

HAPROXY_BACKEND_FIELDS = [
  'pxname', 'svname', 'qcur', 'qmax', 'scur', 'smax', 'slim', 'stot', 'bin',
  'bout', 'dreq', 'dresp', 'econ', 'eresp', 'wretr', 'wredis', 'status',
  'weight', 'act', 'bck', 'chkdown', 'lastchg', 'downtime', 'pid', 'iid',
  'lbtot', 'type', 'rate', 'rate_max', 'hrsp_1xx', 'hrsp_2xx', 'hrsp_3xx',
  'hrsp_4xx', 'hrsp_5xx', 'hrsp_other', 'cli_abrt', 'srv_abrt', 'comp_in',
  'comp_out', 'comp_byp', 'comp_rsp', 'lastsess', 'qtime', 'ctime', 'rtime',
  'ttime'
]

HAPROXY_SERVER_FIELDS = [
  'pxname', 'svname', 'qcur', 'qmax', 'scur', 'smax', 'slim', 'stot', 'bin',
  'bout', 'dresp', 'econ', 'eresp', 'wretr', 'wredis', 'status', 'weight',
  'act', 'bck', 'chkfail', 'chkdown', 'lastchg', 'downtime', 'qlimit', 'pid',
  'iid', 'sid', 'throttle', 'lbtot', 'tracked', 'type', 'rate', 'rate_max',
  'check_status', 'check_code', 'check_duration', 'hrsp_1xx', 'hrsp_2xx',
  'hrsp_3xx', 'hrsp_4xx', 'hrsp_5xx', 'hrsp_other', 'hanafail', 'cli_abrt',
  'srv_abrt', 'lastsess', 'last_chk', 'last_agt', 'qtime', 'ctime', 'rtime',
  'ttime'
]

ALL_HAPROXY_FIELDS = set(
  HAPROXY_LISTENER_FIELDS + HAPROXY_FRONTEND_FIELDS
  + HAPROXY_BACKEND_FIELDS + HAPROXY_SERVER_FIELDS
)
INTEGER_FIELDS = set(ALL_HAPROXY_FIELDS) - {'pxname', 'svname',
                                            'status', 'check_status'}

class _UnknownValue(object):
  """
  Instance of this private class denotes unknown value.
  It's used to denote values of stats properties which are missed
  in haproxy stats csv
  """
  def __nonzero__(self):
    return False
  def __repr__(self):
    return "-"

UNKNOWN_VALUE = _UnknownValue()

HAProxyListenerStats = namedtuple('HAProxyListenerStats', HAPROXY_LISTENER_FIELDS)
HAProxyFrontendStats = namedtuple('HAProxyFrontendStats', HAPROXY_FRONTEND_FIELDS)
HAProxyBackendStats = namedtuple('HAProxyBackendStats', HAPROXY_BACKEND_FIELDS)
HAProxyServerStats = namedtuple('HAProxyServerStats', HAPROXY_SERVER_FIELDS)


class InvalidHAProxyStats(ValueError):
  pass


class ProxyStats(object):
  """
  Object of ProxyStats is kind of structured container for all haproxy stats
  provided for the specific proxy (e.g.: TaskQueue, UserAppServer, ...)
  
  Only those Hermes nodes which are collocated with HAProxy collects this stats.
  """

  def __init__(self, name, appscale_service_name, timestamp,
               frontend, backend, servers, listeners):
    self.name = name
    self.appscale_service_name = appscale_service_name
    self.timestamp = timestamp
    self.frontend = frontend
    """ :type HAProxyFrontendStats """
    self.backend = backend
    """ :type HAProxyBackendStats """
    self.servers = servers
    """ :type list[HAProxyServerStats] """
    self.servers = listeners
    """ :type list[HAProxyListenerStats] """

  @staticmethod
  def _get_field_value(row, field_name):
    """ Private method for getting value from csv cell """
    if field_name not in row:
      return UNKNOWN_VALUE
    value = row[field_name]
    if not value:
      return None
    if field_name in INTEGER_FIELDS:
      return int(value)
    return value

  @staticmethod
  def describe_proxies(stats_socket_path, appscale_names_mapper):
    """ Static method which parses haproxy stats and returns detailed
    proxy statistics for all proxies.
    
    Args:
      stats_socket_path: a str representing path to haproxy stats socket
      appscale_names_mapper: an object with method 'from_proxy_name' which
                             returns standard appscale name for the proxy 
    Returns:
      dict[<proxy_name>, ProxyStats]
    """
    # Get CSV table with haproxy stats
    csv_text = subprocess.check_output(
      "echo 'show stat' | socat stdio unix-connect:{}"
      .format(stats_socket_path), shell=True
    ).replace("# ", "", 1)
    csv_buffer = StringIO.StringIO(csv_text)
    table = csv.DictReader(csv_buffer, delimiter=',')
    missed_fields = ALL_HAPROXY_FIELDS - set(table.fieldnames)
    if missed_fields:
      logging.warning("HAProxy stats fields {} are missed. Old version of "
                      "HAProxy is probably used (v1.5+ is expected)"
                      .format(list(missed_fields)))

    timestamp = time.mktime(datetime.utcnow().timetuple())

    # Parse haproxy stats output line by line
    parsed_objects = defaultdict(list)
    for row in table:
      proxy_name = row['pxname']
      svname = row['svname']
      if svname == 'FRONTEND':
        stats_type = HAProxyFrontendStats
      elif svname == 'BACKEND':
        stats_type = HAProxyBackendStats
      elif row['qcur']:
        # Listener stats doesn't have "current queued requests" property
        stats_type = HAProxyServerStats
      else:
        stats_type = HAProxyListenerStats

      stats_values = {
        field: ProxyStats._get_field_value(row, field)
        for field in stats_type._fields
      }

      stats = stats_type(**stats_values)
      parsed_objects[proxy_name].append(stats)

    # Attempt to merge separate stats object to ProxyStats instances
    proxy_stats_dict = {}
    for proxy_name, stats_objects in parsed_objects.iteritems():
      frontends = [stats for stats in stats_objects
                   if isinstance(stats, HAProxyFrontendStats)]
      backends = [stats for stats in stats_objects
                  if isinstance(stats, HAProxyBackendStats)]
      servers = [stats for stats in stats_objects
                 if isinstance(stats, HAProxyServerStats)]
      listeners = [stats for stats in stats_objects
                   if isinstance(stats, HAProxyListenerStats)]
      if len(frontends) != 1 or len(backends) != 1:
        raise InvalidHAProxyStats(
          "Exactly one FRONTEND and one BACKEND line should correspond to "
          "a single proxy. Proxy '{}' has {} frontends and {} backends"
          .format(proxy_name, len(frontends), len(backends))
        )

      # Create ProxyStats object which contains all stats related to the proxy
      appscale_name = appscale_names_mapper.from_proxy_name(proxy_name)
      proxy_stats = ProxyStats(
        name=proxy_name, appscale_service_name=appscale_name,
        timestamp=timestamp, frontend=frontends[0], backend=backends[0],
        servers=servers, listeners=listeners
      )
      proxy_stats_dict[proxy_name] = proxy_stats

    return proxy_stats_dict
