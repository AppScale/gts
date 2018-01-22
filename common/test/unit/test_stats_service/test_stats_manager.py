import unittest
from time import time

from mock import patch

from appscale.common.service_stats import matchers, metrics, stats_manager, \
  categorizers

def request_simulator(service_stats, time_mock=None):
  """ Builds quick request reported for simulating
  start and finalization of request with optionally specified latency.

  Args:
    service_stats: an instance of stats_manager.ServiceStats
    time_mock: a mock of time.time() function
  Returns:
    a function for reporting requests
  """
  def parametrized(latency=None, end_time=None, start_kwargs=None,
                   **finish_kwargs):
    """ Util function for quick reporting request with wanted latency.

    Args:
      latency: an integer number representing wanted latency in ms.
      end_time: unix epoch time in ms.
      start_kwargs: a dict containing items to use for starting request.
      finish_kwargs: a dict containing items to use for finalizing request.
    """
    if latency:
      if end_time:
        end_time_s = float(end_time)/1000
        start_time = end_time_s - float(latency)/1000
      else:
        start_time = time()
        end_time_s = start_time + float(latency)/1000
      time_mock.return_value = start_time
      request_no = service_stats.start_request(**(start_kwargs or {}))
      time_mock.return_value = end_time_s
      service_stats.finalize_request(request_no, **finish_kwargs)
    else:
      request_no = service_stats.start_request(**(start_kwargs or {}))
      service_stats.finalize_request(request_no, **finish_kwargs)

  return parametrized


class TestDefaultCumulativeCounters(unittest.TestCase):

  def setUp(self):
    self.time_patcher = patch.object(stats_manager.time, 'time')
    self.time_mock = self.time_patcher.start()
    # Initialize ServiceStats
    current_time = time()
    self.time_mock.return_value = current_time - 0.001
    self.start_time = int((current_time - 0.001) * 1000)
    self.stats = stats_manager.ServiceStats("my_service")
    self.time_mock.return_value = current_time

  def tearDown(self):
    self.time_patcher.stop()

  def test_default_configs(self):
    in_mock_time = self.time_mock()
    # Test cumulative counters in zero state
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
      }
    })

    # Starting new request shouldn't affect counters
    req_no = self.stats.start_request(app="guestbook")
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
      }
    })

    # Only finishing request should change things
    self.stats.finalize_request(req_no, status=200)
    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 1,
      "4xx": 0,
      "5xx": 0,
      "by_app": {
        "guestbook": {"all": 1, "4xx": 0, "5xx": 0}
      }
    })

    # Reporting client error in guestbook
    req_no = self.stats.start_request(app="guestbook")
    self.stats.finalize_request(req_no, status=401)
    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 2,
      "4xx": 1,
      "5xx": 0,
      "by_app": {
        "guestbook": {"all": 2, "4xx": 1, "5xx": 0}
      }
    })

    # Reporting client and then server errors in new application ghostbook
    req_no = self.stats.start_request(app="ghostbook")
    self.stats.finalize_request(req_no, status=404)
    req_no = self.stats.start_request(app="ghostbook")
    self.stats.finalize_request(req_no, status=503)
    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
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


