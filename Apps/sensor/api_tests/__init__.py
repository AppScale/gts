""" An abstract base class for running tests. """
import abc

class ApiTestBase(object):
  """ An abstract class for tests to inherit. """
  __metaclass__ = abc.ABCMeta

  def __init__(self, uuid_tag):
    """ Shared constructor. """
    if not isinstance(uuid_tag, str):
      raise TypeError("Expected a str")  
    self.uuid_tag = uuid_tag

  @abc.abstractmethod
  def run(self):
    """ Run the given test and return a json string with results. """
    return

  @abc.abstractmethod
  def cleanup(self):
    """ Clean up any left over state. """
    return
