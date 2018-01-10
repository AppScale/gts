from collections import defaultdict
import logging
import time

from future.utils import iteritems

from appscale.common.service_stats import matchers, metrics, categorizers


class UnknownRequestField(AttributeError):
  pass


class ReservedRequestField(Exception):
  pass


DEFAULT_REQUEST_FIELDS = [
  "app", "module", "version", "method", "resource",
  "status", "response_size"
]

DEFAULT_CUMULATIVE_COUNTERS = {
  "all": matchers.ANY,
  "4xx": matchers.CLIENT_ERRORS,
  "5xx": matchers.SERVER_ERRORS,
  categorizers.ExactValueCategorizer("by_app", field_name="app"): {
    "all": matchers.ANY,
    "4xx": matchers.CLIENT_ERRORS,
    "5xx": matchers.SERVER_ERRORS
  }
}
# This counters config corresponds to the following output:
# {
#   "from": 1515595829,
#   "to": 1515735126,
#   "all": 27365,
#   "4xx": 97,
#   "5xx": 15,
#   "by_app": {
#     "guestbook": {"all": 18321, "4xx": 90, "5xx": 13},
#     "validity": {"all": 9044, "4xx": 7, "5xx": 2}
#   }
# }

DEFAULT_METRICS_MAP = {
  "all": metrics.CountOf(matchers.ANY),
  "4xx": metrics.CountOf(matchers.CLIENT_ERRORS),
  "5xx": metrics.CountOf(matchers.SERVER_ERRORS),
  "avg_latency": metrics.AvgLatency(),
  categorizers.ExactValueCategorizer("by_app", field_name="app"):{
    categorizers.ExactValueCategorizer("by_resource", field_name="resource"): {
      "all": metrics.CountOf(matchers.ANY),
      "4xx": metrics.CountOf(matchers.CLIENT_ERRORS),
      "5xx": metrics.CountOf(matchers.SERVER_ERRORS),
      "avg_latency": metrics.AvgLatency(),
    }
  }
}
# This metrics map corresponds to following output:
# {
#   "from": 1515699718,
#   "to": 1515735126,
#   "all": 1225,
#   "4xx": 11,
#   "5xx": 3,
#   "avg_latency": 325,
#   "by_app": {
#     "guestbook": {
#       "by_resource": {
#         "/get/user": {"all": 56, "4xx": 11, "5xx": 3, "avg_latency": 321},
#         "/": {"all": 300, "4xx": 0, "5xx": 0, "avg_latency": 68}
#       }
#     },
#     "validity": {
#       "by_resource": {
#         "/wait": {"all": 69, "4xx": 0, "5xx": 0, "avg_latency": 5021},
#         "/version": {"all": 800, "4xx": 0, "5xx": 0, "avg_latency": 35}
#       }
#     }
#   }
# }


class _DummyLock(object):
  def __enter__(self):
    pass
  def __exit__(self, exc_type, exc_val, exc_tb):
    pass


NO_LOCK = _DummyLock()


