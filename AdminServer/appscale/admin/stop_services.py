""" Tries to stop all Monit services until they are stopped. """
import socket
import subprocess
import time

from appscale.common.monit_interface import MonitOperator, MonitStates


def order_services(running_services):
  """ Arranges a list of running services in the order they should be stopped.

  Args:
    running_services: A list of strings specifying running services.
  Returns:
    A list of strings specifying services that should be stopped.
  """
  service_order = [
    # First, stop the services that manage other services.
    'controller',
    'admin_server',
    'appmanagerserver',

    # Next, stop application runtime instances.
    'app___',
    'api-server_',

    # Next, stop services that depend on other services.
    'app_haproxy',
    'service_haproxy',
    'blobstore',
    'celery-',
    'flower',
    'groomer_service',
    'hermes',
    'iaas_manager',
    'log_service',
    'taskqueue-',
    'transaction_groomer',
    'uaserver',

    # Finally, stop the underlying backend services.
    'cassandra',
    'ejabberd',
    'memcached',
    'rabbitmq',
    'zookeeper'
  ]

  ordered_services = []
  for service_type in service_order:
    relevant_entries = [service for service in running_services
                        if service.startswith(service_type)]
    for entry in relevant_entries:
      index = running_services.index(entry)
      ordered_services.append(running_services.pop(index))

  return ordered_services + running_services


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
      service = next((service for service in order_services(running.keys())
                      if services[service] != MonitStates.PENDING))
      subprocess.Popen(['monit', 'stop', service])
    except StopIteration:
      # If all running services are pending, just wait until they are not.
      pass

    time.sleep(.3)
