import unittest
import subprocess

import os

from stats import process
from stats.unified_service_names import ServicesEnum

from flexmock import flexmock


class TestCurrentProcesses(unittest.TestCase):
  def test_reading_monit_status(self):
    flexmock(subprocess).should_receive('check_output').and_return(MONIT_STATUS)
    (flexmock(process.ProcessStats)
       .should_receive('_process_stats')
       .with_args(8466, ServicesEnum.HAPROXY, 'haproxy')
       .ordered())
    (flexmock(process.ProcessStats)
       .should_receive('_process_stats')
       .with_args(5045, ServicesEnum.APPLICATION, 'app___my-25app-20003')
       .ordered())

    process.ProcessStats.current_processes()

  def test_process_stats(self):
    flexmock(subprocess).should_receive('check_output').and_return(
      "Process 'app___fakeapp-testprocess-321'\n"
      "  pid {mypid}\n"
      "Process 'proc-with-invalid-PID'\n"
      "  pid 70000\n".format(os.getpid())
    )
    (flexmock(process.appscale_info)
       .should_receive('get_private_ip')
       .and_return('10.10.11.12')
    )
    (flexmock(process.logging)
       .should_receive('warning')
       .with_args("Unable to get process stats for proc-with-invalid-PID "
                  "(psutil.NoSuchProcess no process found with pid 70000)")
       .once()
    )
    processes_stats = process.ProcessStats.current_processes()
    self.assertEqual(len(processes_stats), 1)
    stats = processes_stats[0]
    self.assertIsInstance(stats, process.ProcessStats)
    self.assertEqual(stats.pid, os.getpid())
    self.assertEqual(stats.monit_name, 'app___fakeapp-testprocess-321')
    self.assertEqual(stats.unified_service_name, 'application')
    self.assertEqual(stats.application_id, 'fakeapp-testprocess')
    self.assertEqual(stats.private_ip, '10.10.11.12')
    self.assertEqual(stats.port, 321)
    self.assertIsInstance(stats.cmdline, list)
    self.assertIsInstance(stats.utc_timestamp, float)
    self.assertIsInstance(stats.cpu, process.ProcessCPU)
    self.assertIsInstance(stats.memory, process.ProcessMemory)
    self.assertIsInstance(stats.disk_io, process.ProcessDiskIO)
    self.assertIsInstance(stats.network, process.ProcessNetwork)
    self.assertIsInstance(stats.threads_num, int)
    self.assertIsInstance(stats.children_stats_sum, process.ProcessChildrenSum)
    self.assertIsInstance(stats.children_num, int)
    print stats

MONIT_STATUS = """
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