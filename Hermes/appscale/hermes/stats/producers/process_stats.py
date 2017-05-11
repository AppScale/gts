import logging
import re
import subprocess
import time
from datetime import datetime

import attr
import psutil
from appscale.common import appscale_info

from appscale.hermes.stats.constants import LOCAL_STATS_DEBUG_INTERVAL, MISSED
from appscale.hermes.stats.producers.shared import WrongIncludeLists, \
  stats_entity_to_dict
from appscale.hermes.stats.pubsub_base import StatsSource
from appscale.hermes.stats.unified_service_names import \
  find_service_by_monit_name


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
class ProcessesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  processes_stats = attr.ib()  # list[ProcessStats]

  def todict(self, include_lists=None):
    return processes_stats_snapshot_to_dict(self, include_lists)


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

  unified_service_name = attr.ib()  #| These 4 fields are primary key
  application_id = attr.ib()        #| for an instance of appscale service
  private_ip = attr.ib()            #| - Application ID can be None if
  port = attr.ib()                  #|   process is not related to specific app
                                    #| - port can be missed if it is not
                                    #|   mentioned in monit process name
  cmdline = attr.ib()
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


class ProcessesStatsSource(StatsSource):

  last_debug = 0

  def get_current(self):
    """ Method for building a list of ProcessStats.
    It parses output of `monit status` and generates ProcessStats object
    for each monitored service

    Returns:
      ProcessesStatsSnapshot
    """
    monit_status = subprocess.check_output('monit status', shell=True)
    processes_stats = []
    for match in MONIT_PROCESS_PATTERN.finditer(monit_status):
      monit_name = match.group('name')
      pid = int(match.group('pid'))
      service = find_service_by_monit_name(monit_name)
      private_ip = appscale_info.get_private_ip()
      try:
        stats = _process_stats(pid, service, monit_name, private_ip)
        processes_stats.append(stats)
      except psutil.Error as err:
        logging.warn(u"Unable to get process stats for {monit_name} ({err})"
                     .format(monit_name=monit_name, err=err))
    stats = ProcessesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.utcnow().timetuple()),
      processes_stats=processes_stats
    )
    if time.time() - self.last_debug > LOCAL_STATS_DEBUG_INTERVAL:
      ProcessesStatsSource.last_debug = time.time()
      logging.debug(stats)
    return stats


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
    pid=pid, monit_name=monit_name, unified_service_name=service.name,
    application_id=service.get_application_id_by_monit_name(monit_name),
    port=service.get_port_by_monit_name(monit_name), private_ip=private_ip,
    cmdline=process_info['cmdline'], cpu=cpu, memory=memory, disk_io=disk_io,
    network=network, threads_num=threads_num, children_stats_sum=children_sum,
    children_num=len(children_info)
  )


def process_stats_from_dict(dictionary, strict=False):
  """ Addition to attr.asdict function.
  Args:
    dictionary: a dict containing fields for building ProcessStats obj.
    strict: a boolean. If True, any missed field will result in IndexError.
            If False, all missed values will be replaced with MISSED.
  Returns:
    an instance of ProcessStats
  Raises:
    IndexError if strict is set to True and dictionary is lacking any fields
  """
  cpu = dictionary.get('cpu', {})
  memory = dictionary.get('memory', {})
  disk_io = dictionary.get('disk_io', {})
  network = dictionary.get('network', {})
  children_stats_sum = dictionary.get('children_stats_sum', {})

  if strict:
    return ProcessStats(
      pid=dictionary['pid'],
      monit_name=dictionary['monit_name'],
      unified_service_name=dictionary['unified_service_name'],
      application_id=dictionary['application_id'],
      private_ip=dictionary['private_ip'],
      port=dictionary['port'],
      cmdline=dictionary['cmdline'],
      cpu=ProcessCPU(**{field: cpu[field] for field in ProcessCPU.__slots__}),
      memory=ProcessMemory(**{field: memory[field]
                              for field in ProcessMemory.__slots__}),
      disk_io=ProcessDiskIO(**{field: disk_io[field]
                               for field in ProcessDiskIO.__slots__}),
      network=ProcessNetwork(**{field: network[field]
                                for field in ProcessNetwork.__slots__}),
      threads_num=dictionary['threads_num'],
      children_stats_sum=ProcessChildrenSum(
        **{field: children_stats_sum[field]
           for field in ProcessChildrenSum.__slots__}),
      children_num=dictionary['children_num']
    )
  return ProcessStats(
    pid=dictionary.get('pid', MISSED),
    monit_name=dictionary.get('monit_name', MISSED),
    unified_service_name=dictionary.get('unified_service_name', MISSED),
    application_id=dictionary.get('application_id', MISSED),
    private_ip=dictionary.get('private_ip', MISSED),
    port=dictionary.get('port', MISSED),
    cmdline=dictionary.get('cmdline', MISSED),
    cpu=ProcessCPU(**{field: cpu.get(field, MISSED)
                      for field in ProcessCPU.__slots__}),
    memory=ProcessMemory(**{field: memory.get(field, MISSED)
                            for field in ProcessMemory.__slots__}),
    disk_io=ProcessDiskIO(**{field: disk_io.get(field, MISSED)
                             for field in ProcessDiskIO.__slots__}),
    network=ProcessNetwork(**{field: network.get(field, MISSED)
                              for field in ProcessNetwork.__slots__}),
    threads_num=dictionary.get('threads_num', MISSED),
    children_stats_sum=ProcessChildrenSum(
      **{field: children_stats_sum.get(field, MISSED)
         for field in ProcessChildrenSum.__slots__}),
    children_num=dictionary.get('children_num', MISSED)
  )


