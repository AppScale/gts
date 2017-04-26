#!/usr/bin/env python

import logging
import sys

from appscale.common import monit_interface


def stop_service(service_name):
  logging.info("Stopping " + service_name)
  if not monit_interface.stop(service_name):
    logging.error("Monit was unable to stop " + service_name)
    return 1
  else:
    logging.info("Successfully stopped " + service_name)
    return 0

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 2:
    sys.exit(1)

  service_name = (str(sys.argv[1]))
  stop_service(service_name)
