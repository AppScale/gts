""" A cache of recently created operations. """


class OperationsCache(dict):
  """ A cache of recently created operations """
  def __init__(self, size=256):
    """ Creates new OperationsCache.

    Args:
      size: An integer specifying the maximum size of the cache.
    """
    super(OperationsCache, self).__init__()
    self.operations_list = []
    self.max_size = size

  def __setitem__(self, key, value):
    """ Adds a new operation to the cache.

    Args:
      key: A string specifying the operation ID.
      value: A dictionary containing the operation details.
    """
    super(OperationsCache, self).__setitem__(key, value)
    self.operations_list.append(key)
    to_remove = len(self) - self.max_size
    for _ in range(to_remove):
      old_key = self.operations_list.pop(0)
      del self[old_key]
