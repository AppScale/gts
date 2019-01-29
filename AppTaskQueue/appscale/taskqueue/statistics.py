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


# Configure ServiceStats
REQUEST_STATS_FIELDS = [
  "pb_method", "pb_status", "rest_method", "rest_status", "api"
]
CUMULATIVE_COUNTERS = {
  "all": samples.summarize_all,
  "failed": summarize_failed_request,
  "pb_reqs": summarize_protobuffer_request,
  "rest_reqs": summarize_rest_request
}
METRICS_CONFIG = {
  "all": samples.count_all,
  "failed": count_failed_requests,
  "avg_latency": samples.count_avg_latency,
  "pb_reqs": count_protobuff_requests,
  "rest_reqs": count_rest_requests,
  ("by_pb_method", categorize_by_pb_method): samples.count_all,
  ("by_rest_method", categorize_by_rest_method): samples.count_all,
  ("by_pb_status", categorize_by_pb_status): samples.count_all,
  ("by_rest_status", categorize_by_rest_status): samples.count_all
}
# Instantiate singleton ServiceStats
service_stats = stats_manager.ServiceStats(
  "taskqueue", request_fields=REQUEST_STATS_FIELDS,
  cumulative_counters=CUMULATIVE_COUNTERS,
  default_metrics_for_recent=METRICS_CONFIG
)
# Create tornado lock for tracking concurrent requests
stats_lock = locks.Lock()
