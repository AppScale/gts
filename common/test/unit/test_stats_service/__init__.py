class RequestInfo(object):
  __slots__ = ["app", "service", "version", "method", "resource",
               "status", "response_size"]

  def __init__(self, **fields_dict):
    for field in self.__slots__:
      value = fields_dict.get(field)
      setattr(self, field, value)
