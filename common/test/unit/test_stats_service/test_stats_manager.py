import unittest
from time import time

from mock import patch

from appscale.common.service_stats import stats_manager, samples

def request_simulator(service_stats, time_mock=None):
  """ Builds quick request reported for simulating
  start and finalization of request with optionally specified latency.

  Args:
    service_stats: an instance of stats_manager.ServiceStats
    time_mock: a mock of time.time() function
  Returns:
    a function for reporting requests
  """
  def parametrized(latency=None, end_time=None, app=None, status=None,
                   resource=None):
    """ Util function for quick reporting request with wanted latency.

    Args:
      latency: an integer number representing wanted latency in ms.
      end_time: unix epoch time in ms.
      app: a string representing application name.
      status: an integer representing request status.
    """
    if latency:
      if end_time:
        end_time_s = float(end_time)/1000
        start_time = end_time_s - float(latency)/1000
      else:
        start_time = time()
        end_time_s = start_time + float(latency)/1000
      time_mock.return_value = start_time
      request_info = service_stats.start_request()
      request_info.app = app
      request_info.resource = resource
      time_mock.return_value = end_time_s
      request_info.status = status
      request_info.finalize()
    else:
      request_info = service_stats.start_request()
      request_info.finalize()

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
    self.request_simulation = request_simulator(self.stats, self.time_mock)

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
      "latency": 0,
      "by_app": {
      }
    })

    # Starting new request shouldn't affect counters
    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 0,
      "4xx": 0,
      "5xx": 0,
      "latency": 0,
      "by_app": {
      }
    })

    # Only finishing request should change things
    req_info.status = 200
    req_info.finalize()
    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 1,
      "4xx": 0,
      "5xx": 0,
      "latency": 0,
      "by_app": {
        "guestbook": {"all": 1, "4xx": 0, "5xx": 0, "latency": 0}
      }
    })

    # Reporting client error in guestbook
    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.status = 401  # You can fill request fields manually
    req_info.finalize()
    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 2,
      "4xx": 1,
      "5xx": 0,
      "latency": 0,
      "by_app": {
        "guestbook": {"all": 2, "4xx": 1, "5xx": 0, "latency": 0}
      }
    })

    # Reporting client and then server errors in new application ghostbook
    req_info = self.stats.start_request()
    req_info.app = "ghostbook"
    req_info.status=404
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "ghostbook"
    req_info.status = 503
    req_info.finalize()

    self.time_mock.return_value = in_mock_time = int(time() * 1000)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": int(in_mock_time * 1000),
      "all": 4,
      "4xx": 2,
      "5xx": 1,
      "latency": 0,
      "by_app": {
        "guestbook": {"all": 2, "4xx": 1, "5xx": 0, "latency": 0},
        "ghostbook": {"all": 2, "4xx": 1, "5xx": 1, "latency": 0}
      }
    })

    # Testing latency using request_simulator function
    self.request_simulation(latency=100, app="guestbook", status=200,
                            end_time=1515595821111)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": 1515595821111,
      "all": 5,
      "4xx": 2,
      "5xx": 1,
      "latency": 100,
      "by_app": {
        "guestbook": {"all": 3, "4xx": 1, "5xx": 0, "latency": 100},
        "ghostbook": {"all": 2, "4xx": 1, "5xx": 1, "latency": 0}
      }
    })

    self.request_simulation(latency=150, app="guestbook", status=200,
                            end_time=1515595821111)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": 1515595821111,
      "all": 6,
      "4xx": 2,
      "5xx": 1,
      "latency": 250,
      "by_app": {
        "guestbook": {"all": 4, "4xx": 1, "5xx": 0, "latency": 250},
        "ghostbook": {"all": 2, "4xx": 1, "5xx": 1, "latency": 0}
      }
    })

    self.request_simulation(latency=200, app="guestbook", status=404,
                            end_time=1515595821111)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": 1515595821111,
      "all": 7,
      "4xx": 3,
      "5xx": 1,
      "latency": 450,
      "by_app": {
        "guestbook": {"all": 5, "4xx": 2, "5xx": 0, "latency": 450},
        "ghostbook": {"all": 2, "4xx": 1, "5xx": 1, "latency": 0}
      }
    })

    self.request_simulation(latency=200, app="ghostbook", status=503,
                            end_time=1515595821111)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": 1515595821111,
      "all": 8,
      "4xx": 3,
      "5xx": 2,
      "latency": 650,
      "by_app": {
        "guestbook": {"all": 5, "4xx": 2, "5xx": 0, "latency": 450},
        "ghostbook": {"all": 3, "4xx": 1, "5xx": 2, "latency": 200}
      }
    })

    self.request_simulation(latency=350, app="mybook", status=404,
                            end_time=1515595821111)
    self.assertEqual(self.stats.get_cumulative_counters(), {
      "from": self.start_time,
      "to": 1515595821111,
      "all": 9,
      "4xx": 4,
      "5xx": 2,
      "latency": 1000,
      "by_app": {
        "guestbook": {"all": 5, "4xx": 2, "5xx": 0, "latency": 450},
        "ghostbook": {"all": 3, "4xx": 1, "5xx": 2, "latency": 200},
        "mybook": {"all": 1, "4xx": 1, "5xx": 0, "latency": 350},
      }
    })


