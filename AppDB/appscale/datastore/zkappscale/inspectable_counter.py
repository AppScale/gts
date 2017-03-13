""" A ZooKeeper counter that returns the new value when incremented. """

from kazoo.exceptions import BadVersionError
from kazoo.retry import ForceRetryError


class InspectableCounter(object):
  """ A ZooKeeper counter that returns the new value when incremented.

  This is based off the Kazoo Counter recipe.
  """
  def __init__(self, client, path, default=0):
    """ Create an InspectableCounter.

    Args:
      client: A KazooClient object.
      path: A string containing the ZooKeeper path to use for the counter.
      default: An integer containing the default counter value.
    """
    self.client = client
    self.path = path
    self.default = default
    self.default_type = type(default)
    self._ensured_path = False

  def _ensure_node(self):
    """ Make sure the ZooKeeper path that stores the counter value exists. """
    if not self._ensured_path:
      self.client.ensure_path(self.path)
      self._ensured_path = True

  def _value(self):
    """ Retrieve the current value and node version from ZooKeeper.

    Returns:
      A tuple consisting of the current count and node version.
    """
    self._ensure_node()
    old, stat = self.client.get(self.path)
    old = old.decode('ascii') if old != b'' else self.default
    version = stat.version
    data = self.default_type(old)
    return data, version

  @property
  def value(self):
    """ Retrieve the current value from ZooKeeper.

    Returns:
      An integer containing the current count.
    """
    return self._value()[0]

  def _change(self, value):
    """ Add a value to the counter.

    Args:
      value: An integer specifying how much to add.
    Returns:
      An integer indicating the new count after the change.
    """
    if not isinstance(value, self.default_type):
      raise TypeError('Invalid type for value change')

    return self.client.retry(self._inner_change, value)

  def _inner_change(self, value):
    """ Add a value to the counter.

    Args:
      value: An integer specifying how much to add.
    Returns:
      An integer indicating the new count after the change.
    """
    data, version = self._value()
    new_value = data + value
    new_data = repr(new_value).encode('ascii')
    try:
      self.client.set(self.path, new_data, version=version)
      return new_value
    except BadVersionError:
      raise ForceRetryError()

  def __add__(self, value):
    """ Add value to counter.

    Returns:
      An integer indicating the new count after the change.
    """
    return self._change(value)

  def __sub__(self, value):
    """ Subtract value from counter.

    Returns:
      An integer indicating the new count after the change.
    """
    return self._change(-value)
