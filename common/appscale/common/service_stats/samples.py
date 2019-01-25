""" This module contains standard functions to use in Service Stats. """


def categorize_by_app(req_info):
  return req_info.app


def categorize_by_method(req_info):
  return req_info.method


def categorize_by_resource(req_info):
  return req_info.resource


def categorize_by_status(req_info):
  return req_info.status


def summarize_all(req_info):
  """ Can be also used as matcher. """
  return True


def summarize_client_error(req_info):
  """ Can be also used as matcher. """
  return 400 <= req_info.status <= 499


def summarize_server_error(req_info):
  """ Can be also used as matcher. """
  return 500 <= req_info.status <= 599


def summarize_latency(req_info):
  return req_info.latency


def count_all(requests):
  return len(requests)


def count_client_errors(requests):
  return sum(1 for request in requests if 400 <= request.status <= 499)


def count_server_errors(requests):
  return sum(1 for request in requests if 500 <= request.status <= 599)


def count_avg_latency(requests):
  if not requests:
    return None
  return sum(request.latency for request in requests) / len(requests)
