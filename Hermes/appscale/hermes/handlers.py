import json
import logging
import time
from datetime import datetime

from tornado import gen
from tornado.options import options
from tornado.web import RequestHandler

from appscale.hermes.constants import SECRET_HEADER, HTTP_Codes
from appscale.hermes.constants import ACCEPTABLE_STATS_AGE
from appscale.hermes.converter import stats_to_dict, \
  IncludeLists, WrongIncludeLists


class CurrentStatsHandler(RequestHandler):
  """ Handler for getting current local stats of specific kind.
  """

  def initialize(self, source, default_include_lists):
    self._stats_source = source
    self._default_include_lists = default_include_lists
    self._snapshot = None

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

    need_refresh = (
      not self._snapshot or
      (self._snapshot.utc_timestamp <= newer_than and max_age)
    )
    if need_refresh:
      self._snapshot = self._stats_source.get_current()
      if isinstance(self._snapshot, gen.Future):
        self._snapshot = yield self._snapshot

    json.dump(stats_to_dict(self._snapshot, include_lists), self)


class CurrentClusterStatsHandler(RequestHandler):
  """ Handler for getting current stats of specific kind.
  """
  def initialize(self, source, default_include_lists):
    self._current_cluster_stats_source = source
    self._default_include_lists = default_include_lists
    self._snapshots = {}

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
        node_ip: snapshot for node_ip, snapshot in self._snapshots.iteritems()
        if max_age and snapshot.utc_timestamp > newer_than
      }
    else:
      fresh_local_snapshots = {}

    new_snapshots_dict, failures = (
      yield self._current_cluster_stats_source.get_current(
        max_age=max_age, include_lists=include_lists,
        exclude_nodes=fresh_local_snapshots.keys()
      )
    )

    # Put new snapshots to local cache
    self._snapshots.update(new_snapshots_dict)

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

class Respond404Handler(RequestHandler):
  """
  This class is aimed to stub unavailable route.
  Hermes master has some extra routes which are not available on slaves,
  also Hermes stats can work in lightweight or verbose mode and verbose
  mode has extra routes.
  This handlers is configured with a reason why specific resource
  is not available on the instance of Hermes.
  """

  def initialize(self, reason):
    self.reason = reason

  def get(self):
    self.set_status(404, self.reason)
