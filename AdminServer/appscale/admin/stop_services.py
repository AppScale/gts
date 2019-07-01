""" Tries to stop all Monit services until they are stopped. """
import argparse
import logging
import socket
import sys
import time

from appscale.common.async_retrying import retry_coroutine
from tornado import gen, ioloop

from appscale.common.constants import LOG_FORMAT
from appscale.common.monit_interface import (DEFAULT_RETRIES, MonitOperator,
                                             MonitStates, MonitUnavailable,
                                             ProcessNotFound)
from appscale.common.retrying import retry

logger = logging.getLogger(__name__)


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
    ['controller'],
    ['admin_server'],
    ['appmanagerserver'],

    # Next, stop routing requests to running instances.
    ['nginx'],
    ['app_haproxy'],

    # Next, stop application runtime instances.
    ['app___'],
    ['api-server_'],

    # Next, stop services that depend on other services.
    ['service_haproxy'],
    ['blobstore', 'celery-', 'flower', 'groomer_service', 'hermes',
     'iaas_manager', 'log_service', 'taskqueue-', 'transaction_groomer',
     'uaserver'],

    # Finally, stop the underlying backend services.
    ['cassandra', 'ejabberd', 'memcached', 'rabbitmq', 'zookeeper']
  ]

  ordered_services = []
  for service_types in service_order:
    parallel_group = []
    relevant_entries = [
      service
      for service in running_services
      for service_type in service_types
      if service.startswith(service_type)
    ]
    for entry in relevant_entries:
      index = running_services.index(entry)
      parallel_group.append(running_services.pop(index))
    ordered_services.append(parallel_group)

  return ordered_services, running_services


def start_service():
  """ Starts a service using the Monit HTTP API. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to start')
  args = parser.parse_args()

  monit_operator = MonitOperator()
  monit_retry = retry(max_retries=5, retry_on_exception=DEFAULT_RETRIES)
  send_w_retries = monit_retry(monit_operator.send_command_sync)
  send_w_retries(args.service, 'start')


def stop_service():
  """ Stops a service using the Monit HTTP API. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to stop')
  args = parser.parse_args()

  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  try:
    monit_operator = MonitOperator()
    monit_retry = retry(max_retries=5, retry_on_exception=DEFAULT_RETRIES)
    send_w_retries = monit_retry(monit_operator.send_command_sync)
    send_w_retries(args.service, 'stop')
  except ProcessNotFound as e:
    logger.info(str(e))
    sys.exit(1)


@gen.coroutine
def main_async():
  """ Tries to stop all Monit services until they are stopped. """
  monit_operator = MonitOperator()
  hostname = socket.gethostname()

  logger.info('Waiting for monit to stop services')
  logged_service_warning = False
  stopped_count = 0
  while True:
    entries = yield monit_operator.get_entries()
    services = {service: state for service, state in entries.items()
                if 'cron' not in service and service != hostname}
    running = {service: state for service, state in services.items()
               if state not in (MonitStates.STOPPED, MonitStates.UNMONITORED)}
    if not running:
      logger.info('Finished stopping services')
      break

    if len(services) - len(running) != stopped_count:
      stopped_count = len(services) - len(running)
      logger.info(
        'Stopped {}/{} services'.format(stopped_count, len(services)))

    try:
      ordered_services, unrecognized_services = order_services(running.keys())
      if unrecognized_services and not logged_service_warning:
        logger.warning(
          'Unrecognized running services: {}'.format(unrecognized_services))
        logged_service_warning = True

      ordered_services.append(unrecognized_services)
      for parallel_group in ordered_services:
        running = [process for process in parallel_group
                   if services[process] != MonitStates.PENDING]
        if running:
          break
      else:
        continue

      @retry_coroutine(max_retries=5, retry_on_exception=DEFAULT_RETRIES)
      def stop_with_retries(process_name):
        logger.debug('Sending command to stop "{}"..'.format(process_name))
        yield monit_operator.send_command(process_name, 'stop')

      yield [stop_with_retries(process) for process in running]
    except StopIteration:
      # If all running services are pending, just wait until they are not.
      pass

    yield gen.sleep(min(0.3 * len(running), 5))


def main():
  """ Main function which terminates all appscale processes. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  # Parse command line arguments
  parser = argparse.ArgumentParser(description='A stop services command')
  parser.add_argument('--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()
  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  # Like synchronous HTTPClient, create separate IOLoop for sync code
  io_loop = ioloop.IOLoop(make_current=False)
  try:
    return io_loop.run_sync(lambda: main_async())
  finally:
    io_loop.close()
