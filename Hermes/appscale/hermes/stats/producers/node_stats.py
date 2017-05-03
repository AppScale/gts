import os
import time
from datetime import datetime

import attr
import logging
import psutil
from appscale.common import appscale_info

from appscale.hermes.constants import MISSED
from appscale.hermes.stats.producers.shared import WrongIncludeLists, \
  stats_entity_to_dict
from appscale.hermes.stats.pubsub_base import StatsSource


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
  cpu = attr.ib()  # NodeCPU
  memory = attr.ib()  # NodeMemory
  swap = attr.ib()  # NodeSwap
  disk_io = attr.ib()  # NodeDiskIO
  partitions_dict = attr.ib()  # dict[str, NodePartition]
  network = attr.ib()  # NodeNetwork
  loadavg = attr.ib()  # NodeLoadAvg

  def todict(self, include_lists):
    return node_stats_snapshot_to_dict(self, include_lists)


class NodeStatsSource(StatsSource):
  def __init__(self):
    super(NodeStatsSource, self).__init__("NodeStats")

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
    logging.debug(stats)
    return stats



def node_stats_snapshot_from_dict(dictionary, strict=False):
  """ Addition to attr.asdict function.
  Args:
    dictionary: a dict containing fields for building NodeStatsSnapshot obj.
    strict: a boolean. If True, any missed field will result in IndexError.
            If False, all missed values will be replaced with MISSED.
  Returns:
    an instance of NodeStatsSnapshot
  Raises:
    KeyError if strict is set to True and dictionary is lacking any fields
  """
  cpu = dictionary.get('cpu', {})
  memory = dictionary.get('memory', {})
  swap = dictionary.get('swap', {})
  disk_io = dictionary.get('disk_io', {})
  partitions_dict = dictionary.get('partitions_dict', {})
  network = dictionary.get('network', {})
  loadavg = dictionary.get('loadavg', {})

  if strict:
    return NodeStatsSnapshot(
      utc_timestamp=dictionary['utc_timestamp'],
      private_ip=dictionary['private_ip'],
      cpu=NodeCPU(**{field: cpu[field] for field in NodeCPU.__slots__}),
      memory=NodeMemory(**{field: memory[field]
                           for field in NodeMemory.__slots__}),
      swap=NodeSwap(**{field: swap[field] for field in NodeSwap.__slots__}),
      disk_io=NodeDiskIO(**{field: disk_io[field]
                            for field in NodeDiskIO.__slots__}),
      partitions_dict={
        mount: NodePartition(**{field: part[field]
                                for field in NodePartition.__slots__})
        for mount, part in partitions_dict.iteritems()
      },
      network=NodeNetwork(**{field: network[field]
                             for field in NodeNetwork.__slots__}),
      loadavg=NodeLoadAvg(**{field: loadavg[field]
                             for field in NodeLoadAvg.__slots__})
    )

  return NodeStatsSnapshot(
      utc_timestamp=dictionary.get('utc_timestamp', MISSED),
      private_ip=dictionary.get('private_ip', MISSED),
      cpu=NodeCPU(**{field: cpu.get(field, MISSED)
                     for field in NodeCPU.__slots__}),
      memory=NodeMemory(**{field: memory.get(field, MISSED)
                           for field in NodeMemory.__slots__}),
      swap=NodeSwap(**{field: swap.get(field, MISSED)
                       for field in NodeSwap.__slots__}),
      disk_io=NodeDiskIO(**{field: disk_io.get(field, MISSED)
                            for field in NodeDiskIO.__slots__}),
      partitions_dict={
        mount: NodePartition(**{field: part.get(field, MISSED)
                                for field in NodePartition.__slots__})
        for mount, part in partitions_dict.iteritems()
      },
      network=NodeNetwork(**{field: network.get(field, MISSED)
                             for field in NodeNetwork.__slots__}),
      loadavg=NodeLoadAvg(**{field: loadavg.get(field, MISSED)
                             for field in NodeLoadAvg.__slots__})
    )


def node_stats_snapshot_to_dict(stats, include_lists=None):
  """ Converts an instance of NodeStatsSnapshot to dictionary. Optionally
  it can
  
  Args:
    stats: an instance of NodeStatsSnapshot to render
    include_lists: a dictionary containing include lists for root entity 
        (node stats), for NodeCPU entity, NodeMemory, ...
        e.g.: {
          'node' ['utc_timestamp', 'private_ip', 'memory', 'loadavg'],
          'node.memory': ['available'],
          'node.loadavg': ['last_5min'],
        }
  Returns:
    a dictionary representing an instance of NodeStatsSanpshot
  Raises:
    WrongIncludeLists if unknown field was specified in include_lists
  """
  if include_lists and not isinstance(include_lists, dict):
    raise WrongIncludeLists('include_lists should be dict, actual type is {}'
                            .format(type(include_lists)))

  include = include_lists or {}
  node_stats_fields = set(include.pop('node', NodeStatsSnapshot.__slots__))
  nested_entities = {
    'cpu': set(include.pop('node.cpu', NodeCPU.__slots__)),
    'memory': set(include.pop('node.memory', NodeMemory.__slots__)),
    'swap': set(include.pop('node.swap', NodeSwap.__slots__)),
    'disk_io': set(include.pop('node.disk_io', NodeDiskIO.__slots__)),
    'network': set(include.pop('node.network', NodeNetwork.__slots__)),
    'loadavg': set(include.pop('node.loadavg', NodeLoadAvg.__slots__)),
  }
  partition_fields = set(include.pop('node.partition', NodePartition.__slots__))

  if include:
    # All known include lists were popped
    raise WrongIncludeLists(u'Following include lists are not recognized: {}'
                            .format(include))

  try:
    result = {}
    for field in node_stats_fields:
      value = getattr(stats, field)
      if field == 'partitions_dict':
        # render partitions dict
        result[field] = {
          mount: stats_entity_to_dict(partition, partition_fields)
          for mount, partition in value.iteritems()
        }
      elif field in nested_entities:
        # render nested entity like NodeCPU
        result[field] = stats_entity_to_dict(value, nested_entities[field])
      else:
        result[field] = value
  except AttributeError as err:
    raise WrongIncludeLists(u'Unknown field in include lists ({})'.format(err))

  return result

