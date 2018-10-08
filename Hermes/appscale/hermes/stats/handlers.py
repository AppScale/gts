import json
import logging
import time
from datetime import datetime

from tornado import gen
from tornado.options import options
from tornado.web import RequestHandler

from appscale.hermes.constants import SECRET_HEADER, HTTP_Codes
from appscale.hermes.stats.constants import ACCEPTABLE_STATS_AGE
from appscale.hermes.stats.converter import stats_to_dict, \
  IncludeLists, WrongIncludeLists


class CurrentStatsHandler(RequestHandler):
  """ Handler for getting current local stats of specific kind.
  """

  def initialize(self, source, default_include_lists, cache_container):
    """ Initializes RequestHandler for handling a single request.

    Args:
      source: an object with method get_current.
      default_include_lists: an instance of IncludeLists to use as default.
      cache_container: a list containing a single element - cached snapshot.
    """
    self._stats_source = source
    self._default_include_lists = default_include_lists
    self._cache_container = cache_container

  @property
  def _cached_snapshot(self):
    return self._cache_container[0]

  @_cached_snapshot.setter
  def _cached_snapshot(self, newer_snapshot):
    self._cache_container[0] = newer_snapshot

  @gen.coroutine
  def get(self):
    if self.request.headers.get(SECRET_HEADER) != options.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(HTTP_Codes.HTTP_DENIED, "Bad secret")
      return
    if self.request.body:
      payload = json.loads(self.request.body)
    else:
      payload = {}
    include_lists = payload.get('include_lists')
    max_age = payload.get('max_age', ACCEPTABLE_STATS_AGE)

    if include_lists is not None:
      try:
        include_lists = IncludeLists(include_lists)
      except WrongIncludeLists as err:
        logging.warn("Bad request from {client} ({error})"
                     .format(client=self.request.remote_ip, error=err))
        json.dump({'error': str(err)}, self)
        self.set_status(HTTP_Codes.HTTP_BAD_REQUEST, 'Wrong include_lists')
        return
    else:
      include_lists = self._default_include_lists

    snapshot = None

    # Try to use cached snapshot
    if self._cached_snapshot:
      now = time.time()
      acceptable_time = now - max_age
      if self._cached_snapshot.utc_timestamp >= acceptable_time:
        snapshot = self._cached_snapshot
        logging.info("Returning cached snapshot with age {:.2f}s"
                     .format(now-self._cached_snapshot.utc_timestamp))

    if not snapshot:
      snapshot = self._stats_source.get_current()
      if isinstance(snapshot, gen.Future):
        snapshot = yield snapshot
      self._cached_snapshot = snapshot

    json.dump(stats_to_dict(snapshot, include_lists), self)


class CurrentClusterStatsHandler(RequestHandler):
  """ Handler for getting current stats of specific kind.
  """

  def initialize(self, source, default_include_lists, cache_container):
    """ Initializes RequestHandler for handling a single request.

    Args:
      source: an object with method get_current.
      default_include_lists: an instance of IncludeLists to use as default.
      cache_container: a dict with cached snapshots.
    """
    self._current_cluster_stats_source = source
    self._default_include_lists = default_include_lists
    self._cached_snapshots = cache_container

  @gen.coroutine
  def get(self):
    if self.request.headers.get(SECRET_HEADER) != options.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(HTTP_Codes.HTTP_DENIED, "Bad secret")
      return
    if self.request.body:
      payload = json.loads(self.request.body)
    else:
      payload = {}
    include_lists = payload.get('include_lists')
    max_age = payload.get('max_age', ACCEPTABLE_STATS_AGE)

    if include_lists is not None:
      try:
        include_lists = IncludeLists(include_lists)
      except WrongIncludeLists as err:
        logging.warn("Bad request from {client} ({error})"
                     .format(client=self.request.remote_ip, error=err))
        json.dump({'error': str(err)}, self)
        self.set_status(HTTP_Codes.HTTP_BAD_REQUEST, 'Wrong include_lists')
        return
    else:
      include_lists = self._default_include_lists

    newer_than = time.mktime(datetime.now().timetuple()) - max_age

    if (not self._default_include_lists or
        include_lists.is_subset_of(self._default_include_lists)):
      # If user didn't specify any non-default fields we can use local cache
      fresh_local_snapshots = {
        node_ip: snapshot
        for node_ip, snapshot in self._cached_snapshots.iteritems()
        if max_age and snapshot.utc_timestamp > newer_than
      }
      if fresh_local_snapshots:
        logging.debug("Returning cluster stats with {} cached snapshots"
                      .format(len(fresh_local_snapshots)))
    else:
      fresh_local_snapshots = {}

    new_snapshots_dict, failures = (
      yield self._current_cluster_stats_source.get_current(
        max_age=max_age, include_lists=include_lists,
        exclude_nodes=fresh_local_snapshots.keys()
      )
    )

    # Put new snapshots to local cache
    self._cached_snapshots.update(new_snapshots_dict)

    # Extend fetched snapshots dict with fresh local snapshots
    new_snapshots_dict.update(fresh_local_snapshots)

    rendered_snapshots = {
      node_ip: stats_to_dict(snapshot, include_lists)
      for node_ip, snapshot in new_snapshots_dict.iteritems()
    }

    json.dump({
      "stats": rendered_snapshots,
      "failures": failures
    }, self)