class TestRecentStatsFor0Requests(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.time_patcher = patch.object(stats_manager.time, 'time')
    cls.time_mock = cls.time_patcher.start()
    # Initialize ServiceStats
    cls.time_mock.return_value = time()
    cls.stats = stats_manager.ServiceStats("my_service")

  @classmethod
  def tearDownClass(cls):
    cls.time_patcher.stop()

  def test_default_metrics(self):
    in_mock_time = self.time_mock()
    # Check recent stats for 0 requests
    self.assertEqual(self.stats.get_recent(), {
      "from": int(in_mock_time * 1000),
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "avg_latency": None
    })

  def test_detailed_metrics(self):
    in_mock_time = self.time_mock()
    # Check recent stats for 0 requests using detailed metrics
    detailed_metrics = stats_manager.PER_APP_DETAILED_METRICS_MAP
    self.assertEqual(self.stats.get_recent(metrics_map=detailed_metrics), {
      "from": int(in_mock_time * 1000),
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "avg_latency": None,
      "by_app": {}
    })


class TestMetricsConfigs(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.time_patcher = patch.object(stats_manager.time, 'time')
    cls.time_mock = cls.time_patcher.start()
    # Initialize ServiceStats with default metrics for recent requests
    cls.time_mock.return_value = time()
    cls.stats = stats_manager.ServiceStats("my_service")

    # Initialize request_simulator for shorter form of start-finalize calls
    request = request_simulator(cls.stats, cls.time_mock)

    # Start and finalize requests using request_simulator
    request(latency=100, app="guestbook", resource="/", status=200,
            end_time=1515595821111)
    request(latency=150, app="guestbook", resource="/", status=200)
    request(latency=200, app="guestbook", resource="/api/foo", status=200)
    request(latency=250, app="guestbook", resource="/api/v2", status=200)
    request(latency=300, app="guestbook", resource="/api/v2", status=403)
    request(latency=350, app="guestbook", resource="/api/v2", status=403)
    request(latency=400, app="guestbook", resource="/api/v3/z", status=404)
    request(latency=450, app="guestbook", resource="/api/v3/z", status=502)
    request(latency=500, app="other", resource="/foo/bar", status=200)
    request(latency=550, app="other", resource="/foo/bar", status=200)
    request(latency=600, app="other", resource="/path", status=200)
    request(latency=650, app="other", resource="/path", status=200)
    request(latency=701, app="other", resource="/path", status=401,
            end_time=1515595824444)

  @classmethod
  def tearDownClass(cls):
    cls.time_patcher.stop()

  def test_default_metrics(self):
    # Check recent stats for 13 requests using default main metrics
    self.assertEqual(self.stats.get_recent(), {
      "from": 1515595821111,
      "to": 1515595824444,
      "all": 13,
      "4xx": 4,
      "5xx": 1,
      "avg_latency": 400
    })

  def test_detailed_metrics(self):
    # Check recent stats for 13 requests using detailed metrics
    detailed_metrics = stats_manager.PER_APP_DETAILED_METRICS_MAP
    self.assertEqual(self.stats.get_recent(metrics_map=detailed_metrics), {
      "from": 1515595821111,
      "to": 1515595824444,
      "all": 13,
      "4xx": 4,
      "5xx": 1,
      "avg_latency": 400,
      "by_app": {
        "guestbook": {
          "by_resource": {
            "/": {"all": 2, "4xx": 0, "5xx": 0, "avg_latency": 125},
            "/api/foo": {"all": 1, "4xx": 0, "5xx": 0, "avg_latency": 200},
            "/api/v2": {"all": 3, "4xx": 2, "5xx": 0, "avg_latency": 300},
            "/api/v3/z": {"all": 2, "4xx": 1, "5xx": 1, "avg_latency": 425}
          },
          "all": 8,
          "4xx": 3,
          "5xx": 1,
          "avg_latency": 275
        },
        "other": {
          "by_resource": {
            "/foo/bar": {"all": 2, "4xx": 0, "5xx": 0, "avg_latency": 525},
            "/path": {"all": 3, "4xx": 1, "5xx": 0, "avg_latency": 650}
          },
          "all": 5,
          "4xx": 1,
          "5xx": 0,
          "avg_latency": 600
        }
      }
    })


class TestScrollingRecent(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.time_patcher = patch.object(stats_manager.time, 'time')
    cls.time_mock = cls.time_patcher.start()
    # Initialize ServiceStats with default metrics for recent requests
    cls.time_mock.return_value = time()
    cls.stats = stats_manager.ServiceStats(
      "my_service", history_size=6,
      default_metrics_for_recent={
        "all": metrics.CountOf(matchers.ANY),
        "4xx": metrics.CountOf(matchers.CLIENT_ERROR),
        "5xx": metrics.CountOf(matchers.SERVER_ERROR),
      })

    # Start and finalize requests to fill recent requests history

    # First two are finished in the same time,
    # but one with status 500 was reported first
    cls.time_mock.return_value = 151550002
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=500)
    cls.time_mock.return_value = 151550002
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=400)

    # Then one request every second (only 2 latest has status 200)
    cls.time_mock.return_value = 151550003
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=400)
    cls.time_mock.return_value = 151550004
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=400)
    cls.time_mock.return_value = 151550005
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=400)
    cls.time_mock.return_value = 151550006
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=200)
    cls.time_mock.return_value = 151550007
    req_no = cls.stats.start_request(app="my_app")
    cls.stats.finalize_request(req_no, status=200)

  @classmethod
  def tearDownClass(cls):
    cls.time_patcher.stop()

  def test_history_size(self):
    self.assertEqual(self.stats.get_recent(), {
      "from": 151550002000,
      "to": 151550007000,
      "all": 6,
      "4xx": 4,
      "5xx": 0  # 1st request with server error was removed from limited history
    })

  def test_get_recent(self):
    self.time_mock.return_value = 151550008.5
    self.assertEqual(self.stats.get_recent(for_last_milliseconds=6000), {
      "from": 151550003000, "to": 151550007000, "all": 5, "4xx": 3, "5xx": 0
    })

  def test_scroll_recent(self):
    self.assertEqual(self.stats.scroll_recent(cursor=151550003500), {
      "from": 151550004000, "to": 151550007000, "all": 4, "4xx": 2, "5xx": 0
    })
    self.assertEqual(self.stats.scroll_recent(cursor=151550004000), {
      "from": 151550004000, "to": 151550007000, "all": 4, "4xx": 2, "5xx": 0
    })
    self.assertEqual(self.stats.scroll_recent(cursor=151550004500), {
      "from": 151550005000, "to": 151550007000, "all": 3, "4xx": 1, "5xx": 0
    })
    self.assertEqual(self.stats.scroll_recent(cursor=151550005000), {
      "from": 151550005000, "to": 151550007000, "all": 3, "4xx": 1, "5xx": 0
    })


class TestProperties(unittest.TestCase):

  def test_service_name(self):
    stats = stats_manager.ServiceStats("my_SERvice")
    self.assertEqual(stats.service_name, "my_SERvice")

  def test_current_requests(self):
    # Initialize ServiceStats with default metrics for recent requests
    stats = stats_manager.ServiceStats("my_service")

    # Start and finalize 3 requests
    req_no = stats.start_request()
    stats.finalize_request(req_no)
    req_no = stats.start_request()
    stats.finalize_request(req_no)
    req_no = stats.start_request()
    stats.finalize_request(req_no)

    # Start without finalization 4 requests
    stats.start_request()
    stats.start_request()
    stats.start_request()
    stats.start_request()

    self.assertEqual(stats.current_requests, 4)
