"""
A collection of common utility functions which can be used by any
module within the AppDB backup implementation.
"""

class ExitCodes(object):
  """ Shell exit codes. """
  SUCCESS = 0


class MonitStates(object):
  RUNNING = 'Running'
  UNMONITORED = 'Not monitored'


class ServiceException(Exception):
  pass


def monit_status(summary, service):
  """ Retrieves the status of a Monit service.

  Args:
    summary: A string containing the output of 'monit summary'.
    service: A string containing the name of a service.
  Raises:
    ServiceException if summary does not include service.
  """
  for line in summary.split('\n'):
    if service in line:
      return ' '.join(line.split()[2:])
  raise ServiceException('Unable to find Monit entry for {}'.format(service))
