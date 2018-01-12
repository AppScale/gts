class Categorizer(object):
  """
  An interface for request categorizer. Any categorizer can
  be used as a key in a metrics map (see stats_manager.py), in this case,
  specified metrics will be counted for each category
  """
  def __init__(self, categorizer_name):
    self._categorizer_name = categorizer_name

  @property
  def name(self):
    return self._categorizer_name

  def category_of(self, req_info):
    """ Lists categories which request belongs to.
    
    Args:
      req_info: an object containing request info.
    Returns:
      A string or a list of strings representing name of category.
    """
    raise NotImplemented

  def __hash__(self):
    """ Categorizer suppose to be used as a key in a metrics map,
    so __hash__ and __eq__ methods have to be implemented """
    return hash(self._categorizer_name)

  def __eq__(self, other):
    """ Categorizer suppose to be used as a key in a metrics map,
    so __hash__ and __eq__ methods have to be implemented """
    if isinstance(other, Categorizer):
      return self._categorizer_name == other._categorizer_name
    return self._categorizer_name == other


class ExactValueCategorizer(Categorizer):
  def __init__(self, categorizer_name, field_name):
    super(ExactValueCategorizer, self).__init__(categorizer_name)
    self._field_name = field_name

  def category_of(self, req_info):
    return getattr(req_info, self._field_name)


class VersionCategorizer(Categorizer):
  def category_of(self, req_info):
    return "{}.{}.{}".format(req_info.app, req_info.service, req_info.version)


class StatusCategorizer(Categorizer):
  def category_of(self, req_info):
    if 100 <= req_info.status <= 199:
      return "1xx"
    if 200 <= req_info.status <= 299:
      return "2xx"
    if 300 <= req_info.status <= 399:
      return "3xx"
    if 400 <= req_info.status <= 499:
      return "4xx"
    if 500 <= req_info.status <= 599:
      return "5xx"
    return "other_xx"
