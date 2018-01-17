from collections import defaultdict
import logging
import time

import copy
from future.utils import iteritems

from appscale.common.service_stats import matchers, metrics, categorizers


class UnknownRequestField(AttributeError):
  pass


class ReservedRequestField(Exception):
  pass


DEFAULT_REQUEST_FIELDS = [
  "app", "service", "version", "method", "resource",
  "status", "response_size"
]

DEFAULT_CUMULATIVE_COUNTERS = {
  "all": matchers.ANY,
  "4xx": matchers.CLIENT_ERROR,
  "5xx": matchers.SERVER_ERROR,
  categorizers.ExactValueCategorizer("by_app", field="app"): {
    "all": matchers.ANY,
    "4xx": matchers.CLIENT_ERROR,
    "5xx": matchers.SERVER_ERROR
  }
}
# This counters config corresponds to the following output:
# {
#   "from": 1515595829789,
#   "to": 1515735126987,
#   "all": 27365,
#   "4xx": 97,
#   "5xx": 15,
#   "by_app": {
#     "guestbook": {"all": 18321, "4xx": 90, "5xx": 13},
#     "validity": {"all": 9044, "4xx": 7, "5xx": 2}
#   }
# }

SINGLE_APP_METRICS_MAP = {
  "all": metrics.CountOf(matchers.ANY),
  "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
  "5xx": metrics.CountOf(matchers.SERVER_ERROR),
  "avg_latency": metrics.Avg("latency")
}
# This metrics map corresponds to following output:
# {
#   "from": 1515699718987,
#   "to": 1515735126789,
#   "all": 1225,
#   "4xx": 11,
#   "5xx": 3,
#   "avg_latency": 325
# }

