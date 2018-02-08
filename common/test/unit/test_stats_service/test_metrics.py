import unittest

from appscale.common.service_stats import metrics, matchers
from appscale.common.service_stats.stats_manager import (
  ServiceStats, DEFAULT_REQUEST_FIELDS
)


RequestInfo = ServiceStats.generate_request_model(DEFAULT_REQUEST_FIELDS)


class TestBuiltinMetrics(unittest.TestCase):
  def test_avg_latency(self):
    requests = [RequestInfo(), RequestInfo(), RequestInfo(), RequestInfo()]
    req_a, req_b, req_c, req_d = requests
    # latency is builtin property which can't be passed to constructor
    req_a.latency = 300
    req_b.latency = 1000
    req_c.latency = 500
    req_d.latency = 602
    self.assertEqual(metrics.Avg("latency").compute(requests), 600)

  def test_max_latency(self):
    requests = [RequestInfo(), RequestInfo(), RequestInfo(), RequestInfo()]
    req_a, req_b, req_c, req_d = requests
    # latency is builtin property which can't be passed to constructor
    req_a.latency = 300
    req_b.latency = 1000
    req_c.latency = 500
    req_d.latency = 602
    self.assertEqual(metrics.Max("latency").compute(requests), 1000)

  def test_avg_respsize(self):
    requests = [
      RequestInfo(response_size=20000),
      RequestInfo(response_size=0),
      RequestInfo(response_size=20000),
      RequestInfo(response_size=2)
    ]
    self.assertEqual(metrics.Avg("response_size").compute(requests), 10000)

  def test_count_of(self):
    requests = [
      RequestInfo(status=200, method="GET"),
      RequestInfo(status=404, method="GET"),
      RequestInfo(status=405, method="POST"),
      RequestInfo(status=401, method="POST"),
      RequestInfo(status=500, method="GET"),
      RequestInfo(status=503, method="POST"),
      RequestInfo(status=200, method="GET"),
      RequestInfo(status=200, method="GET"),
    ]

    class PostMatcher(matchers.RequestMatcher):
      def matches(self, request_info):
        return request_info.method == "POST"

    total = metrics.CountOf(matchers.ANY)
    client_errors = metrics.CountOf(matchers.CLIENT_ERROR)
    server_errors = metrics.CountOf(matchers.SERVER_ERROR)
    post = metrics.CountOf(PostMatcher())
    self.assertEqual(total.compute(requests), 8)
    self.assertEqual(client_errors.compute(requests), 3)
    self.assertEqual(server_errors.compute(requests), 2)
    self.assertEqual(post.compute(requests), 3)


class TestCustomMetric(unittest.TestCase):

  class SuccessPercentMetric(metrics.Metric):
    def compute(self, requests):
      succeeded = sum(1 for request in requests if request.status < 400)
      return float(succeeded) / len(requests) * 100

  def test_custom_metric(self):
    requests = [
      RequestInfo(status=200),
      RequestInfo(status=404),
      RequestInfo(status=405),
      RequestInfo(status=401),
      RequestInfo(status=500),
      RequestInfo(status=503),
      RequestInfo(status=200),
      RequestInfo(status=200),
    ]
    success_pct = self.SuccessPercentMetric()
    self.assertEqual(success_pct.compute(requests), 37.5)
