from tornado import locks

from appscale.common.service_stats import stats_manager, samples

PROTOBUFFER_API = "protobuffer"
REST_API = "rest"

# Define matcher for detecting different types of request
def summarize_failed_request(request_info):
  return request_info.pb_status != "OK" and request_info.rest_status != 200


def summarize_protobuffer_request(request_info):
  return request_info.api == PROTOBUFFER_API


def summarize_rest_request(request_info):
  return request_info.api == REST_API


# Define categorizers for grouping requests
def categorize_by_pb_method(request_info):
  if request_info.api != PROTOBUFFER_API:
    return stats_manager.HIDDEN_CATEGORY
  return request_info.pb_method


def categorize_by_rest_method(request_info):
  if request_info.api != REST_API:
    return stats_manager.HIDDEN_CATEGORY
  return request_info.rest_method


def categorize_by_pb_status(request_info):
  if request_info.api != PROTOBUFFER_API:
    return stats_manager.HIDDEN_CATEGORY
  return request_info.pb_status


def categorize_by_rest_status(request_info):
  if request_info.api != REST_API:
    return stats_manager.HIDDEN_CATEGORY
  return request_info.rest_status


# define metrics
def count_failed_requests(requests):
  return sum(1 for request in requests
             if request.pb_status != "OK" and request.rest_status != 200)


def count_protobuff_requests(requests):
  return sum(1 for request in requests if request.api == PROTOBUFFER_API)


def count_rest_requests(requests):
  return sum(1 for request in requests if request.api == REST_API)


# Instantiate request matchers
FAILED_REQUEST = summarize_failed_request
PROTOBUFF_REQUEST = summarize_protobuffer_request
REST_REQUEST = summarize_rest_request

# Instantiate request categorizers
PB_METHOD_CATEGORIZER = categorize_by_pb_method
REST_METHOD_CATEGORIZER = categorize_by_rest_method
PB_STATUS_CATEGORIZER = categorize_by_pb_status
REST_STATUS_CATEGORIZER = categorize_by_rest_status


# Configure ServiceStats
REQUEST_STATS_FIELDS = [
  "pb_method", "pb_status", "rest_method", "rest_status", "api"
]
CUMULATIVE_COUNTERS = {
  "all": samples.summarize_any,
  "failed": FAILED_REQUEST,
  "pb_reqs": PROTOBUFF_REQUEST,
  "rest_reqs": REST_REQUEST
}
METRICS_CONFIG = {
  "all": samples.count_any,
  "failed": count_failed_requests,
  "avg_latency": samples.count_avg_latency,
  "pb_reqs": count_protobuff_requests,
  "rest_reqs": count_rest_requests,
  PB_METHOD_CATEGORIZER: samples.count_any,
  REST_METHOD_CATEGORIZER: samples.count_any,
  PB_STATUS_CATEGORIZER: samples.count_any,
  REST_STATUS_CATEGORIZER: samples.count_any
}
# Instantiate singleton ServiceStats
service_stats = stats_manager.ServiceStats(
  "taskqueue", request_fields=REQUEST_STATS_FIELDS,
  cumulative_counters=CUMULATIVE_COUNTERS,
  default_metrics_for_recent=METRICS_CONFIG
)
# Create tornado lock for tracking concurrent requests
stats_lock = locks.Lock()
