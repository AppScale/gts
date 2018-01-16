from appscale.common.service_stats import matchers


class Metric(object):
  def compute(self, requests):
    raise NotImplemented


class Avg(Metric):
  def __init__(self, field):
    self._field_name = field

  def compute(self, requests):
    if not requests:
      return None
    return sum(getattr(r, self._field_name) for r in requests) / len(requests)


class Max(Metric):
  def __init__(self, field):
    self._field_name = field

  def compute(self, requests):
    if not requests:
      return None
    return max(getattr(r, self._field_name) for r in requests)


class Min(Metric):
  def __init__(self, field):
    self._field_name = field

  def compute(self, requests):
    if not requests:
      return None
    return min(getattr(r, self._field_name) for r in requests)


class CountOf(Metric):
  def __init__(self, matcher):
    super(CountOf, self).__init__()
    self._matcher = matcher

  def compute(self, requests):
    if self._matcher is matchers.ANY:
      return len(requests)
    return sum(1 for request in requests if self._matcher.matches(request))


