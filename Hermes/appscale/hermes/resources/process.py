import logging
import time
import re

import attr
import psutil

from appscale.common import appscale_info
from appscale.hermes import helper
from appscale.hermes.constants import SubprocessError


logger = logging.getLogger(__name__)

APPSCALE_PROCESS_TAG = 'appscale'
SERVICE_NAME_PATTERN = re.compile(
  r'(appscale-)?(?P<before_at>[^@]+)(@(?P<after_at>[^.]+))?.service'
)
PID_SLICE_LINE_PATTERN = re.compile(
  r'(?P<pid>\d+) /sys/fs/cgroup/systemd/appscale\.slice/appscale-'
  r'(?P<name>[^\.]+)\.slice/'
)


@attr.s(cmp=False, hash=False, slots=True)
class Process(object):
  """
  A container for all parameters representing process state at
  a specific moment of time.
  """
  # A global dict containing previous processes state.
  # It is used for computing *_1h_diff attributes.
  PREVIOUS_STATE = {}

  utc_timestamp = attr.ib(default=None)
  host = attr.ib(default=None)

  long_pid = attr.ib(default=None)
  pid = attr.ib(default=None)
  ppid = attr.ib(default=None)
  create_time = attr.ib(default=None)
  status = attr.ib(default=None)
  username = attr.ib(default=None)
  cwd = attr.ib(default=None)
  name = attr.ib(default=None)
  exe = attr.ib(default=None)
  cmdline = attr.ib(default=None)

  own_tags = attr.ib(default=None)  # Tags related to the process.
  all_tags = attr.ib(default=None)  # Own tags + ancestors' tags.

  cpu_user = attr.ib(default=None)
  cpu_system = attr.ib(default=None)
  cpu_percent = attr.ib(default=None)
  cpu_user_1h_diff = attr.ib(default=None)
  cpu_system_1h_diff = attr.ib(default=None)

  memory_resident = attr.ib(default=None)
  memory_virtual = attr.ib(default=None)
  memory_shared = attr.ib(default=None)

  disk_io_read_count = attr.ib(default=None)
  disk_io_write_count = attr.ib(default=None)
  disk_io_read_bytes = attr.ib(default=None)
  disk_io_write_bytes = attr.ib(default=None)
  disk_io_read_count_1h_diff = attr.ib(default=None)
  disk_io_write_count_1h_diff = attr.ib(default=None)
  disk_io_read_bytes_1h_diff = attr.ib(default=None)
  disk_io_write_bytes_1h_diff = attr.ib(default=None)

  threads_num = attr.ib(default=None)
  file_descriptors_num = attr.ib(default=None)

  ctx_switches_voluntary = attr.ib(default=None)
  ctx_switches_involuntary = attr.ib(default=None)
  ctx_switches_voluntary_1h_diff = attr.ib(default=None)
  ctx_switches_involuntary_1h_diff = attr.ib(default=None)

  sample_time_diff = attr.ib(default=None)


PROCESS_ATTRS = (
  'pid', 'ppid', 'name', 'cwd', 'exe', 'cmdline', 'status', 'username',
  'cpu_times', 'cpu_percent', 'memory_info', 'io_counters', 'num_threads',
  'num_fds', 'num_ctx_switches', 'create_time'
)


async def list_resource():
  """ A coroutine which prepares a list of Process,
  converts it to dictionaries.

  Returns:
    A tuple (list of dict representation of Process, empty list of failures).
  """
  processes = [attr.asdict(process) for process in (await list_processes())]
  failed = []
  return processes, failed


