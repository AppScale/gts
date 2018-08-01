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
  stopped_count = 0
  while True:
    entries = monit_operator.get_entries_sync()
    services = {service: state for service, state in entries.items()
                if 'cron' not in service and service != hostname}
    running = {service: state for service, state in services.items()
               if state not in (MonitStates.STOPPED, MonitStates.UNMONITORED)}
    if not running:
      print('Finished stopping services')
      break

    if len(services) - len(running) != stopped_count:
      stopped_count = len(services) - len(running)
      print('Stopped {}/{} services'.format(stopped_count, len(services)))

    try:
      service = next((service for service in sorted(running.keys())
                      if services[service] != MonitStates.PENDING))
      subprocess.Popen(['monit', 'stop', service])
    except StopIteration:
      # If all running services are pending, just wait until they are not.
      pass

    time.sleep(.3)
