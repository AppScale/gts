import unittest
from time import time

from mock import patch

from appscale.common.service_stats import matchers, metrics, stats_manager, \
  categorizers


def report_request(service_stats, time_mock=None, latency=None,
                   start_kwargs=None, **finish_kwargs):
  """ Util function for quick reporting request with wanted latency.
  
  Args:
    service_stats: an instance of stats_manager.ServiceStats
    time_mock: a mock of time.time() function
    latency: an integer number representing wanted latency in ms. 
    start_kwargs: a dict containing items to use for starting request.
    finish_kwargs: a dict containing items to use for finalizing request.
  Returns:
    the latest time what was set to time mock or None if no mock provided.
  """
  if latency:
    real_time = time()
    time_mock.return_value = real_time
    request_no = service_stats.start_request(start_kwargs or {})
    latest_time_set = real_time + float(latency)/1000
    time_mock.return_value = latest_time_set
    service_stats.finalize_request(request_no, finish_kwargs)
    return latest_time_set
  else:
    request_no = service_stats.start_request(start_kwargs or {})
    service_stats.finalize_request(request_no, finish_kwargs)


class TestDefaultCumulativeCounters(unittest.TestCase):

  @patch.object(stats_manager.time, 'time')
  def test_default_configs(self, time_mock):
    current_time = time()
    time_mock.return_value = current_time - 0.001
    start_time = int((current_time - 0.001) * 1000)
    stats = stats_manager.ServiceStats("my_service")
    time_mock.return_value = in_mock_time = current_time

    # Test cumulative counters in zero state
    self.assertEqual(stats.get_cumulative_counters(), {
      "from": start_time,
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
      }
    })

    # Starting new request shouldn't affect counters
    req_no = stats.start_request(app="guestbook")
    self.assertEqual(stats.get_cumulative_counters(), {
      "from": start_time,
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
      }
    })

    # Only finishing request should change things
    stats.finalize_request(req_no, status=200)
    time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(stats.get_cumulative_counters(), {
      "from": start_time,
      "to": int(in_mock_time * 1000),
      "all": 1,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
        "guestbook": {"all": 1, "4xx": 0, "5xx": 0}
      }
    })

    # Reporting client error in guestbook
    req_no = stats.start_request(app="guestbook")
    stats.finalize_request(req_no, status=401)
    time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(stats.get_cumulative_counters(), {
      "from": start_time,
      "to": int(in_mock_time * 1000),
      "all": 2,
      "4xx": 1,
      "5xx": 0,
      "by_app": {
        "guestbook": {"all": 2, "4xx": 1, "5xx": 0}
      }
    })

    # Reporting client and then server errors in new application ghostbook
    req_no = stats.start_request(app="ghostbook")
    stats.finalize_request(req_no, status=404)
    req_no = stats.start_request(app="ghostbook")
    stats.finalize_request(req_no, status=503)
    time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(stats.get_cumulative_counters(), {
      "from": start_time,
      "to": int(in_mock_time * 1000),
      "all": 4,
      "4xx": 2,
      "5xx": 1,
      "by_app": {
        "guestbook": {"all": 2, "4xx": 1, "5xx": 0},
        "ghostbook": {"all": 2, "4xx": 1, "5xx": 1}
      }
    })


class TestCustomCumulativeCounters(unittest.TestCase):

  def setUp(self):
    request_fields = ["app", "namespace", "status"]

    class DefaultNsMatcher(matchers.RequestMatcher):
      def matches(self, request_info):
        return request_info.namespace == "default"

    by_app = categorizers.ExactValueCategorizer("by_app", field="app")
    by_ns = categorizers.ExactValueCategorizer("by_ns", field="namespace")
    by_status = categorizers.ExactValueCategorizer("by_status", field="status")

    counters_config = {
      "all": matchers.ANY,
      by_app: {
        "all": matchers.ANY,
        "default_ns": DefaultNsMatcher(),
        by_ns: {
          "all": matchers.ANY,
          "4xx": matchers.CLIENT_ERROR,
          "5xx": matchers.SERVER_ERROR,
        },
        by_status: matchers.ANY,
      }
    }

    self.stats = stats_manager.ServiceStats(
      "my_service", cumulative_counters=counters_config,
      request_fields=request_fields
    )

  def test_custom_configs(self):
    # Check initial state of counters
    counters = self.stats.get_cumulative_counters()
    self.assertEqual(counters, {
      "from": counters["from"],  # it's not an object of the test
      "to": counters["to"],  # it's not an object of the test
      "all": 0,
      "by_app": {
      }
    })

    # Report requests
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=500)
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=400)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=201)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=201)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=200)

    # Check counters
    counters = self.stats.get_cumulative_counters()
    self.maxDiff = None
    self.assertEqual(counters, {
      "from": counters["from"],  # it's not an object of the test
      "to": counters["to"],  # it's not an object of the test
      "all": 9,
      "by_app": {
        "guestbook": {
          "all": 6,
          "default_ns": 3,
          "by_ns": {
            "friends": {"all": 3, "4xx": 0, "5xx": 1},
            "default": {"all": 3, "4xx": 1, "5xx": 0},
          },
          "by_status": {200: 2, 201: 2, 400: 1, 500: 1}
        },
        "other": {
          "all": 3,
          "default_ns": 0,
          "by_ns": {
            "ghosts": {"all": 3, "4xx": 0, "5xx": 0},
          },
          "by_status": {200: 3}
        }
      }
    })


