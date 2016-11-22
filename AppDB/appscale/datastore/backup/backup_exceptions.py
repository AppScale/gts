""" AppScale exceptions for backup or restores. """


class BRException(Exception):
  """ Base class for backup and recovery exceptions. """
  pass


class NoKeyException(Exception):
  """ Indicates that a required key is missing. """


class AmbiguousKeyException(Exception):
  """ Indicates that there is more than one key to choose from. """
