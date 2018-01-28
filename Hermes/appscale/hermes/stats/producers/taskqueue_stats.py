""" Fetches TaskQueue service statistics. """
import base64
import json
import logging
import socket
import time

import attr
from tornado.httpclient import AsyncHTTPClient

from appscale.hermes.stats.converter import include_list_name, Meta

# The endpoint used for retrieving node stats.
STATS_ENDPOINT = '/service-stats'


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


@include_list_name('taskqueue.instance')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class InstanceStatsSnapshot(object):
  """ Stats reported for each TaskQueue instance. """
  start_timestamp_ms = attr.ib()
  current_requests = attr.ib()
  cumulative = attr.ib(metadata={Meta.ENTITY: CumulativeStatsSnapshot})
  recent = attr.ib(metadata={Meta.ENTITY: RecentStatsSnapshot})


@include_list_name('taskqueue.instance')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class TaskqueueInstanceStatsSnapshot(object):
  """ Stats reported for TaskQueue service. """
  current_requests = attr.ib()
  cumulative = attr.ib(metadata={Meta.ENTITY: CumulativeStatsSnapshot})
  recent = attr.ib(metadata={Meta.ENTITY: RecentStatsSnapshot})
  instances = attr.ib(metadata={Meta.ENTITY_LIST: InstanceStatsSnapshot})
  instances_count = attr.ib()
  failures = attr.ib()
