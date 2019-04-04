import http
import inspect
import logging
import time
from datetime import datetime

from aiohttp import web

from appscale.common import appscale_info
from appscale.hermes.constants import SECRET_HEADER, ACCEPTABLE_STATS_AGE
from appscale.hermes.converter import (
  stats_to_dict, IncludeLists, WrongIncludeLists
)

logger = logging.getLogger(__name__)


@web.middleware
async def verify_secret_middleware(request, handler):
  """ Security middleware for secret verification.

  Args:
    request: an instance of Request.
    handler: a callable handler for further request processing.
  Return:
    403 Response if secret is incorrect,
    Response provided by handler otherwise.
  """
  if request.headers.get(SECRET_HEADER) != appscale_info.get_secret():
    logger.warn("Received bad secret from {client}"
                .format(client=request.remote))
    return web.Response(status=http.HTTPStatus.FORBIDDEN,
                        reason="Bad secret")
  return await handler(request)


def get_default_include_lists():
  """ Creates an instance of IncludeLists with default values.
  It is not a constant because all model classes should be imported before
  creating an instance of IncludeLists.
  We're planning to get rid of complicated include lists logic
  by splitting composite models into smaller.
  """
  return IncludeLists({
    # Node stats
    'node': ['utc_timestamp', 'cpu', 'memory',
             'partitions_dict', 'loadavg'],
    'node.cpu': ['percent', 'count'],
    'node.memory': ['available', 'total'],
    'node.partition': ['free', 'used'],
    'node.loadavg': ['last_5min'],
    # Processes stats
    'process': ['monit_name', 'unified_service_name', 'application_id',
                'port', 'cpu', 'memory', 'children_stats_sum'],
    'process.cpu': ['user', 'system', 'percent'],
    'process.memory': ['resident', 'virtual', 'unique'],
    'process.children_stats_sum': ['cpu', 'memory'],
    # Proxies stats
    'proxy': ['name', 'unified_service_name', 'application_id',
              'frontend', 'backend', 'servers_count'],
    'proxy.frontend': ['bin', 'bout', 'scur', 'smax', 'rate',
                       'req_rate', 'req_tot', 'hrsp_4xx', 'hrsp_5xx'],
    'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
    # Taskqueue service stats
    'taskqueue': ['utc_timestamp', 'current_requests', 'cumulative', 'recent',
                  'instances_count', 'failures'],
    'taskqueue.instance': ['start_timestamp_ms', 'current_requests',
                           'cumulative', 'recent'],
    'taskqueue.cumulative': ['total', 'failed', 'pb_reqs', 'rest_reqs'],
    'taskqueue.recent': ['total', 'failed', 'avg_latency',
                         'pb_reqs', 'rest_reqs'],
    # RabbitMQ stats
    'rabbitmq': ['utc_timestamp', 'disk_free_alarm', 'mem_alarm', 'name',
                 'partitions'],
    # Push queue stats
    'queue': ['name', 'messages'],
    # Cassandra stats
    'cassandra': ['utc_timestamp', 'nodes', 'missing_nodes', 'unknown_nodes'],
    # Cassandra node stats
    'cassandra.node': ['address', 'status', 'state', 'load', 'owns_pct',
                       'tokens_num'],
  })


