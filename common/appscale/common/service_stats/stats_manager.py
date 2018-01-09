from datetime import datetime
import logging
import time


class UnknownRequestField(AttributeError):
  pass


class ReservedRequestField(Exception):
  pass


class ServiceStats(object):
  DEFAULT_HISTORY_SIZE = 1000

  DEFAULT_MAX_REQUEST_AGE = 60 * 60 * 2  # Force clean requests older than 2h
  AUTOCLEAN_INTERVAL = 60 * 60 * 4

  RESERVED_REQUEST_FIELDS = ["start_time", "end_time", "latency"]
  DEFAULT_REQUEST_FIELDS = [
    "app", "module", "version", "method", "resource",
    "status", "response_size"
  ]
  DEFAULT_STATS_SCHEMA = {
    "all": (),
    "apps": (1, None),  # TODO
    "versions": None,  # TODO
    "resources": None
  }

  def __init__(self, service_name, history_size=DEFAULT_HISTORY_SIZE,
               force_clean_after=DEFAULT_MAX_REQUEST_AGE,
               lock_context_manager=None,
               request_fields=DEFAULT_REQUEST_FIELDS,
               stats_schema=DEFAULT_STATS_SCHEMA):

    now = time.mktime(datetime.now().timetuple())
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

    # Initialize properties for global counters
    self._start_time = now
    # TODO global counter

    # Initialize statistics schema
    self._stats_schema = stats_schema
    # TODO schema

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
        for field in fields_dict:
          try:
            setattr(self, field, fields_dict[fields_dict])
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
      now = time.mktime(datetime.now().timetuple())
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
      now = time.mktime(datetime.now().timetuple())
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

  def _clean_outdated(self):
    """ Removes old requests which are unlikely to be finished ever as
    there were started longer than self._force_clean_after seconds ago.
    """
    now = time.mktime(datetime.now().timetuple())
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

  def get_stats(self, since=None):
    """ TODO """
    if since:
      index = None  # TODO
    else:
      index = 0
    return {
      "service_name": self._service_name,
      "running_since": self._start_time,
      "current_requests": len(self._current_requests),
      "cumulative": {
        "all": 32,  # TODO
        "by_status": {"1xx": 5},
        "by_app": {"app1": 98},
        "by_resource": {""},
        "by_custom_category": {}
      },
      "recent": {
        "avg_latency": 0.3,
        "requests": 100500,
        "4xx": 100,
        "5xx": 500,
        "by_resource": {

        }
      },

    }




