""" Tries to stop all Monit services until they are stopped. """
import argparse
import logging
import socket
import time

from appscale.common.constants import LOG_FORMAT
from appscale.common.monit_interface import (MonitOperator, MonitStates,
                                             MonitUnavailable)
from appscale.common.retrying import retry


def order_services(running_services):
  """ Arranges a list of running services in the order they should be stopped.

  Args:
    running_services: A list of strings specifying running services.
  Returns:
    A tuple with two items. The first is a list of ordered services. The second
    is a list of remaining services that are not recognized.
  """
  service_order = [
    # First, stop the services that manage other services.
    'controller',
    'admin_server',
    'appmanagerserver',

    # Next, stop routing requests to running instances.
    'nginx',
    'app_haproxy',

    # Next, stop application runtime instances.
    'app___',
    'api-server_',

    # Next, stop services that depend on other services.
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

  return ordered_services, running_services


def start_service():
  """ Starts a service using the Monit HTTP API. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to start')
  args = parser.parse_args()

  monit_operator = MonitOperator()
  monit_retry = retry(max_retries=5, retry_on_exception=MonitUnavailable)
  send_w_retries = monit_retry(monit_operator.send_command_sync)
  send_w_retries(args.service, 'start')


def stop_service():
  """ Stops a service using the Monit HTTP API. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to stop')
  args = parser.parse_args()

  monit_operator = MonitOperator()
  monit_retry = retry(max_retries=5, retry_on_exception=MonitUnavailable)
  send_w_retries = monit_retry(monit_operator.send_command_sync)
  send_w_retries(args.service, 'stop')


def main():
  """ Tries to stop all Monit services until they are stopped. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  monit_operator = MonitOperator()
  hostname = socket.gethostname()

  logging.info('Waiting for monit to stop services')
  logged_service_warning = False
  stopped_count = 0
  while True:
    entries = monit_operator.get_entries_sync()
    services = {service: state for service, state in entries.items()
                if 'cron' not in service and service != hostname}
    running = {service: state for service, state in services.items()
               if state not in (MonitStates.STOPPED, MonitStates.UNMONITORED)}
    if not running:
      logging.info('Finished stopping services')
      break

    if len(services) - len(running) != stopped_count:
      stopped_count = len(services) - len(running)
      logging.info(
        'Stopped {}/{} services'.format(stopped_count, len(services)))

    try:
      ordered_services, unrecognized_services = order_services(running.keys())
      if unrecognized_services and not logged_service_warning:
        logging.warning(
          'Unrecognized running services: {}'.format(unrecognized_services))
        logged_service_warning = True

      ordered_services = ordered_services + unrecognized_services
      service = next((service for service in ordered_services
                      if services[service] != MonitStates.PENDING))

      monit_retry = retry(max_retries=5, retry_on_exception=MonitUnavailable)
      send_w_retries = monit_retry(monit_operator.send_command_sync)
      send_w_retries(service, 'stop')
    except StopIteration:
      # If all running services are pending, just wait until they are not.
      pass

    time.sleep(.3)