class LocalStatsHandler:
  """ Handler for getting current local stats of specific kind.
  """
  def __init__(self, stats_source):
    """ Initializes request handler for providing current stats.

    Args:
      stats_source: an object with method get_current.
    """
    self.stats_source = stats_source
    self.cached_snapshot = None
    self.default_include_lists = get_default_include_lists()

  async def __call__(self, request):
    """ Handles HTTP request.

    Args:
      request: an instance of Request.
    Returns:
      An instance of Resposne.
    """
    if request.has_body:
      payload = await request.json()
    else:
      payload = {}
    include_lists = payload.get('include_lists')
    max_age = payload.get('max_age', ACCEPTABLE_STATS_AGE)

    if include_lists is not None:
      try:
        include_lists = IncludeLists(include_lists)
      except WrongIncludeLists as err:
        logger.warn("Bad request from {client} ({error})"
                    .format(client=request.remote, error=err))
        return web.Response(status=http.HTTPStatus.BAD_REQUEST,
                            reason='Wrong include_lists', text=str(err))
    else:
      include_lists = self.default_include_lists

    snapshot = None

    # Try to use cached snapshot
    if self.cached_snapshot:
      now = time.time()
      acceptable_time = now - max_age
      if self.cached_snapshot.utc_timestamp >= acceptable_time:
        snapshot = self.cached_snapshot
        logger.info("Returning cached snapshot with age {:.2f}s"
                    .format(now-self.cached_snapshot.utc_timestamp))

    if not snapshot:
      snapshot = self.stats_source.get_current()
      if inspect.isawaitable(snapshot):
        snapshot = await snapshot
      self.cached_snapshot = snapshot

    return web.json_response(stats_to_dict(snapshot, include_lists))


class ClusterStatsHandler:
  """ Handler for getting current cluster stats of specific kind.
  """

  def __init__(self, stats_source):
    """ Initializes request handler for providing current stats.

    Args:
      stats_source: an object with method get_current.
    """
    self.stats_source = stats_source
    self.cached_snapshots = {}
    self.default_include_lists = get_default_include_lists()

  async def __call__(self, request):
    """ Handles HTTP request.

    Args:
      request: an instance of Request.
    Returns:
      An instance of Response.
    """
    if request.has_body:
      payload = await request.json()
    else:
      payload = {}
    include_lists = payload.get('include_lists')
    max_age = payload.get('max_age', ACCEPTABLE_STATS_AGE)

    if include_lists is not None:
      try:
        include_lists = IncludeLists(include_lists)
      except WrongIncludeLists as err:
        logger.warn("Bad request from {client} ({error})"
                    .format(client=request.remote, error=err))
        return web.Response(status=http.HTTPStatus.BAD_REQUEST,
                            reason='Wrong include_lists', text=str(err))
    else:
      include_lists = self.default_include_lists

    newer_than = time.mktime(datetime.now().timetuple()) - max_age

    if (not self.default_include_lists or
        include_lists.is_subset_of(self.default_include_lists)):
      # If user didn't specify any non-default fields we can use local cache
      fresh_local_snapshots = {
        node_ip: snapshot
        for node_ip, snapshot in self.cached_snapshots.items()
        if max_age and snapshot.utc_timestamp > newer_than
      }
      if fresh_local_snapshots:
        logger.debug("Returning cluster stats with {} cached snapshots"
                     .format(len(fresh_local_snapshots)))
    else:
      fresh_local_snapshots = {}

    new_snapshots_dict, failures = (
      await self.stats_source.get_current(
        max_age=max_age, include_lists=include_lists,
        exclude_nodes=list(fresh_local_snapshots.keys())
      )
    )

    # Put new snapshots to local cache
    self.cached_snapshots.update(new_snapshots_dict)

    # Extend fetched snapshots dict with fresh local snapshots
    new_snapshots_dict.update(fresh_local_snapshots)

    rendered_snapshots = {
      node_ip: stats_to_dict(snapshot, include_lists)
      for node_ip, snapshot in new_snapshots_dict.items()
    }

    return web.json_response({
      "stats": rendered_snapshots,
      "failures": failures
    })


def not_found(reason):
  """
  This function creates handler is aimed to stub unavailable route.
  Hermes master has some extra routes which are not available on slaves,
  also Hermes stats can work in lightweight or verbose mode and verbose
  mode has extra routes.
  This handlers is configured with a reason why specific resource
  is not available on the instance of Hermes.
  """
  def handler(request):
    return web.Response(status=http.HTTPStatus.NOT_FOUND, reason=reason)
  return handler
