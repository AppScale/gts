#!/usr/bin/env python
#
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../lib'))
import monit_interface

def stop_service(service_name):
  logging.info("Stopping " + service_name)
  if not monit_interface.stop(service_name):
    logging.error("Monit was unable to stop " + service_name)
    sys.exit(1)
  else:
    logging.info("Successfully stopped " + service_name)

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 2:
    sys.exit(1)

  service_name = (str(sys.argv[1]))
  stop_service(service_name)


