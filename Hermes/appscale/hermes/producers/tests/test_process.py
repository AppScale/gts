import os
import unittest

from mock import patch, call

from appscale.hermes.unified_service_names import ServicesEnum
from appscale.hermes.producers import process_stats

SYSTEMCTL_SHOW = """
MainPID=8466
Id=appscale-haproxy.service

MainPID=5045
Id=appscale-instance-run@appscaledashboard_default_v1_1566168050028-20000.service
"""


class TestCurrentProcessesStats(unittest.TestCase):

  @patch.object(process_stats.appscale_info, 'get_private_ip')
  @patch.object(process_stats, '_process_stats')
  @patch.object(process_stats.subprocess, 'check_output')
  def test_reading_systemd_status(self, mock_check_output, mock_process_stats,
                                  mock_get_private_ip):
    # Mocking `systemctl show` output and appscale_info.get_private_ip
    mock_check_output.return_value = SYSTEMCTL_SHOW
    mock_get_private_ip.return_value = '1.1.1.1'

    # Calling method under test
    snapshot = process_stats.ProcessesStatsSource.get_current()

    # Checking expectations
    mock_process_stats.assert_has_calls([
      call(8466, ServicesEnum.SERVICE_HAPROXY, 'appscale-haproxy.service', '1.1.1.1'),
      call(5045, ServicesEnum.APPLICATION, 'appscale-instance-run@appscaledashboard_default_v1_1566168050028-20000.service', '1.1.1.1')
    ])
    self.assertIsInstance(snapshot, process_stats.ProcessesStatsSnapshot)

  @patch.object(process_stats.appscale_info, 'get_private_ip')
  @patch.object(process_stats.subprocess, 'check_output')
  @patch.object(process_stats.logger, 'warn')
  def test_process_stats(self, mock_logging_warn, mock_check_output,
                               mock_get_private_ip):
    # Mocking `systemctl show` output and appscale_info.get_private_ip
    mock_check_output.return_value = """\
MainPID={mypid}
Id=appscale-instance-run@fakeapp-testprocess-321.service

MainPID=70000
Id=appscale-proc-with-invalid-PID.service\n""".format(mypid=os.getpid())
    mock_get_private_ip.return_value = '10.10.11.12'

    # Calling method under test
    stats_snapshot = process_stats.ProcessesStatsSource.get_current()

    # Verifying outcomes
    self.assertIsInstance(stats_snapshot.utc_timestamp, float)
    processes_stats = stats_snapshot.processes_stats
    mock_logging_warn.assert_called_once_with(
      "Unable to get process stats for proc_with_invalid_PID "
      "(psutil.NoSuchProcess no process found with pid 70000)"
    )
    self.assertEqual(len(processes_stats), 1)
    stats = processes_stats[0]
    self.assertIsInstance(stats, process_stats.ProcessStats)
    self.assertEqual(stats.pid, os.getpid())
    self.assertEqual(stats.monit_name, 'appscale-instance-run@fakeapp-testprocess-321.service')
    self.assertEqual(stats.unified_service_name, 'application')
    self.assertEqual(stats.application_id, 'fakeapp-testprocess')
    self.assertEqual(stats.private_ip, '10.10.11.12')
    self.assertEqual(stats.port, 321)
    self.assertIsInstance(stats.cmdline, list)
    self.assertIsInstance(stats.cpu, process_stats.ProcessCPU)
    self.assertIsInstance(stats.memory, process_stats.ProcessMemory)
    self.assertIsInstance(stats.disk_io, process_stats.ProcessDiskIO)
    self.assertIsInstance(stats.network, process_stats.ProcessNetwork)
    self.assertIsInstance(stats.threads_num, int)
    self.assertIsInstance(stats.children_stats_sum, process_stats.ProcessChildrenSum)
    self.assertIsInstance(stats.children_num, int)
