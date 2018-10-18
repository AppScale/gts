""" Fetches TaskQueue service statistics. """
import json
import logging

import attr
import collections

import sys

import time

import socket
from tornado import gen, httpclient

from appscale.hermes.converter import include_list_name, Meta

# The endpoint used for retrieving node stats.
from appscale.hermes.producers import proxy_stats

STATS_ENDPOINT = '/service-stats'


class BadTaskqueueStatsFormat(ValueError):
  pass


@include_list_name('taskqueue.cumulative')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class CumulativeStatsSnapshot(object):
  """ Cumulative counters reported for each TaskQueue instance. """
  total = attr.ib()
  failed = attr.ib()
  pb_reqs = attr.ib()
  rest_reqs = attr.ib()


@include_list_name('taskqueue.recent')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class RecentStatsSnapshot(object):
  """ Recent stats reported for each TaskQueue instance. """
  total = attr.ib()
  failed = attr.ib()
  avg_latency = attr.ib()
  pb_reqs = attr.ib()
  rest_reqs = attr.ib()
  by_pb_method = attr.ib()
  by_rest_method = attr.ib()
  by_pb_status = attr.ib()
  by_rest_status = attr.ib()


@include_list_name('taskqueue.instance')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class InstanceStatsSnapshot(object):
  """ Stats reported for each TaskQueue instance. """
  ip_port = attr.ib()
  start_timestamp_ms = attr.ib()
  current_requests = attr.ib()
  cumulative = attr.ib(metadata={Meta.ENTITY: CumulativeStatsSnapshot})
  recent = attr.ib(metadata={Meta.ENTITY: RecentStatsSnapshot})


@include_list_name('taskqueue.failure')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class FailureSnapshot(object):
  """ Failure reported for a TaskQueue instance. """
  ip_port = attr.ib()
  error = attr.ib()


@include_list_name('taskqueue')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class TaskqueueServiceStatsSnapshot(object):
  """ Stats reported for TaskQueue service. """
  utc_timestamp = attr.ib()
  current_requests = attr.ib()
  cumulative = attr.ib(metadata={Meta.ENTITY: CumulativeStatsSnapshot})
  recent = attr.ib(metadata={Meta.ENTITY: RecentStatsSnapshot})
  instances = attr.ib(metadata={Meta.ENTITY_LIST: InstanceStatsSnapshot})
  instances_count = attr.ib()
  failures = attr.ib(metadata={Meta.ENTITY_LIST: FailureSnapshot})


