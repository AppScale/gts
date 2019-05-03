""" A cache of recently created operations. """


class OperationIdsCache(dict):
  """ A cache of recently created operations """
  def __init__(self, size=256):
    """ Creates new OperationsCache.

    Args:
      size: An integer specifying the maximum size of the cache.
    """
    super(OperationIdsCache, self).__init__()
    self.reservations_list = []
    self.max_size = size

  def __setitem__(self, key, value):
    """ Adds a new operation to the cache.

    Args:
      key: A string specifying the operation ID.
      value: A dictionary containing the operation details.
    """
    super(OperationIdsCache, self).__setitem__(key, value)
    self.reservations_list.append(key)
    to_remove = len(self) - self.max_size
    for _ in range(to_remove):
      old_key = self.reservations_list.pop(0)
      del self[old_key]