class TestCustomCumulativeCounters(unittest.TestCase):

  def setUp(self):
    request_fields = ["app", "namespace", "status", "method",
                      "preproc_time", "postproc_time"]

    def data_proc_summarizer(request_info):
      return request_info.preproc_time + request_info.postproc_time

    counters_config = {
      "all": samples.summarize_all,
      "total": data_proc_summarizer,
      ("by_app", samples.categorize_by_app): {
        "all": samples.summarize_all,
        "default_ns": lambda req_info: req_info.namespace == "default",
        ("by_ns", lambda req_info: req_info.namespace): {
          "all": samples.summarize_all,
          "4xx": samples.summarize_client_error,
          "5xx": samples.summarize_server_error,
        },
        ("by_status", samples.categorize_by_status): samples.summarize_all,
        ("by_method", samples.categorize_by_method): data_proc_summarizer
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
      "total": 0,
      "by_app": {
      }
    })

    # Report requests
    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "friends"
    req_info.method = "POST"
    req_info.preproc_time = 6
    req_info.status = 500
    req_info.postproc_time = 0
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "friends"
    req_info.method = "GET"
    req_info.preproc_time = 12
    req_info.status = 200
    req_info.postproc_time = 12
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "default"
    req_info.method = "GET"
    req_info.preproc_time = 12
    req_info.status = 400
    req_info.postproc_time = 0
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "default"
    req_info.method = "GET"
    req_info.preproc_time = 10
    req_info.status = 201
    req_info.postproc_time = 10
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "default"
    req_info.method = "POST"
    req_info.preproc_time = 5
    req_info.status = 201
    req_info.postproc_time = 10
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "other"
    req_info.namespace = "ghosts"
    req_info.method = "POST"
    req_info.preproc_time = 20
    req_info.status = 200
    req_info.postproc_time = 10
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "other"
    req_info.namespace = "ghosts"
    req_info.method = "GET"
    req_info.preproc_time = 10
    req_info.status = 200
    req_info.postproc_time = 10
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "other"
    req_info.namespace = "ghosts"
    req_info.method = "GET"
    req_info.preproc_time = 15
    req_info.status = 200
    req_info.postproc_time = 10
    req_info.finalize()

    req_info = self.stats.start_request()
    req_info.app = "guestbook"
    req_info.namespace = "friends"
    req_info.method = "POST"
    req_info.preproc_time = 10
    req_info.status = 200
    req_info.postproc_time = 10
    req_info.finalize()

    # Check counters
    counters = self.stats.get_cumulative_counters()
    self.maxDiff = None
    self.assertEqual(counters, {
      "from": counters["from"],  # it's not an object of the test
      "to": counters["to"],  # it's not an object of the test
      "all": 9,
      "total": 172,
      "by_app": {
        "guestbook": {
          "all": 6,
          "default_ns": 3,
          "by_ns": {
            "friends": {"all": 3, "4xx": 0, "5xx": 1},
            "default": {"all": 3, "4xx": 1, "5xx": 0},
          },
          "by_status": {200: 2, 201: 2, 400: 1, 500: 1},
          "by_method": {"GET": 56, "POST": 41}
        },
        "other": {
          "all": 3,
          "default_ns": 0,
          "by_ns": {
            "ghosts": {"all": 3, "4xx": 0, "5xx": 0},
          },
          "by_status": {200: 3},
          "by_method": {"GET": 45, "POST": 30}
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
        "all": samples.count_all,
        "4xx": samples.count_client_errors,
        "5xx": samples.count_server_errors
      })

    # Start and finalize requests to fill recent requests history

    # First two are finished in the same time,
    # but one with status 500 was reported first
    cls.time_mock.return_value = 151550002
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 500
    req_info.finalize()
    cls.time_mock.return_value = 151550002
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 400
    req_info.finalize()

    # Then one request every second (only 2 latest has status 200)
    cls.time_mock.return_value = 151550003
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 400
    req_info.finalize()
    cls.time_mock.return_value = 151550004
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 400
    req_info.finalize()
    cls.time_mock.return_value = 151550005
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 400
    req_info.finalize()
    cls.time_mock.return_value = 151550006
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 200
    req_info.finalize()
    cls.time_mock.return_value = 151550007
    req_info = cls.stats.start_request()
    req_info.app = "my_app"
    req_info.status = 200
    req_info.finalize()

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
    req_info = stats.start_request()
    req_info.app = "app"
    req_info.status = 404
    req_info.finalize()
    req_info = stats.start_request()
    req_info.app = "app"
    req_info.status = 404
    req_info.finalize()
    req_info = stats.start_request()
    req_info.app = "app"
    req_info.status = 404
    req_info.finalize()

    # Start without finalization 4 requests
    stats.start_request()
    stats.start_request()
    stats.start_request()
    stats.start_request()

    self.assertEqual(stats.current_requests, 4)
