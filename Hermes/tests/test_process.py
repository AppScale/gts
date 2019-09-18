import os

from mock import patch, call

from appscale.hermes.unified_service_names import ServicesEnum
from appscale.hermes.producers import process_stats

MONIT_STATUS = b"""
The Monit daemon 5.6 uptime: 20h 22m

Process 'haproxy'
  status                            Running
  monitoring status                 Monitored
  pid                               8466
  parent pid                        1
  uptime                            20h 21m
  children                          0
  memory kilobytes                  8140
  memory kilobytes total            8140
  memory percent                    0.2%
  memory percent total              0.2%
  cpu percent                       0.0%
  cpu percent total                 0.0%
  data collected                    Wed, 19 Apr 2017 14:15:29

File 'groomer_file_check'
  status                            Accessible
  monitoring status                 Monitored
  permission                        644

Process 'appmanagerserver'
  status                            Not monitored
  monitoring status                 Not monitored
  data collected                    Wed, 19 Apr 2017 13:49:44

Process 'app___my-25app-20003'
  status                            Running
  monitoring status                 Monitored
  pid                               5045
  parent pid                        5044
  uptime                            21h 41m
  children                          1
  memory kilobytes                  65508
  memory kilobytes total            132940
  memory percent                    1.7%
  memory percent total              3.5%
  cpu percent                       0.0%
  cpu percent total                 0.0%
  port response time                0.000s to 10.10.9.111:20000 [DEFAULT via TCP]
  data collected                    Wed, 19 Apr 2017 14:18:33

System 'appscale-image0'
  status                            Running
  monitoring status                 Monitored
  load average                      [0.23] [0.40] [0.46]
  cpu                               2.8%us 2.4%sy 1.3%wa
  memory usage                      2653952 kB [70.7%]
  swap usage                        0 kB [0.0%]
  data collected                    Wed, 19 Apr 2017 14:15:29
"""


@patch('appscale.common.appscale_info.get_private_ip')
@patch('appscale.hermes.producers.process_stats._process_stats')
@patch('subprocess.check_output')
def test_reading_monit_status(mock_check_output, mock_process_stats,
                              mock_get_private_ip):
  # Mocking `monit status` output and appscale_info.get_private_ip
  mock_check_output.return_value = MONIT_STATUS
  mock_get_private_ip.return_value = '1.1.1.1'

  # Calling method under test
  snapshot = process_stats.ProcessesStatsSource.get_current()

  # Checking expectations
  mock_process_stats.assert_has_calls([
    call(8466, ServicesEnum.HAPROXY, 'haproxy', '1.1.1.1'),
    call(5045, ServicesEnum.APPLICATION, 'app___my-25app-20003', '1.1.1.1')
  ])
  assert isinstance(snapshot, process_stats.ProcessesStatsSnapshot)


@patch('appscale.admin.service_manager.ServiceManager.get_state')
@patch('appscale.common.appscale_info.get_private_ip')
@patch('subprocess.check_output')
@patch('appscale.hermes.producers.process_stats.logger.warning')
def test_process_stats(mock_logging_warn, mock_check_output,
                       mock_get_private_ip, mock_get_state):
  # Mocking `monit status` output and appscale_info.get_private_ip
  mock_check_output.return_value = (
    "Process 'app___fakeapp-testprocess-321'\n"
    "  pid {mypid}\n"
    "Process 'proc-with-invalid-PID'\n"
    "  pid 70000\n".format(mypid=os.getpid()).encode()
  )
  mock_get_private_ip.return_value = '10.10.11.12'
  mock_get_state.return_value = []

  # Calling method under test
  stats_snapshot = process_stats.ProcessesStatsSource.get_current()

  # Verifying outcomes
  assert isinstance(stats_snapshot.utc_timestamp, float)
  processes_stats = stats_snapshot.processes_stats
  mock_logging_warn.assert_called_once_with(
    "Unable to get process stats for proc-with-invalid-PID "
    "(psutil.NoSuchProcess no process found with pid 70000)"
  )
  assert len(processes_stats) == 1
  stats = processes_stats[0]
  assert isinstance(stats, process_stats.ProcessStats)
  assert stats.pid == os.getpid()
  assert stats.monit_name == 'app___fakeapp-testprocess-321'
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
