import asyncio

import psutil
import pytest
from mock import patch, MagicMock

from appscale.hermes.resources import process


def future(value=None):
  future_obj = asyncio.Future()
  future_obj.set_result(value)
  return future_obj


# cat /lib/systemd/system/appscale-*.target
# | grep -E "^After=.*\.service$" | cut -d "=" -f 2
APPSCALE_TARGETS = b"""
ejabberd.service                                                                                                                                                                                                                              
nginx.service                                                                                                                                                                                                                                 
rabbitmq-server.service                                                                                                                                                                                                                       
zookeeper.service 
"""

# systemctl --no-legend list-units "appscale-*.service" | cut -d " " -f 1
APPSCALE_SERVICES = b"""
appscale-blobstore.service
appscale-cassandra.service
appscale-controller.service
appscale-groomer.service
appscale-haproxy@app.service
appscale-haproxy@service.service
appscale-hermes.service
appscale-infrastructure@basic.service
appscale-instance-manager.service
appscale-instance-run@testapp_mod1_v1_1570022208920-20000.service
appscale-memcached.service
appscale-transaction-groomer.service
appscale-uaserver.service
"""

# systemctl show --property MainPID --value <SERVICE>
SERVICE_PID_MAP = {
  'ejabberd.service': b'9021',
  'nginx.service': b'9022',
  'rabbitmq-server.service': b'9023',
  'zookeeper.service': b'9024',
  'appscale-blobstore.service': b'10025',
  'appscale-cassandra.service': b'10026',
  'appscale-controller.service': b'10027',
  'appscale-groomer.service': b'10028',
  'appscale-haproxy@app.service': b'10029',
  'appscale-haproxy@service.service': b'10030',
  'appscale-hermes.service': b'10031',
  'appscale-infrastructure@basic.service': b'10032',
  'appscale-instance-manager.service': b'10033',
  'appscale-instance-run@testapp_mod1_v1_1570022208920-20000.service': b'10034',
  'appscale-memcached.service': b'10035',
  'appscale-transaction-groomer.service': b'10036',
  'appscale-uaserver.service': b'10037',
}

# for slice in /sys/fs/cgroup/systemd/appscale.slice/appscale-*.slice/; do
#     sed -e "s|\$| ${slice}|" ${slice}/cgroup.procs
# done
APPSCALE_SLICE_PIDS = b"""
11038 /sys/fs/cgroup/systemd/appscale.slice/appscale-datastore.slice/
11039 /sys/fs/cgroup/systemd/appscale.slice/appscale-datastore.slice/
11040 /sys/fs/cgroup/systemd/appscale.slice/appscale-search.slice/
"""


@pytest.mark.asyncio
async def test_get_known_processes():
  subprocess_mocks = []

  # Mock `cat /lib/systemd/system/appscale-*.target | ...` output
  targets_mock = MagicMock(returncode=0)
  stdout, stderr = APPSCALE_TARGETS, b''
  targets_mock.communicate.return_value = future((stdout, stderr))
  subprocess_mocks.append(('cat /lib/systemd/', targets_mock))

  # Mock `systemctl --no-legend list-units "appscale-*.service" | ...` output
  list_units_mock = MagicMock(returncode=0)
  stdout, stderr = APPSCALE_SERVICES, b''
  list_units_mock.communicate.return_value = future((stdout, stderr))
  subprocess_mocks.append(('systemctl --no-legend list-units', list_units_mock))

  # Mock `systemctl show --property MainPID --value <SERVICE>` output
  for service, pid in SERVICE_PID_MAP.items():
    show_mainpid_mock = MagicMock(returncode=0)
    stdout, stderr = pid, b''
    show_mainpid_mock.communicate.return_value = future((stdout, stderr))
    subprocess_mocks.append(('--value {}'.format(service), show_mainpid_mock))

  # Mock `for slice in /sys/fs/cgroup/systemd/appscale.slice/... ; do...` output
  appscale_slice_pids_mock = MagicMock(returncode=0)
  stdout, stderr = APPSCALE_SLICE_PIDS, b''
  appscale_slice_pids_mock.communicate.return_value = future((stdout, stderr))
  subprocess_mocks.append(('for slice in /sys/fs/', appscale_slice_pids_mock))

  def fake_subprocess_shell(command, **kwargs):
    for matcher, command_mock in subprocess_mocks:
      if matcher in command:
        return future(command_mock)
    assert False, 'Unexpected command "{}"'.format(command)

  subprocess_patcher = patch(
    'asyncio.create_subprocess_shell',
    side_effect=fake_subprocess_shell
  )

  # ^^^ ALL INPUTS ARE SPECIFIED (or mocked) ^^^
  with subprocess_patcher:
    # Calling method under test
    known_processes = await process.get_known_processes()

  # ASSERTING EXPECTATIONS
  assert known_processes == {
    9021: ['appscale', 'ejabberd'],
    9022: ['appscale', 'nginx'],
    9023: ['appscale', 'rabbitmq-server'],
    9024: ['appscale', 'zookeeper'],
    10025: ['appscale', 'blobstore'],
    10026: ['appscale', 'cassandra'],
    10027: ['appscale', 'controller'],
    10028: ['appscale', 'groomer'],
    10029: ['appscale', 'haproxy', '_app'],
    10030: ['appscale', 'haproxy', '_service'],
    10031: ['appscale', 'hermes'],
    10032: ['appscale', 'infrastructure', '_basic'],
    10033: ['appscale', 'instance-manager'],
    10034: ['appscale', 'instance-run', '_testapp', '_mod1', '_v1', '_1570022208920-20000'],
    10035: ['appscale', 'memcached'],
    10036: ['appscale', 'transaction-groomer'],
    10037: ['appscale', 'uaserver'],
    11038: ['appscale', 'datastore'],
    11039: ['appscale', 'datastore'],
    11040: ['appscale', 'search'],
  }