PER_APP_DETAILED_METRICS_MAP = {
  "all": metrics.CountOf(matchers.ANY),
  "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
  "5xx": metrics.CountOf(matchers.SERVER_ERROR),
  "avg_latency": metrics.Avg("latency"),
  categorizers.ExactValueCategorizer("by_app", field="app"): {
    categorizers.ExactValueCategorizer("by_resource", field="resource"): {
      "all": metrics.CountOf(matchers.ANY),
      "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
      "5xx": metrics.CountOf(matchers.SERVER_ERROR),
      "avg_latency": metrics.Avg("latency")
    },
    "all": metrics.CountOf(matchers.ANY),
    "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
    "5xx": metrics.CountOf(matchers.SERVER_ERROR),
    "avg_latency": metrics.Avg("latency")
  }
}
# This metrics map corresponds to following output:
# {
#   "from": 1515699718987,
#   "to": 1515735126789,
#   "all": 1225,
#   "4xx": 11,
#   "5xx": 3,
#   "avg_latency": 325,
#   "by_app": {
#     "guestbook": {
#       "by_resource": {
#         "/get/user": {"all": 56, "4xx": 11, "5xx": 3, "avg_latency": 321},
#         "/": {"all": 300, "4xx": 0, "5xx": 0, "avg_latency": 68}
#       },
#       "all": 356,
#       "4xx": 11,
#       "5xx": 3,
#       "avg_latency": 107
#     },
#     "validity": {
#       "by_resource": {
#         "/wait": {"all": 69, "4xx": 0, "5xx": 0, "avg_latency": 5021},
#         "/version": {"all": 800, "4xx": 0, "5xx": 0, "avg_latency": 35}
#       },
#       "all": 869,
#       "4xx": 0,
#       "5xx": 0,
#       "avg_latency": 430
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
  """
  Collects stats about requests handled by a service.
  Service should report any request it starts working on using:
    start_request(request_info_dict)
  After finishing request service should call:
    finalize_request(request_no, result_info_dict)
  (its recommended to do this in finally section of try-except statement).
   
  To retrieve cumulative stats call:
    get_cumulative_stats()
  To retrieve statistics for recent requests use one of:
    get_recent(age)
    scroll_recent(cursor)
  """

  DEFAULT_HISTORY_SIZE = 1000

  DEFAULT_MAX_REQUEST_AGE = 60 * 60 * 2  # Force clean requests older than 2h
  AUTOCLEAN_INTERVAL = 60 * 60 * 4

  RESERVED_REQUEST_FIELDS = ["start_time", "end_time", "latency"]

  def __init__(self, service_name, history_size=DEFAULT_HISTORY_SIZE,
               force_clean_after=DEFAULT_MAX_REQUEST_AGE,
               lock_context_manager=NO_LOCK,
               request_fields=DEFAULT_REQUEST_FIELDS,
               cumulative_counters=DEFAULT_CUMULATIVE_COUNTERS,
               default_metrics_for_recent=SINGLE_APP_METRICS_MAP):
    """ Initialises an instance of ServiceStats.
    
    Args:
      service_name: a str representing name of service.
      history_size: a number of recent requests to store.
      force_clean_after: seconds to wait before removing started requests.
      lock_context_manager: an instance of context manager to use for managing
        concurrent execution of requests.
      request_fields: a list of request property names.
      cumulative_counters: a dictionary describing cumulative counters config.
      default_metrics_for_recent: a dictionary containing metrics 
        which should be computed for recent requests by default.
    """

    now = _now()
    self._service_name = service_name
    self._request_info_class = self.generate_request_model(request_fields)

    # Initialize properties for tracking latest N requests
    self._lock = lock_context_manager
    self._last_request_no = 0
    self._current_requests = {}  # {request_no: RequestInfo()}
    self._finished_requests = []  # circular list containing recent N requests

    # Configure parameters limiting memory usage
    self._history_size = history_size
    self._force_clean_after = force_clean_after
    self._last_autoclean_time = now

    # Configure cumulative counters
    self._start_time = now
    self._cumulative_counters_config = cumulative_counters
    self._cumulative_counters = {}
    _fill_zero_counters_dict(cumulative_counters, self._cumulative_counters)

    # Configure metrics for recent requests
    self._metrics_for_recent_config = default_metrics_for_recent

  @property
  def service_name(self):
    """ Name of service """
    return self._service_name

  @property
  def current_requests(self):
    """ Number of currently running requests """
    return len(self._current_requests)

  @staticmethod
  def generate_request_model(request_fields):
    """ Defines class describing request information.

    Args:
      request_fields: a list of string names of fields.
    Returns:
      a python class having request fields as instance attributes.
    """
    for request_field in ServiceStats.RESERVED_REQUEST_FIELDS:
      if request_field in request_fields:
        raise ReservedRequestField(
          "custom_request_fields or request_fields list contains "
          "reserved name '{}'", format(request_field))

    class RequestInfo(object):
      __slots__ = set(request_fields + ServiceStats.RESERVED_REQUEST_FIELDS)

      def __init__(self, **fields_dict):
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

      def __getattr__(self, field):
        try:
          object.__getattribute__(self, field)
        except AttributeError as e:
          raise UnknownRequestField(str(e))

    return RequestInfo

  def start_request(self, **request_info_dict):
    """ Adds request to a collection of currently running requests.

    Args:
      request_info_dict: a dictionary containing initial request info.
    Returns:
      an internal request ID which should be used for finishing request.
    """
    with self._lock:
      now = _now()
      # Instantiate a request_info object and fill its start_time
      new_request = self._request_info_class(**request_info_dict)
      new_request.start_time = now
      # Add currently running request
      self._last_request_no += 1
      self._current_requests[self._last_request_no] = new_request

      if now - self._last_autoclean_time > self.AUTOCLEAN_INTERVAL:
        # Avoid memory leak even if client sometimes don't finish requests
        self._clean_outdated()

      return self._last_request_no

  def finalize_request(self, request_no, **new_info_dict):
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
      request_info.latency = now - request_info.start_time
      # Add finished request to circular list of finished requests
      self._finished_requests.append(request_info)
      if len(self._finished_requests) > self._history_size:
        self._finished_requests.pop(0)
      # Update cumulative counters
      self._increment_counters(self._cumulative_counters_config,
                               self._cumulative_counters, request_info)

  def _increment_counters(self, counters_config, counters_dict, request_info):
    for counter_pair in iteritems(counters_config):
      # Counters config can contain following types of items:
      #  - str->Matcher
      #  - Categorizer->Matcher
      #  - Categorizer->nested config with the same structure

      if isinstance(counter_pair[1], matchers.RequestMatcher):
        # Stop as soon as possible if we know that matcher doesn't match
        matcher = counter_pair[1]
        if not matcher.matches(request_info):
          continue

      if isinstance(counter_pair[0], str):
        # Increment single counter if key is str
        counter_name = counter_pair[0]
        counters_dict[counter_name] += 1
        continue

      # counter_pair[0] is instance of categorizers.Categorizer
      categorizer = counter_pair[0]
      category = categorizer.category_of(request_info)
      category_counters = _get_nested_dict(counters_dict, categorizer.name)
      if isinstance(counter_pair[1], dict):
        # Update nested counters
        nested_config = counter_pair[1]
        nested_counters = _get_nested_dict(category_counters, category, nested_config)
        self._increment_counters(nested_config, nested_counters, request_info)
      else:
        # Update category counter
        category_counters[category] = category_counters.get(category, 0) + 1

  def get_cumulative_counters(self):
    """
    Returns:
      A dictionary containing current value of cumulative counters.
    """
    counter_stats = copy.deepcopy(self._cumulative_counters)
    counter_stats["from"] = self._start_time
    counter_stats["to"] = _now()
    return counter_stats

  def get_recent(self, for_last_milliseconds=None, metrics_map=None):
    """ Provides value of metrics for recent requests which were finished
    not earlier than for_last_seconds seconds ago.
    
    Args:
      for_last_milliseconds: a number of seconds.
      metrics_map: a dict describing metrics config.
    Returns:
      a dictionary containing value of metrics for recent requests.
    """
    cursor = (_now() - for_last_milliseconds) if for_last_milliseconds else None
    return self.scroll_recent(cursor, metrics_map)

  def scroll_recent(self, cursor=None, metrics_map=None):
    """ Provides value of metrics for recent requests which were finished
    after specified timestamp (cursor).
    
    Args:
      cursor: a unix timestamp (in ms).
      metrics_map: a dict describing metrics config.
    Returns:
      a dictionary containing value of metrics for recent requests.
    """
    requests = self._get_requests(since=cursor)
    if not metrics_map:
      metrics_map = self._metrics_for_recent_config
    stats = self._render_recent(metrics_map, requests)
    if not requests:
      now = _now()
      stats["from"] = now
      stats["to"] = now
    else:
      stats["from"] = requests[0].end_time
      stats["to"] = requests[-1].end_time
    return stats

  def _render_recent(self, metrics_config, requests):
    """ Computes configured metrics according to metrics_config for requests.
    
    Args:
      metrics_config: a dictionary describing what metrics should be computed.
      requests: a list of requests to compute metrics for.
    Returns:
      a dictionary containing computed metrics.
    """
    stats_dict = {}
    for metric_pair in iteritems(metrics_config):
      # Metrics config can contain following types of items:
      #  - str->Metric
      #  - Categorizer->Metric
      #  - Categorizer->nested config with the same structure

      if isinstance(metric_pair[0], str):
        # Compute single metric if key is str
        metric_name = metric_pair[0]
        metric = metric_pair[1]
        stats_dict[metric_name] = metric.compute(requests)
        continue

      # metric_pair[0] is instance of categorizers.Categorizer
      categorizer = metric_pair[0]
      stats_dict[categorizer.name] = categories_stats = {}

      # Grouping requests by category
      grouped_by_category = defaultdict(list)
      for request_info in requests:
        category = categorizer.category_of(request_info)
        grouped_by_category[category].append(request_info)

      if isinstance(metric_pair[1], metrics.Metric):
        # Compute single metric for each category
        metric = metric_pair[1]
        for category, requests_group in iteritems(grouped_by_category):
          categories_stats[category] = metric.compute(requests_group)
      else:
        # Render nested stats for each category
        nested_config = metric_pair[1]
        for category, requests_group in iteritems(grouped_by_category):
          categories_stats[category] = self._render_recent(
            nested_config, requests_group
          )
    return stats_dict

  def _get_requests(self, since=None):
    """ Selects requests which were finished since specified timestamp (in ms).
    
    Args:
      since: a unix timestamp in ms.
    Returns:
      a list of requests finished since specified timestamp.
    """
    if since is None:
      return self._finished_requests
    # Find the first element newer than 'since' using bisect
    left, right = 0, len(self._finished_requests)
    while left < right:
      middle = (left + right) // 2
      if since <= self._finished_requests[middle].end_time:
        right = middle
      else:
        left = middle + 1
    result = self._finished_requests[left:]
    return result

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