async def list_processes():
  """ Function for building a list of Process.

  Returns:
    A list of Processes.
  """
  start_time = time.time()
  host = appscale_info.get_private_ip()

  # Get dict with known processes (<PID>: <a list of tags>)
  known_processes = await get_known_processes()
  # Iterate through all processes and init majority of its info.
  pid_to_process = {
    '{}_{}_{}'.format(host, process.pid, int(process.create_time() * 1000)):
    init_process_info(process, known_processes)
    for process in psutil.process_iter(attrs=PROCESS_ATTRS, ad_value=None)
  }

  def list_ancestors_tags(ppid):
    """ A recursive function for collecting ancestors' tags.

    Args:
      ppid: An int - parent PID.
    Returns:
      A list of ancestors' tags.
    """
    parent_process = pid_to_process.get(ppid)
    if not parent_process:
      return []
    if parent_process.ppid in [0, 1, 2]:  # Skip common root processes
      return parent_process.own_tags
    return parent_process.own_tags + list_ancestors_tags(parent_process.ppid)

  # Set the rest of information about processes state
  for long_pid, p in pid_to_process.items():
    # Set unique process identifier
    p.long_pid = long_pid
    # and *_1h_diff attributes
    prev = Process.PREVIOUS_STATE.get(p.long_pid)
    if prev:
      # Compute one hour difference coefficient
      diff_coef = 60 * 60 / (start_time - prev.utc_timestamp)
      # Set diff attributes
      p.cpu_user_1h_diff = (
        (p.cpu_user - prev.cpu_user) * diff_coef
      )
      p.cpu_system_1h_diff = (
        (p.cpu_system - prev.cpu_system) * diff_coef
      )
      if p.disk_io_read_count is not None:
        p.disk_io_read_count_1h_diff = (
          (p.disk_io_read_count - prev.disk_io_read_count) * diff_coef
        )
        p.disk_io_write_count_1h_diff = (
          (p.disk_io_write_count - prev.disk_io_write_count) * diff_coef
        )
        p.disk_io_read_bytes_1h_diff = (
          (p.disk_io_read_bytes - prev.disk_io_read_bytes) * diff_coef
        )
        p.disk_io_write_bytes_1h_diff = (
          (p.disk_io_write_bytes - prev.disk_io_write_bytes) * diff_coef
        )
      p.ctx_switches_voluntary_1h_diff = (
        (p.ctx_switches_voluntary - prev.ctx_switches_voluntary) * diff_coef
      )
      p.ctx_switches_involuntary_1h_diff = (
        (p.ctx_switches_involuntary - prev.ctx_switches_involuntary) * diff_coef
      )

    p.utc_timestamp = start_time
    p.host = host
    p.all_tags += list_ancestors_tags(p.ppid)

  processes = pid_to_process.values()
  logger.info(
    "Prepared info about {} processes in {:.3f}s."
    .format(len(processes), time.time() - start_time)
  )
  Process.PREVIOUS_STATE = pid_to_process
  return processes


def init_process_info(psutil_process, known_processes):
  """ Initializes Process entity accoring to information in psutil process
  and known appscale processes.

  Args:
    psutil_process: An instance of psutil.Process.
    known_processes: A dict - tags for known processes (<PID>: <tags>).
  Returns:
    An instance of Process.
  """
  process = Process()

  process_info = psutil_process.info
  cpu_times = process_info['cpu_times']
  memory_info = process_info['memory_info']
  io_counters = process_info['io_counters']
  ctx_switches = process_info['num_ctx_switches']

  # Fill psutil process attributes:
  process.pid = process_info['pid']
  process.ppid = process_info['ppid']
  process.create_time = process_info['create_time']
  process.status = process_info['status']
  process.username = process_info['username']
  process.cwd = process_info['cwd']
  process.name = process_info['name']
  process.exe = process_info['exe']
  process.cmdline = process_info['cmdline']
  process.own_tags = known_processes.get(psutil_process.pid, [process.name])
  process.all_tags = process.own_tags[::]
  process.cpu_user = cpu_times.user
  process.cpu_system = cpu_times.system
  process.cpu_percent = process_info['cpu_percent']
  process.memory_resident = memory_info.rss
  process.memory_virtual = memory_info.vms
  process.memory_shared = memory_info.shared
  if io_counters:
    process.disk_io_read_count = io_counters.read_count
    process.disk_io_write_count = io_counters.write_count
    process.disk_io_read_bytes = io_counters.read_bytes
    process.disk_io_write_bytes = io_counters.write_bytes
  process.threads_num = process_info['num_threads']
  process.file_descriptors_num = process_info['num_fds']
  process.ctx_switches_voluntary = ctx_switches.voluntary
  process.ctx_switches_involuntary = ctx_switches.involuntary
  return process


