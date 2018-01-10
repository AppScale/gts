from appscale.common.service_stats import matchers


class Metric(object):
  def compute(self, requests):
    raise NotImplemented


class AvgLatency(Metric):
  def compute(self, requests):
    if not requests:
      return None
    return sum(request.latency for request in requests) * 1000 / len(requests)


class AvgResponseSize(Metric):
  def compute(self, requests):
    if not requests:
      return None
    return sum(request.response_size for request in requests) / len(requests)


class CountOf(Metric):
  def __init__(self, matcher):
    super(CountOf, self).__init__()
    self._matcher = matcher

  def compute(self, requests):
    if self._matcher is matchers.ANY:
      return len(requests)
    return sum(1 for request in requests if self._matcher.matches(request))


