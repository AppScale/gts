#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale)


class AppControllerException(Exception):
  """A special Exception class that should be thrown if the user tries to
  interact with an AppController, but receives a failure message back from
  that AppController.
  """
  pass


class AppEngineConfigException(Exception):
  """A special Exception class that should be thrown if there is a problem
  with the user's App Engine application (e.g., it has no app.yaml or web.xml,
  or has a malformed appid).
  """
  pass


class AppScaleException(Exception):
  """A special Exception class that should be thrown if the user tries to
  interact with an AppScale deployment, but it's not in the expected
  state. Examples of this include scenarios when AppScale configuration
  files aren't written locally, or if we expect AppScale to be running
  and it isn't.
  """
  pass


class AppScalefileException(Exception):
  """A special Exception class that should be thrown if the user tries to
  run an appscale command that interacts with an AppScalefile and the
  file is either malformed or in an unexpected state.
  """
  pass


class BadConfigurationException(Exception):
  """A special Exception class that should be thrown if the user attempts
  to execute a command with malformed arguments.
  """
  pass


class ShellException(Exception):
  """A special Exception class that should be thrown if a shell command is
  executed and has a non-zero return value.
  """
  pass


class TimeoutException(Exception):
  """A special Exception class that should be thrown if a function is executed
  but takes longer to run than the caller expects.
  """
  pass


class UsageException(Exception):
  """A special Exception class that should be thrown if the user attempts
  to run the 'help' directive, which reports on the usage of this tool.
  """
  pass