class TaskqueueStatsSource(object):

  IGNORE_RECENT_OLDER_THAN = 5*60*1000  # 5 minutes
  REQUEST_TIMEOUT = 10  # Wait up to 10 seconds

  @gen.coroutine
  def fetch_stats_from_instance(self, ip_port):
    url = "http://{ip_port}{path}?last_milliseconds={max_age}".format(
      ip_port=ip_port, path=STATS_ENDPOINT,
      max_age=self.IGNORE_RECENT_OLDER_THAN
    )
    request = httpclient.HTTPRequest(
      url=url, method='GET', request_timeout=self.REQUEST_TIMEOUT
    )
    async_client = httpclient.AsyncHTTPClient()

    try:
      # Send Future object to coroutine and suspend till result is ready
      response = yield async_client.fetch(request)
    except (socket.error, httpclient.HTTPError) as err:
      msg = u"Failed to get stats from {url} ({err})".format(url=url, err=err)
      if hasattr(err, 'response') and err.response and err.response.body:
        msg += u"\nBODY: {body}".format(body=err.response.body)
      logging.error(msg)
      failure = FailureSnapshot(ip_port=ip_port, error=unicode(err))
      raise gen.Return(failure)

    try:
      stats_body = json.loads(response.body)
      cumulative_dict = stats_body["cumulative_counters"]
      recent_dict = stats_body["recent_stats"]
      cumulative = CumulativeStatsSnapshot(
        total=cumulative_dict["all"],
        failed=cumulative_dict["failed"],
        pb_reqs=cumulative_dict["pb_reqs"],
        rest_reqs=cumulative_dict["rest_reqs"]
      )
      recent = RecentStatsSnapshot(
        total=recent_dict["all"],
        failed=recent_dict["failed"],
        avg_latency=recent_dict["avg_latency"],
        pb_reqs=recent_dict["pb_reqs"],
        rest_reqs=recent_dict["rest_reqs"],
        by_pb_method=recent_dict["by_pb_method"],
        by_rest_method=recent_dict["by_rest_method"],
        by_pb_status=recent_dict["by_pb_status"],
        by_rest_status=recent_dict["by_rest_status"]
      )
      instance_stats_snapshot = InstanceStatsSnapshot(
        ip_port=ip_port,
        start_timestamp_ms=cumulative_dict["from"],
        current_requests=stats_body["current_requests"],
        cumulative=cumulative,
        recent=recent,
      )
      raise gen.Return(instance_stats_snapshot)
    except (TypeError, KeyError) as err:
      msg = u"Can't parse taskqueue ({})".format(err)
      raise BadTaskqueueStatsFormat(msg), None, sys.exc_info()[2]

  @staticmethod
  def summarise_cumulative(instances_stats):
    cumulative_stats = [server.cumulative for server in instances_stats]
    return CumulativeStatsSnapshot(
      total=sum(cumulative.total for cumulative in cumulative_stats),
      failed=sum(cumulative.failed for cumulative in cumulative_stats),
      pb_reqs=sum(cumulative.pb_reqs for cumulative in cumulative_stats),
      rest_reqs=sum(cumulative.rest_reqs for cumulative in cumulative_stats),
    )

  @staticmethod
  def summarise_recent(instances_stats):
    recent_stats = [server.recent for server in instances_stats]
    weighted_avg_latency_sum = sum(
      recent.avg_latency * recent.total for recent in recent_stats
      if recent.avg_latency is not None
    )
    total_recent_reqs = sum(recent.total for recent in recent_stats)
    # Compute sums for nested dictionaries
    by_pb_method_sum = collections.defaultdict(int)
    by_rest_method_sum = collections.defaultdict(int)
    by_pb_status_sum = collections.defaultdict(int)
    by_rest_status_sum = collections.defaultdict(int)
    for recent in recent_stats:
      for pb_method, calls in recent.by_pb_method.iteritems():
        by_pb_method_sum[pb_method] += calls
      for rest_method, calls in recent.by_rest_method.iteritems():
        by_rest_method_sum[rest_method] += calls
      for pb_status, calls in recent.by_pb_status.iteritems():
        by_pb_status_sum[pb_status] += calls
      for rest_status, calls in recent.by_rest_status.iteritems():
        by_rest_status_sum[rest_status] += calls
    # Return snapshot
    return RecentStatsSnapshot(
      total=total_recent_reqs,
      failed=sum(recent.failed for recent in recent_stats),
      avg_latency=(weighted_avg_latency_sum / total_recent_reqs)
                  if total_recent_reqs else None,
      pb_reqs=sum(recent.pb_reqs for recent in recent_stats),
      rest_reqs=sum(recent.rest_reqs for recent in recent_stats),
      by_pb_method=by_pb_method_sum,
      by_rest_method=by_rest_method_sum,
      by_pb_status=by_pb_status_sum,
      by_rest_status=by_rest_status_sum
    )

  @gen.coroutine
  def get_current(self):
    start_time = time.time()
    # Find all taskqueue servers
    tq_instances = proxy_stats.get_service_instances(
      proxy_stats.HAPROXY_SERVICES_STATS_SOCKET_PATH, "TaskQueue"
    )
    # Query all TQ servers
    instances_responses = yield [
      self.fetch_stats_from_instance(ip_port)
      for ip_port in tq_instances
    ]
    # Select successful
    instances_stats = [
      stats_or_err for stats_or_err in instances_responses
      if isinstance(stats_or_err, InstanceStatsSnapshot)
    ]
    # Select failures
    failures = [
      stats_or_err for stats_or_err in instances_responses
      if isinstance(stats_or_err, FailureSnapshot)
    ]
    # Prepare service stats
    current_reqs = sum(server.current_requests for server in instances_stats)
    total_cumulative = self.summarise_cumulative(instances_stats)
    total_recent = self.summarise_recent(instances_stats)
    instances_count = len(instances_stats)
    stats = TaskqueueServiceStatsSnapshot(
      utc_timestamp=int(time.time()),
      current_requests=current_reqs,
      cumulative=total_cumulative,
      recent=total_recent,
      instances=instances_stats,
      instances_count=instances_count,
      failures=failures
    )
    logging.info(
      "Fetched Taskqueue server stats from {nodes} instances in {elapsed:.1f}s."
      .format(nodes=len(instances_stats), elapsed=time.time() - start_time)
    )
    raise gen.Return(stats)


taskqueue_stats_source = TaskqueueStatsSource()
