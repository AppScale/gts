""" Provides a service which does backup/recovery on each datastore node. """
import logging

import backup_recovery

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  LOGGER = logging.getLogger(__name__)
  BR_SERVICE = backup_recovery.BRService()
  try:
    BR_SERVICE.start()
  except Exception, exception:
    LOGGER.warning("An exception slipped through:")
    LOGGER.exception(exception)
    LOGGER.warning("Exiting service.")
