""" Top level exceptions for search from AppScale. """

class SearchException(Exception):
  """ Top level exception for search. """
  pass

class InternalError(SearchException):
  """ Internal error exception. """
  pass

class NotConfiguredError(SearchException):
  """ Search is not configured. """
  pass

