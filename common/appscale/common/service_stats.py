from datetime import datetime

import time

import logging
from future.utils import viewitems

class Measure(object):
  def measure(self, values_sequence):
    raise NotImplemented


class Categorizer(object):
  def split(self, finished_requests):
    raise NotImplemented


class UnknownRequestField(AttributeError):
  pass


class FinishingUnknownRequest(Exception):
  pass


DEFAULT_HISTORY_SIZE = 1000
DEFAULT_MAX_REQUEST_AGE = 60*60*2  # Force clean requests older than 2h


DEFAULT_REQUEST_FIELDS = [
  "app", "module", "version", "method", "resource",
  "status", "response_size", "failure"
]


DEFAULT_STATS_MAP = {
  "all": (),
  "apps": (1, None),  # TODO
  "versions": None,  # TODO
  "resources":
}


class ServiceStats(object):

  AUTOCLEAN_INTERVAL = 60*60*4
  BOOKED_REQUEST_FIELDS = ["start_time", "end_time", "latency"]
  REQUIRED_REQUEST_FIELDS = ["method", "status", "failure", "resource"]

  def __init__(self, history_size=DEFAULT_HISTORY_SIZE,
               force_clean_after=DEFAULT_MAX_REQUEST_AGE,
               lock_context_manager=None,
               custom_request_fields=None, **kwargs):
    # Determine request info model
    request_fields = kwargs.pop("request_fields", DEFAULT_REQUEST_FIELDS)
    if custom_request_fields:
      request_fields = request_fields + custom_request_fields


    class RequestInfo(object):
      __slots__ = request_fields + self.BOOKED_REQUEST_FIELDS

      def __init__(self, fields_dict):
        self.update(fields_dict)

      def update(self, fields_dict):
        for field, value in viewitems(fields_dict):
          try:
            setattr(self, field, value)
          except AttributeError as e:
            raise UnknownRequestField(str(e))

    self._request_info_class = RequestInfo

    # Initialize statistics configuration
    self._stats_map = {}

    # Initialize requests accumulation properties
    self._lock = lock_context_manager
    self._last_request_no = 0
    self._current_requests = {}  # {request_no: RequestInfo()}
    self._finished_requests = []  # [RequestInfo()]
    self._history_size = history_size
    self._force_clean_after = force_clean_after
    self._last_autoclean_time = time.mktime(datetime.now().timetuple())

  def start_request(self, request_info_dict):
    with self._lock:
      now = time.mktime(datetime.now().timetuple())
      new_request = self._request_info_class(request_info_dict)
      new_request.start_time = now
      self._last_request_no += 1
      self._current_requests[self._last_request_no] = new_request

      if now - self._last_autoclean_time > self.AUTOCLEAN_INTERVAL:
        # Avoid memory leak even if client sometimes don't finish requests
        self._clean_outdated()

      return self._last_request_no

  def finalize_request(self, request_no, new_info_dict):
    with self._lock:
      now = time.mktime(datetime.now().timetuple())
      request_info = self._current_requests.pop(request_no, None)
      if not request_info:
        raise FinishingUnknownRequest("Couldn't finalize unknown request #{}"
                                      .format(request_no))
      request_info.update(new_info_dict)
      request_info.end_time = now
      request_info.latency = int((now - request_info.start_time)*1000)
      self._finished_requests.append(request_info)
      if len(self._finished_requests) > self._history_size:
        self._finished_requests.pop(0)

  def _clean_outdated(self):
    now = time.mktime(datetime.now().timetuple())
    outdated = []
    for request_no, request_info in viewitems(self._current_requests):
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
    if since:
      index = None   # TODO
    else:
      index = 0
    # TODO



