from tornado import locks

from appscale.common.service_stats import (
  categorizers, metrics, matchers, stats_manager
)

PROTOBUFFER_API = "protobuffer"
REST_API = "rest"

# Define matcher for detecting different types of request
class FailedRequestMatcher(matchers.RequestMatcher):
  def matches(self, request_info):
    return request_info.pb_status != "OK" and request_info.rest_status != 200


class ProtobufferRequestMatcher(matchers.RequestMatcher):
  def matches(self, request_info):
    return request_info.api == PROTOBUFFER_API


class RestRequestMatcher(matchers.RequestMatcher):
  def matches(self, request_info):
    return request_info.api == REST_API


# Define categorizers for grouping requests
class PBMethodCategorizer(categorizers.Categorizer):
  def category_of(self, req_info):
    if req_info.api != PROTOBUFFER_API:
      return categorizers.HIDDEN_CATEGORY
    return req_info.pb_method


class RestMethodCategorizer(categorizers.Categorizer):
  def category_of(self, req_info):
    if req_info.api != REST_API:
      return categorizers.HIDDEN_CATEGORY
    return req_info.rest_method


class PBStatusCategorizer(categorizers.Categorizer):
  def category_of(self, req_info):
    if req_info.api != PROTOBUFFER_API:
      return categorizers.HIDDEN_CATEGORY
    return req_info.pb_status

class RestStatusCategorizer(categorizers.Categorizer):
  def category_of(self, req_info):
    if req_info.api != REST_API:
      return categorizers.HIDDEN_CATEGORY
    return req_info.rest_status


# Instantiate request matchers
FAILED_REQUEST = FailedRequestMatcher()
PROTOBUFF_REQUEST = ProtobufferRequestMatcher()
REST_REQUEST = RestRequestMatcher()

# Instantiate request categorizers
PB_METHOD_CATEGORIZER = PBMethodCategorizer(
  categorizer_name="by_pb_method")
REST_METHOD_CATEGORIZER = RestMethodCategorizer(
  categorizer_name="by_rest_method")
PB_STATUS_CATEGORIZER = PBStatusCategorizer(
  categorizer_name="by_pb_status")
REST_STATUS_CATEGORIZER = RestStatusCategorizer(
  categorizer_name="by_rest_status")


# Configure ServiceStats
REQUEST_STATS_FIELDS = [
  "pb_method", "pb_status", "rest_method", "rest_status", "api"
]
CUMULATIVE_COUNTERS = {
  "all": matchers.ANY,
  "failed": FAILED_REQUEST,
  "pb_reqs": PROTOBUFF_REQUEST,
  "rest_reqs": REST_REQUEST
}
METRICS_CONFIG = {
  "all": metrics.CountOf(matchers.ANY),
  "failed": metrics.CountOf(FAILED_REQUEST),
  "avg_latency": metrics.Avg("latency"),
  "pb_reqs": metrics.CountOf(PROTOBUFF_REQUEST),
  "rest_reqs": metrics.CountOf(REST_REQUEST),
  PB_METHOD_CATEGORIZER: metrics.CountOf(matchers.ANY),
  REST_METHOD_CATEGORIZER: metrics.CountOf(matchers.ANY),
  PB_STATUS_CATEGORIZER: metrics.CountOf(matchers.ANY),
  REST_STATUS_CATEGORIZER: metrics.CountOf(matchers.ANY)
}
# Instantiate singleton ServiceStats
service_stats = stats_manager.ServiceStats(
  "taskqueue", request_fields=REQUEST_STATS_FIELDS,
  cumulative_counters=CUMULATIVE_COUNTERS,
  default_metrics_for_recent=METRICS_CONFIG
)
# Create tornado lock for tracking concurrent requests
stats_lock = locks.Lock()