def processes_stats_snapshot_from_dict(dictionary, strict=False):
  """ Addition to attr.asdict function.
  Args:
    dictionary: a dict containing fields for building ProcessesStatsSnapshot obj.
    strict: a boolean. If True, any missed field will result in IndexError.
            If False, all missed values will be replaced with MISSED.
  Returns:
    an instance of ProcessesStatsSnapshot
  Raises:
    KeyError if strict is set to True and dictionary is lacking any fields
  """
  if strict:
    return ProcessesStatsSnapshot(
      utc_timestamp=dictionary['utc_timestamp'],
      processes_stats=[
        process_stats_from_dict(process_stats, strict)
        for process_stats in dictionary['processes_stats']
      ]
    )
  return ProcessesStatsSnapshot(
    utc_timestamp=dictionary.get('utc_timestamp', MISSED),
    processes_stats=[
      process_stats_from_dict(process_stats, strict)
      for process_stats in dictionary.get('processes_stats', [])
    ]
  )


def processes_stats_snapshot_to_dict(stats, include_lists=None):
  """ Converts an instance of ProcessesStatsSnapshot to dictionary. Optionally
  it can

  Args:
    stats: an instance of ProcessesStatsSnapshot to render
    include_lists: a dictionary containing include lists for rendering
        ProcessStats entity, ProcessCPU entity, ProcessMemory, ...
        e.g.: {
          'process': ['pid', 'monit_name', 'unified_service_name',
                      'application_id', 'private_ip', 'port', 'cpu', 'memory'],
          'process.cpu': ['user', 'system'],
          'process.memory': ['unique'],
        }
  Returns:
    a dictionary representing an instance of ProcessesStatsSnapshot
  Raises:
    WrongIncludeLists if unknown field was specified in include_lists
  """
  if include_lists and not isinstance(include_lists, dict):
    raise WrongIncludeLists('include_lists should be dict, actual type is {}'
                            .format(type(include_lists)))

  include = include_lists or {}
  process_stats_fields = set(include.pop('process', ProcessStats.__slots__))
  nested_entities = {
    'cpu': set(include.pop('process.cpu', ProcessCPU.__slots__)),
    'memory': set(include.pop('process.memory', ProcessMemory.__slots__)),
    'disk_io': set(include.pop('process.disk_io', ProcessDiskIO.__slots__)),
    'network': set(include.pop('process.network', ProcessNetwork.__slots__)),
    'children_stats_sum': set(include.pop('process.children_stats_sum',
                                          ProcessChildrenSum.__slots__)),
  }

  if include:
    # All known include lists were popped
    raise WrongIncludeLists(u'Following include lists are not recognized: {}'
                            .format(include))

  try:
    rendered_processes = []
    for process in stats.processes_stats:
      rendered_process = {}

      for field in process_stats_fields:
        value = getattr(process, field)
        if field in nested_entities:
          if field == 'children_stats_sum':
            # render children_stats_sum with its nested entities
            children_stats_sum = {}
            for nested_field in nested_entities['children_stats_sum']:
              nested_value = getattr(value, nested_field)
              if nested_value is MISSED:
                continue
              if nested_field in nested_entities:
                children_stats_sum[nested_field] = stats_entity_to_dict(
                  nested_value, nested_entities[nested_field])
              else:
                children_stats_sum[nested_field] = nested_value
            rendered_process[field] = children_stats_sum
          else:
            # render nested entity like ProcessMemory
            rendered_process[field] = \
              stats_entity_to_dict(value, nested_entities[field])
        else:
          rendered_process[field] = value

      rendered_processes.append(rendered_process)
  except AttributeError as err:
    raise WrongIncludeLists(u'Unknown field in include lists ({})'.format(err))

  return {
    'utc_timestamp': stats.utc_timestamp,
    'processes_stats': rendered_processes
  }
