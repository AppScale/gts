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


class InvalidNameException(SearchException):
  """" Name attribute is not valid. """
  pass


class InvalidFieldException(SearchException):
  """" Invalid Field. """
  pass

class UnknownFieldTypeException(SearchException):
  """ Field type is not defined """
  pass