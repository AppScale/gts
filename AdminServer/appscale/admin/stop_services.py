""" Tries to stop all services until they are stopped. """
import argparse
import logging
import time

from appscale.common import service_helper
from appscale.common.constants import LOG_FORMAT
from appscale.common.retrying import retry

logger = logging.getLogger(__name__)


def start_service():
  """ Starts a service. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to start')
  args = parser.parse_args()

  service_helper.start(args.service)


def stop_service():
  """ Stops a service. """
  parser = argparse.ArgumentParser()
  parser.add_argument('service', help='The service to stop')
  args = parser.parse_args()

  service_helper.stop(args.service)


def stop_services():
  """ Tries to stop all appscale services until they are stopped. """
  @retry(max_retries=3)
  def stop_with_retries():
    logger.debug('Stopping AppScale services')
    service_helper.start('appscale-down.target', enable=False)

  logger.info('Waiting for services to stop')
  stop_requested = False
  original_services_count = None
  stopped_count = 0
  while True:
    services = service_helper.list()

    if original_services_count is None:
        original_services_count = len(services)

    running = {service: state for service, state in services.items()
               if state not in ('stopped')}

    if not running:
      logger.info('Finished stopping services')
      break

    if original_services_count - len(running) != stopped_count:
      stopped_count = original_services_count - len(running)
      logger.info(
        'Stopped {}/{} services'.format(stopped_count, original_services_count))

    if not stop_requested:
      stop_with_retries()
      stop_requested = True

    time.sleep(min(0.3 * len(running), 5))


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

  stop_services()