def _now():
  """
  Returns:
    a unix timestamp in milliseconds.
  """
  return int(time.time() * 1000)


def _get_nested_dict(dictionary, key, nested_config=None):
  """ A util function for getting (and putting if missed) nested dictionary.
  
  Args:
    dictionary: an instance of dict. 
    key: a key.
    nested_config: a dictionary containing counters config.
      It's used for initialization of new counters dict.
  Returns:
    a dictionary got by key (newly created dict if it was missed). 
  """
  if key not in dictionary:
    nested = {}
    if nested_config:
      _fill_zero_counters_dict(nested_config, nested)
    dictionary[key] = nested
    return nested
  return dictionary[key]


def _fill_zero_counters_dict(counters_config, counters_dict):
  """ A util function for filling counters dict with all counters set to 0.
  
  Args: 
    counters_config: a dict containing cumulative counters configuration.
    counters_dict: an empty dict to fill with zero counters.
  Returns:
    a filled dictionary with zero counters.
  """
  for counter_pair in iteritems(counters_config):
    # Counters config can contain following types of items:
    #  - str->Matcher
    #  - Categorizer->Matcher
    #  - Categorizer->nested config with the same structure
    if isinstance(counter_pair[0], str):
      # Increment single counter if key is str
      counter_name = counter_pair[0]
      counters_dict[counter_name] = 0
    else:
      # counter_pair[0] is instance of categorizers.Categorizer
      categorizer = counter_pair[0]
      counters_dict[categorizer.name] = {}
  return counters_dict

