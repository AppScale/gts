"""
A collection of common utility functions which can be used by any
module within the AppDB backup implementation.
"""

class ExitCodes(object):
  """ Shell exit codes. """
  SUCCESS = 0


class ServiceException(Exception):
  pass
