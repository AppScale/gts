""" Tries to stop all Monit services until they are stopped. """
import socket
import subprocess
import time

from appscale.common.monit_interface import MonitOperator, MonitStates


def main():
  """ Tries to stop all Monit services until they are stopped. """
  monit_operator = MonitOperator()
  hostname = socket.gethostname()

  print('Waiting for monit to stop services')
  while True:
    monit_entries = monit_operator.get_entries_sync()
    all_stopped = True
    for service in sorted(monit_entries.keys()):
      state = monit_entries[service]
      if 'cron' in service or service == hostname:
        continue

      if state in (MonitStates.STOPPED, MonitStates.UNMONITORED):
        continue

      all_stopped = False
      if state == MonitStates.PENDING:
        continue

      subprocess.Popen(['monit', 'stop', service])
      time.sleep(.3)
      break

    if all_stopped:
      break