class ServiceStats(object):
  DEFAULT_HISTORY_SIZE = 1000

  DEFAULT_MAX_REQUEST_AGE = 60 * 60 * 2  # Force clean requests older than 2h
  AUTOCLEAN_INTERVAL = 60 * 60 * 4

  RESERVED_REQUEST_FIELDS = ["start_time", "end_time", "latency"]

  def __init__(self, service_name, history_size=DEFAULT_HISTORY_SIZE,
               force_clean_after=DEFAULT_MAX_REQUEST_AGE,
               lock_context_manager=NO_LOCK,
               request_fields=DEFAULT_REQUEST_FIELDS,
               cumulative_counters=DEFAULT_CUMULATIVE_COUNTERS,
               metrics_for_recent=DEFAULT_METRICS_MAP):

    now = _now()
    self._service_name = service_name

    self._request_info_class = self._generate_request_model(request_fields)

    # Initialize properties for tracking latest N requests
    self._lock = lock_context_manager
    self._last_request_no = 0
    self._current_requests = {}  # {request_no: RequestInfo()}
    self._finished_requests = []  # [RequestInfo()] up

    # Configure parameters limiting memory usage
    self._history_size = history_size
    self._force_clean_after = force_clean_after
    self._last_autoclean_time = now

    # Configure cumulative counters
    self._start_time = now
    self._cumulative_counters_config = cumulative_counters
    self._cumulative_counters = defaultdict(int)

    # Configure metrics for recent requests
    self._metrics_for_recent_config = metrics_for_recent

  @property
  def service_name(self):
    return self._service_name

  @property
  def current_requests(self):
    return len(self._current_requests)

  def _generate_request_model(self, request_fields):
    """ Defines class describing request information.

    Args:
      request_fields: a list of string names of fields.
    Returns:
      a python class having request fields as instance attributes.
    """
    for request_field in self.RESERVED_REQUEST_FIELDS:
      if request_field in request_fields:
        raise ReservedRequestField(
          "custom_request_fields or request_fields list contains "
          "reserved name '{}'", format(request_field))

    class RequestInfo(object):
      __slots__ = set(request_fields + self.RESERVED_REQUEST_FIELDS)

      def __init__(self, fields_dict):
        # Make sure that new object has all request fields
        for field in self.__slots__:
          setattr(self, field, None)
        self.update(fields_dict)

      def update(self, fields_dict):
        for field, value in iteritems(fields_dict):
          try:
            setattr(self, field, value)
          except AttributeError as e:
            raise UnknownRequestField(str(e))

    return RequestInfo

  def start_request(self, request_info_dict):
    """ Adds request to a collection of currently running requests.

    Args:
      request_info_dict: a dictionary containing initial request info.
    Returns:
      an internal request ID which should be used for finishing request.
    """
    with self._lock:
      now = _now()
      # Instantiate a request_info object and fill its start_time
      new_request = self._request_info_class(request_info_dict)
      new_request.start_time = now
      # Add currently running request
      self._last_request_no += 1
      self._current_requests[self._last_request_no] = new_request

      if now - self._last_autoclean_time > self.AUTOCLEAN_INTERVAL:
        # Avoid memory leak even if client sometimes don't finish requests
        self._clean_outdated()

      return self._last_request_no

  def finalize_request(self, request_no, new_info_dict):
    """ Finalizes previously started request. Moves request from currently
    running to finished.

    Args:
      request_no: an internal request ID provided by start_request method.
      new_info_dict: a dictionary containing info about request result.
    """
    with self._lock:
      now = _now()
      # Find request with the specified request_no
      request_info = self._current_requests.pop(request_no, None)
      if not request_info:
        logging.error("Couldn't finalize request #{} as it wasn't started "
                      "or it was started longer than {}s ago"
                      .format(request_no, self._force_clean_after))
        return
      # Fill request_info object with a new information
      request_info.update(new_info_dict)
      request_info.end_time = now
      request_info.latency = int((now - request_info.start_time) * 1000)
      # Add finished request to circular list of finished requests
      self._finished_requests.append(request_info)
      if len(self._finished_requests) > self._history_size:
        self._finished_requests.pop(0)
      # Update cumulative counters
      for counter_name, matcher in iteritems(self._cumulative_counters_config):
        if matcher.matches(request_info):
          self._cumulative_counters[counter_name] += 1
          # TODO

  def _clean_outdated(self):
    """ Removes old requests which are unlikely to be finished ever as
    there were started longer than self._force_clean_after seconds ago.
    """
    now = _now()
    outdated = []
    for request_no, request_info in self._current_requests.items():
      if now - request_info.start_time > self._force_clean_after:
        outdated.append(request_no)
    if outdated:
      logging.error("There are {} requests which were started but haven't "
                    "been finished in more than {}s."
                    .format(len(outdated), self._force_clean_after))
      for request_no in outdated:
        del self._current_requests[request_no]
    self._last_autoclean_time = now

  def get_recent(self, for_last_seconds=None):
    cursor = _now() - for_last_seconds if for_last_seconds else None
    requests = self._get_requests(since=cursor)
    # TODO

  def scroll_recent(self, cursor=None):
    """  """
    requests = self._get_requests(since=cursor)

    return {
      "cumulative": {
        "from": self._start_time,
        "to": _now(),
        "all": 32,  # TODO
        "4xx": 100,
        "5xx": 500,
        "by_status": {"1xx": 5},
        "by_app": {"app1": 98},
        "by_resource": {""},
        "by_custom_category": {}
      }
    }

  def _render_recent(self, requests):
    # TODO
    return {
      "from": requests[0].end_time,
      "to": requests[-1].end_time,
      "avg_latency": 0.3,
      "requests": 100500,
      "4xx": 100,
      "5xx": 500,
      "by_resource": {
    }

  def _get_requests(self, since=None):
    if since is None:
      return self._finished_requests
    # Find the first element newer than 'since' using bisect
    left, right = 0, len(self._finished_requests)
    while left < right:
      middle = (left + right) // 2
      if since < self._finished_requests[middle].end_time:
        right = middle
      else:
        left = middle + 1
    return self._finished_requests[left:]


def _now():
  return int(time.time() * 1000)