class TestDefaultRecentStats(unittest.TestCase):

  @patch.object(stats_manager.time, 'time')
  def test_default_configs(self, time_mock):
    current_time = time()
    time_mock.return_value = current_time - 0.001
    stats = stats_manager.ServiceStats("my_service")
    time_mock.return_value = in_mock_time = current_time

    # Test recent stats for 0 requests
    self.assertEqual(stats.get_recent(), {
      "from": int(in_mock_time * 1000),
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "avg_latency": None,
      "by_app": {
      }
    })


class TestServiceStats(unittest.TestCase):

  def test_current_requests(self):
    # TODO
    pass

  def test_service_name(self):
    # TODO
    pass

  def test_history_limit(self):
    # TODO
    pass

  def test_tornado_lock(self):
    # TODO
    pass

  def test_multithreading_lock(self):
    # TODO
    pass


'''
class TestCustomRecentStats(unittest.TestCase):

  def setUp(self):
    request_fields = ["app", "namespace", "status", "weight"]

    class AvgWeight(metrics.Metric):
      def compute(self, requests):
        if not requests:
          return None
        return sum(request.weight for request in requests) / len(requests)

    class MaxWeight(metrics.Metric):
      def compute(self, requests):
        if not requests:
          return None
        return max(request.weight for request in requests)

    by_app = categorizers.ExactValueCategorizer("by_app", field="app")
    by_ns = categorizers.ExactValueCategorizer("by_ns", field="namespace")
    by_status = categorizers.ExactValueCategorizer("by_status", field="status")

    metrics_config = {
      "all": metrics.CountOf(matchers.ANY),
      by_app: {
        "all": metrics.CountOf(matchers.ANY),
        "avg_weight": AvgWeight(),
        "max_weight": MaxWeight(),
        by_ns: {
          "all": metrics.CountOf(matchers.ANY),
          "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
          "5xx": metrics.CountOf(matchers.SERVER_ERROR)
        },
        by_status: metrics.CountOf(matchers.ANY),
      }
    }

    self.stats = stats_manager.ServiceStats(
      "my_service", metrics_for_recent=metrics_config,
      request_fields=request_fields
    )

  def test_custom_configs(self):
    # Check initial state of counters
    counters = self.stats.get_cumulative_counters()
    self.assertEqual(counters, {
      "from": counters["from"],  # it's not an object of the test
      "to": counters["to"],  # it's not an object of the test
      "all": 0,
      "by_app": {
      }
    })

    # Report requests
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=500)
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=400)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=201)
    req_no = self.stats.start_request(app="guestbook", namespace="default")
    self.stats.finalize_request(req_no, status=201)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="other", namespace="ghosts")
    self.stats.finalize_request(req_no, status=200)
    req_no = self.stats.start_request(app="guestbook", namespace="friends")
    self.stats.finalize_request(req_no, status=200)

    # Check counters
    counters = self.stats.get_cumulative_counters()
    self.maxDiff = None
    self.assertEqual(counters, {
      "from": counters["from"],  # it's not an object of the test
      "to": counters["to"],  # it's not an object of the test
      "all": 9,
      "by_app": {
        "guestbook": {
          "all": 6,
          "default_ns": 3,
          "by_ns": {
            "friends": {"all": 3, "4xx": 0, "5xx": 1},
            "default": {"all": 3, "4xx": 1, "5xx": 0},
          },
          "by_status": {200: 2, 201: 2, 400: 1, 500: 1}
        },
        "other": {
          "all": 3,
          "default_ns": 0,
          "by_ns": {
            "ghosts": {"all": 3, "4xx": 0, "5xx": 0},
          },
          "by_status": {200: 3}
        }
      }
    })
'''
