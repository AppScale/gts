class RequestMatcher(object):
  def matches(self, request_info):
    raise NotImplemented


class _AnyRequestMatcher(RequestMatcher):
  def matches(self, request_info):
    return True


class _StatusMatcher(RequestMatcher):
  def __init__(self, minimal, maximal):
    self._min = minimal
    self._max = maximal

  def matches(self, request_info):
    return self._min <= request_info.status <= self._max


ANY = _AnyRequestMatcher()
CLIENT_ERROR = _StatusMatcher(400, 499)
SERVER_ERROR = _StatusMatcher(500, 599)