@pytest.mark.asyncio
async def test_init_process_info():
  # Get info about current process
  psutil_process = psutil.Process()
  proc_info = psutil_process.as_dict(process.PROCESS_ATTRS)
  psutil_process.info = proc_info

  my_pid = psutil_process.pid
  # Call function under test
  process_ = process.init_process_info(psutil_process, {my_pid: ['test-tag']})

  # Check if attributes were assigned properly
  assert process_.pid == proc_info['pid']
  assert process_.ppid == proc_info['ppid']
  assert process_.create_time == proc_info['create_time']
  assert process_.status == proc_info['status']
  assert process_.username == proc_info['username']
  assert process_.cwd == proc_info['cwd']
  assert process_.name == proc_info['name']
  assert process_.exe == proc_info['exe']
  assert process_.cmdline == proc_info['cmdline']
  assert process_.own_tags == ['test-tag']
  assert process_.all_tags == ['test-tag']
  assert process_.cpu_user == proc_info['cpu_times'].user
  assert process_.cpu_system == proc_info['cpu_times'].system
  assert process_.cpu_user_1h_diff is None
  assert process_.cpu_system_1h_diff is None
  assert process_.cpu_percent == proc_info['cpu_percent']
  assert process_.memory_resident == proc_info['memory_info'].rss
  assert process_.memory_virtual == proc_info['memory_info'].vms
  assert process_.memory_shared == proc_info['memory_info'].shared
  assert process_.disk_io_read_count == proc_info['io_counters'].read_count
  assert process_.disk_io_write_count == proc_info['io_counters'].write_count
  assert process_.disk_io_read_bytes == proc_info['io_counters'].read_bytes
  assert process_.disk_io_write_bytes == proc_info['io_counters'].write_bytes
  assert process_.disk_io_read_count_1h_diff is None
  assert process_.disk_io_write_count_1h_diff is None
  assert process_.disk_io_read_bytes_1h_diff is None
  assert process_.disk_io_write_bytes_1h_diff is None
  assert process_.threads_num == proc_info['num_threads']
  assert process_.file_descriptors_num == proc_info['num_fds']
  assert (
    process_.ctx_switches_voluntary
    == proc_info['num_ctx_switches'].voluntary
  )
  assert (
    process_.ctx_switches_involuntary
    == proc_info['num_ctx_switches'].involuntary
  )
  assert process_.ctx_switches_voluntary_1h_diff is None
  assert process_.ctx_switches_involuntary_1h_diff is None


@pytest.mark.asyncio
async def test_list_processes():
  # Mock `monit status` with empty output
  monit_mock = MagicMock(returncode=0)
  monit_mock.communicate.return_value = future((b'', b''))
  # Mock `systemctl status solr.service` with empty output
  systemctl_mock = MagicMock(returncode=0)
  systemctl_mock.communicate.return_value = future((b'', b''))
  # Mock ServiceManager.get_state result
  state_mock = [
    MagicMock(process=MagicMock(pid=9850), type='datastore'),
    MagicMock(process=MagicMock(pid=9851), type='datastore'),
  ]
  # Mock psutil.process_iter
  fake_processes = [
    MagicMock()
  ]
