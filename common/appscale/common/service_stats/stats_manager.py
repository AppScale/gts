from collections import defaultdict
import logging
import time

import copy
from future.utils import iteritems

from appscale.common.service_stats import samples


class UnknownRequestField(AttributeError):
  pass


class ReservedRequestField(Exception):
  pass


# This category doesn't appear in stats returned by ServiceStats
HIDDEN_CATEGORY = object()

DEFAULT_REQUEST_FIELDS = (
  "app", "service", "version", "method", "resource",
  "status", "response_size"
)

DEFAULT_CUMULATIVE_COUNTERS = {
  "all": samples.summarize_all,
  "4xx": samples.summarize_client_error,
  "5xx": samples.summarize_server_error,
  "latency": samples.summarize_latency,
  ("by_app", samples.categorize_by_app): {
    "all": samples.summarize_all,
    "4xx": samples.summarize_client_error,
    "5xx": samples.summarize_server_error,
    "latency": samples.summarize_latency
  }
}
# This counters config corresponds to the following output:
# {
#   "from": 1515595829789,
#   "to": 1515735126987,
#   "all": 27365,
#   "4xx": 97,
#   "5xx": 15,
#   "latency": 139297199,
#   "by_app": {
#     "guestbook": {"all": 18321, "4xx": 90, "5xx": 13, "latency": 92864799},
#     "validity": {"all": 9044, "4xx": 7, "5xx": 2, "latency": 46432400}
#   }
# }