async def get_known_processes():
  """ Gets tags (e.g.: appscale, taskqueue, datastore, ...)
  for appscale-related processes using systemd-provided information.

  Returns:
    A dict containing tags for known processes (<PID>: <a list of tags>).
  """
  service_processes = await identify_appscale_service_processes()
  slice_processes = await identify_appscale_slice_processes()
  known_processes = service_processes
  known_processes.update(slice_processes)
  return known_processes


async def identify_appscale_service_processes():
  """ Gets tags (e.g.: appscale, taskqueue, datastore, ...)
  for appscale-related processes which are run as service.

  Returns:
    A dict containing tags for known processes (<PID>: <a list of tags>).
  """
  known_processes = {}
  for service in await identify_appscale_services():
    try:
      # Get Main PID for each service
      show_cmd = 'systemctl show --property MainPID --value {}'.format(service)
      output, error = await helper.subprocess(show_cmd, timeout=5)
    except SubprocessError as err:
      logger.warning('Failed to get Main PID for {} ({})'.format(service, err))
      continue
    output = output.strip(' \t\n')
    if output.isdigit() and output != '0':
      pid = int(output)
      process_tags = [APPSCALE_PROCESS_TAG]
      # Sample service names are:
      # appscale-instance-run@testapp_default_v1_1570022208920-20000.service
      # appscale-memcached.service
      match = SERVICE_NAME_PATTERN.match(service)
      if not match:
        logger.warning('Could not parse service name "{}"'.format(service))
        continue
      before_at = match.group('before_at')
      after_at = match.group('after_at')
      process_tags.append(before_at)
      if after_at:
        for part in after_at.split('_'):
          process_tags.append('_{}'.format(part))
      known_processes[pid] = process_tags
  return known_processes


async def identify_appscale_services():
  """ Lists all appscale-related services.

  Returns:
    A list of service names.
  """
  dependencies_cmd = ('cat /lib/systemd/system/appscale-*.target '
                      '| grep -E "^After=.*\.service$" | cut -d "=" -f 2')
  try:
    # Detect appscale dependency services
    output, error = await helper.subprocess(dependencies_cmd, timeout=5)
    services = output.strip().split('\n')
  except SubprocessError as err:
    logger.warning('Failed to detect appscale dependency services '
                   'by running `{}` ({})'.format(dependencies_cmd, err))
    services = []

  services_cmd = ('systemctl --no-legend list-units "appscale-*.service" '
                  '| cut -d " " -f 1')
  try:
    # Detect appscale own services
    output, error = await helper.subprocess(services_cmd, timeout=5)
    services += output.strip().split('\n')
  except SubprocessError as err:
    logger.warning('Failed to detect appscale own services '
                   'by running `{}` ({})'.format(services_cmd, err))
  return services


async def identify_appscale_slice_processes():
  """ Gets tags (e.g.: appscale, taskqueue, datastore, ...)
  for processes running in appscale-slice.

  Returns:
    A dict containing tags for known processes (<PID>: <a list of tags>).
  """
  slice_processes = (
    'for slice in /sys/fs/cgroup/systemd/appscale.slice/appscale-*.slice/;'
    '  do sed -e "s|\$| ${slice}|" ${slice}/cgroup.procs ; done'
  )
  try:
    # Detect appscale own services
    output, error = await helper.subprocess(slice_processes, timeout=5)
  except SubprocessError as err:
    logger.warning('Failed to detect appscale-slice processes '
                   'by running {} ({})'.format(slice_processes, err))
    return {}
  detected_pids = {}
  lines = output.strip(' \t\n').split('\n')
  for line in lines:
    match = PID_SLICE_LINE_PATTERN.match(line)
    if not match:
      logger.warning('Could not parse PID-slice line "{}"'.format(line))
      continue
    pid = int(match.group('pid'))
    detected_pids[pid] = [APPSCALE_PROCESS_TAG, match.group('name')]
  return detected_pids
