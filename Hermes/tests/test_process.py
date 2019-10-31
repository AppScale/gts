import os

from mock import patch, call

from appscale.hermes.unified_service_names import ServicesEnum
from appscale.hermes.producers import process_stats

SYSTEMCTL_SHOW = b"""
MainPID=8466
Id=appscale-haproxy@service.service

MainPID=5045
Id=appscale-instance-run@appscaledashboard_default_v1_1566168050028-20000.service
"""


@patch('appscale.common.appscale_info.get_private_ip')
@patch('appscale.hermes.producers.process_stats._process_stats')
@patch('subprocess.check_output')
def test_reading_systemd_status(mock_check_output, mock_process_stats,
                                mock_get_private_ip):
  # Mocking `systemctl show` output and appscale_info.get_private_ip
  mock_check_output.return_value = SYSTEMCTL_SHOW
  mock_get_private_ip.return_value = '1.1.1.1'

  # Calling method under test
  snapshot = process_stats.ProcessesStatsSource.get_current()

  # Checking expectations
  mock_process_stats.assert_has_calls([
    call(8466, ServicesEnum.SERVICE_HAPROXY, 'appscale-haproxy@service.service', '1.1.1.1'),
    call(5045, ServicesEnum.APPLICATION, 'appscale-instance-run@appscaledashboard_default_v1_1566168050028-20000.service', '1.1.1.1')
  ])
  assert isinstance(snapshot, process_stats.ProcessesStatsSnapshot)


@patch('appscale.admin.service_manager.ServiceManager.get_state')
@patch('appscale.common.appscale_info.get_private_ip')
@patch('subprocess.check_output')
@patch('appscale.hermes.producers.process_stats.logger.warning')
def test_process_stats(mock_logging_warn, mock_check_output,
                       mock_get_private_ip, mock_get_state):
  # Mocking `systemctl show` output and appscale_info.get_private_ip
  mock_check_output.return_value = """\
MainPID={mypid}
Id=appscale-instance-run@fakeapp-testprocess-321.service

MainPID=70000
Id=appscale-proc-with-invalid-PID.service\n""".format(mypid=os.getpid()).encode()
  mock_get_private_ip.return_value = '10.10.11.12'
  mock_get_state.return_value = []

  # Calling method under test
  stats_snapshot = process_stats.ProcessesStatsSource.get_current()

  # Verifying outcomes
  assert isinstance(stats_snapshot.utc_timestamp, float)
  processes_stats = stats_snapshot.processes_stats
  mock_logging_warn.assert_called_once_with(
    "Unable to get process stats for proc_with_invalid_PID "
    "(psutil.NoSuchProcess no process found with pid 70000)"
  )
  assert len(processes_stats) == 1
  stats = processes_stats[0]
  assert isinstance(stats, process_stats.ProcessStats)
  assert stats.pid == os.getpid()
  assert stats.monit_name == 'appscale-instance-run@fakeapp-testprocess-321.service'
  assert stats.unified_service_name == 'application'
  assert stats.application_id == 'fakeapp-testprocess'
  assert stats.private_ip == '10.10.11.12'
  assert stats.port == 321
  assert isinstance(stats.cmdline, list)
  assert isinstance(stats.cpu, process_stats.ProcessCPU)
  assert isinstance(stats.memory, process_stats.ProcessMemory)
  assert isinstance(stats.disk_io, process_stats.ProcessDiskIO)
  assert isinstance(stats.network, process_stats.ProcessNetwork)
  assert isinstance(stats.threads_num, int)
  assert isinstance(stats.children_stats_sum, process_stats.ProcessChildrenSum)
  assert isinstance(stats.children_num, int)