SINGLE_APP_METRICS_MAP = {
  "all": samples.count_all,
  "4xx": samples.count_client_errors,
  "5xx": samples.count_server_errors,
  "avg_latency": samples.count_avg_latency
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
  "all": samples.count_all,
  "4xx": samples.count_client_errors,
  "5xx": samples.count_server_errors,
  "avg_latency": samples.count_avg_latency,
  ("by_app", samples.categorize_by_app): {
    ("by_resource", samples.categorize_by_resource): {
      "all": samples.count_all,
      "4xx": samples.count_client_errors,
      "5xx": samples.count_server_errors,
      "avg_latency": samples.count_avg_latency
    },
    "all": samples.count_all,
    "4xx": samples.count_client_errors,
    "5xx": samples.count_server_errors,
    "avg_latency": samples.count_avg_latency
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

  RESERVED_REQUEST_FIELDS = ["request_no", "start_time", "end_time", "latency",
                             "_service_stats", "_request_finalizer"]

  def __init__(self, service_name, history_size=DEFAULT_HISTORY_SIZE,
               force_clean_after=DEFAULT_MAX_REQUEST_AGE,
               request_fields=DEFAULT_REQUEST_FIELDS,
               cumulative_counters=DEFAULT_CUMULATIVE_COUNTERS,
               default_metrics_for_recent=SINGLE_APP_METRICS_MAP):
    """ Initialises an instance of ServiceStats.

    Args:
      service_name: a str representing name of service.
      history_size: a number of recent requests to store.
      force_clean_after: seconds to wait before removing started requests.
      request_fields: a list of request property names.
      cumulative_counters: a dictionary describing cumulative counters config.
      default_metrics_for_recent: a dictionary containing metrics
        which should be computed for recent requests by default.
    """

    now = _now()
    self._service_name = service_name
    self._request_info_class = self.generate_request_model(request_fields)

    # Initialize properties for tracking latest N requests
    self._last_request_no = 0
    self._current_requests = {}  # {request_no: RequestInfo()}
    self._finished_requests = []  # circular list containing recent N requests

    # Configure parameters limiting memory usage
    self._history_size = history_size
    self._force_clean_after = force_clean_after
    self._last_autoclean_time = now

    # Configure cumulative counters
    self._start_time = now
    self._cumulative_counters_config = _convert_config_dict(cumulative_counters)
    self._cumulative_counters = {}
    _fill_zero_counters_dict(self._cumulative_counters_config,
                             self._cumulative_counters)

    # Configure metrics for recent requests
    self._metrics_for_recent_config = \
      _convert_config_dict(default_metrics_for_recent)

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
      __slots__ = set(list(request_fields) +
                      list(ServiceStats.RESERVED_REQUEST_FIELDS))

      def __init__(self, request_no, start_time, _request_finalizer):
        self.request_no = request_no
        self.start_time = start_time
        self._request_finalizer = _request_finalizer


      @property
      def is_finalized(self):
        return self.latency is not None

      def finalize(self):
        self._request_finalizer(self.request_no)

    return RequestInfo

  def start_request(self):
    """ Adds request to a collection of currently running requests.

    Returns:
      an instance of self._request_info_class
    """
    now = _now()
    self._last_request_no += 1
    # Instantiate a request_info object and fill its start_time
    new_request = self._request_info_class(
      request_no=self._last_request_no, start_time=now,
      _request_finalizer=self._finalize_request)
    # Add currently running request
    self._current_requests[self._last_request_no] = new_request

    if now - self._last_autoclean_time > self.AUTOCLEAN_INTERVAL:
      # Avoid memory leak even if client sometimes don't finish requests
      self._clean_outdated()

    return new_request

  def _finalize_request(self, request_no):
    """ Finalizes previously started request. Moves request from currently
    running to finished.

    Args:
      request_no: an internal request ID provided by start_request method.
    """
    now = _now()
    # Find request info in current requests
    request_info = self._current_requests.pop(request_no, None)
    if not request_info:
      logging.error("Couldn't finalize request #{} as it wasn't started "
                    "or it was started longer than {}s ago"
                    .format(request_no, self._force_clean_after))
      return
    # Set end_time and latency of request
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
    for counter_name, categorizer, summarizer, nested_config in counters_config:
      # Counters config can contain following types of items:
      #  - str, None, callable(summarizer), None
      #  - str, callable(categorizer), callable(summarizer), None
      #  - str, callable(categorizer), None, nested config(tuple)

      if nested_config is None:
        # Stop as soon as possible if we know that matcher doesn't match
        value_to_add = summarizer(request_info)
        if not value_to_add:
          continue

      if categorizer is None:
        # if no categorizer => str - summarizer
        counters_dict[counter_name] += value_to_add
        continue

      # if categorizer
      category = categorizer(request_info)
      if category is HIDDEN_CATEGORY:
        continue
      category_counters = _get_nested_dict(counters_dict, counter_name)
      if nested_config is None:
        category_counters[category] = category_counters.get(category, 0) + \
                                      value_to_add
      else:
        # Update nested counters
        nested_counters = _get_nested_dict(category_counters,
                                           category, nested_config)
        self._increment_counters(nested_config, nested_counters, request_info)

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
    else:
      metrics_map = _convert_config_dict(metrics_map)
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
      metrics_config: a tuple describing what metrics should be computed.
      requests: a list of requests to compute metrics for.
    Returns:
      a dictionary containing computed metrics.
    """
    stats_dict = {}
    for metric_name, categorizer, metric, nested_config in metrics_config:
      # Metrics config can contain following types of items:
      #  - str, None, callable(metric), None
      #  - str, callable(categorizer), callable(metric), None
      #  - str, callable(categorizer), None, nested config(tuple)

      if categorizer is None:
        # Compute single metric if key is str
        stats_dict[metric_name] = metric(requests)
        continue

      stats_dict[metric_name] = categories_stats = {}

      # Grouping requests by category
      grouped_by_category = defaultdict(list)
      for request_info in requests:
        category = categorizer(request_info)
        if category is HIDDEN_CATEGORY:
          continue
        grouped_by_category[category].append(request_info)

      if nested_config is None:
        # Compute single metric for each category
        for category, requests_group in iteritems(grouped_by_category):
          categories_stats[category] = metric(requests_group)
      else:
        # Render nested stats for each category
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
    nested_config: a tuple containing counters config.
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
    counters_config: a tuple containing cumulative counters configuration.
    counters_dict: an empty dict to fill with zero counters.
  Returns:
    a filled dictionary with zero counters.
  """
  for counter_name, categorizer, _, _ in counters_config:
    # Counters config can contain following types of items:
      #  - str, None, callable(summarizer), None
      #  - str, callable(categorizer), callable(summarizer), None
      #  - str, callable(categorizer), None, nested config(tuple)
    if categorizer is None:
      # Set single counter if key is str
      counters_dict[counter_name] = 0
    else:
      # if categorizer
      counters_dict[counter_name] = {}
  return counters_dict

def _convert_config_dict(init_dict):
  """ Converts initialized by user dict to the tuples model for
  more effective use of Service Stats.

  Args:
    init_dict: dict of cumulative counters or metrics
  Returns:
    tuple of tuples in format
    (name, categorizer, summarizer/metric, nested_config)
  """
  result = []
  for key, value in iteritems(init_dict):
    if isinstance(key, str):
      # if key is string => value is summarizer or metric
      result.append((key, None, value, None))
      continue

    # otherwise key is categorizer
    name, categorizer = key
    if isinstance(value, dict):
      # value is nested config
      nested_config = _convert_config_dict(value)
      result.append((name, categorizer, None, nested_config))
    else:
      # value is summarizer or metric
      result.append((name, categorizer, value, None))

  return tuple(result)
