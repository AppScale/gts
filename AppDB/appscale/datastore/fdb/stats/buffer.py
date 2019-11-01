import datetime
import logging
import monotonic
import random
import time
from collections import defaultdict

import six
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.locks import Lock as AsyncLock

from appscale.datastore.fdb.polling_lock import PollingLock
from appscale.datastore.fdb.stats.containers import ProjectStats
from appscale.datastore.fdb.stats.entities import fill_entities
from appscale.datastore.fdb.utils import (
  fdb, MAX_FDB_TX_DURATION, ResultIterator)

logger = logging.getLogger(__name__)


class ProjectStatsDir(object):
  """
  A ProjectStatsDir handles the encoding and decoding details for a project's
  stats entries.

  The directory path looks like (<project-dir>, 'stats').
  """
  DIR_NAME = u'stats'

  def __init__(self, directory):
    self.directory = directory

  def encode_last_versionstamp(self):
    return self.directory.pack((u'last-versionstamp',)), b'\x00' * 14

  def encode_last_timestamp(self):
    key = self.directory.pack((u'last-timestamp',))
    value = fdb.tuple.pack((int(time.time()),))
    return key, value

  def decode(self, kvs):
    project_stats = ProjectStats()
    last_timestamp = None
    for kv in kvs:
      path = self.directory.unpack(kv.key)
      section = path[0]
      if section == u'last-versionstamp':
        continue

      if section == u'last-timestamp':
        last_timestamp = datetime.datetime.utcfromtimestamp(
          fdb.tuple.unpack(kv.value)[0])
        continue

      project_stats.update_from_kv(section, path[1:], kv.value)

    return project_stats, last_timestamp

  @classmethod
  def directory_path(cls, project_id):
    return project_id, cls.DIR_NAME


class StatsBuffer(object):
  AVG_FLUSH_INTERVAL = 30

  BATCH_SIZE = 20

  SUMMARY_INTERVAL = 120

  _LOCK_KEY = u'stats-lock'

  def __init__(self, db, tornado_fdb, directory_cache, ds_access):
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._directory_cache = directory_cache
    self._buffer_lock = AsyncLock()
    self._ds_access = ds_access

    summary_lock_key = self._directory_cache.root_dir.pack((self._LOCK_KEY,))
    self._summary_lock = PollingLock(
      self._db, self._tornado_fdb, summary_lock_key)

    # By project
    self._last_summarized = {}

    # By project
    self._buffers = defaultdict(ProjectStats)

  def start(self):
    self._summary_lock.start()
    IOLoop.current().spawn_callback(self._periodic_flush)
    IOLoop.current().spawn_callback(self._periodic_summary)

  @gen.coroutine
  def update(self, project_id, mutations):
    with (yield self._buffer_lock.acquire()):
      for old_entry, new_entry, index_stats in mutations:
        self._buffers[project_id].update(old_entry, new_entry, index_stats)

  @gen.coroutine
  def _periodic_flush(self):
    while True:
      try:
        yield gen.sleep(random.random() * self.AVG_FLUSH_INTERVAL)
        yield self._flush()
      except Exception:
        # TODO: Exponential backoff here.
        logger.exception(u'Unexpected error while flushing stats')
        yield gen.sleep(random.random() * 2)
        continue

  @gen.coroutine
  def _flush(self):
    if all(buffer_.empty for buffer_ in six.itervalues(self._buffers)):
      return

    with (yield self._buffer_lock.acquire()):
      tr = self._db.create_transaction()
      for project_id, buffer_ in six.iteritems(self._buffers):
        stats_dir = yield self._project_stats_dir(tr, project_id)
        buffer_.apply(tr, stats_dir.directory)

        vs_key, vs_value = stats_dir.encode_last_versionstamp()
        tr.set_versionstamped_value(vs_key, vs_value)
        ts_key, ts_value = stats_dir.encode_last_timestamp()
        tr[ts_key] = ts_value

      yield self._tornado_fdb.commit(tr)
      logger.debug(u'Finished flushing stats')
      self._buffers.clear()

  @gen.coroutine
  def _periodic_summary(self):
    while True:
      try:
        yield self._summary_lock.acquire()
        tr = self._db.create_transaction()
        deadline = monotonic.monotonic() + MAX_FDB_TX_DURATION - 1
        last_summarized = {}

        # TODO: This can be made async.
        project_ids = self._directory_cache.root_dir.list(tr)

        summarized_projects = []
        for project_id in project_ids:
          stats_dir = yield self._project_stats_dir(tr, project_id)
          last_vs_key = stats_dir.encode_last_versionstamp()[0]
          last_versionstamp = yield self._tornado_fdb.get(
            tr, last_vs_key, snapshot=True)
          if (not last_versionstamp.present() or
              last_versionstamp.value == self._last_summarized.get(project_id)):
            continue

          last_summarized[project_id] = last_versionstamp.value
          results = yield ResultIterator(
            tr, self._tornado_fdb, stats_dir.directory.range(),
            snapshot=True).list()
          project_stats, last_timestamp = stats_dir.decode(results)
          entities = fill_entities(project_id, project_stats, last_timestamp)
          for pos in range(0, len(entities), self.BATCH_SIZE):
            yield [self._ds_access._upsert(tr, entity)
                   for entity in entities[pos:pos + self.BATCH_SIZE]]
            if monotonic.monotonic() > deadline:
              yield self._tornado_fdb.commit(tr)
              tr = self._db.create_transaction()
              deadline = monotonic.monotonic() + MAX_FDB_TX_DURATION - 1

          summarized_projects.append(project_id)

        yield self._tornado_fdb.commit(tr)
        self._last_summarized.update(last_summarized)
        if summarized_projects:
          logger.debug(u'Finished summarizing stats for '
                       u'{}'.format(summarized_projects))

        yield gen.sleep(self.SUMMARY_INTERVAL)
      except Exception:
        logger.exception(u'Unexpected error while summarizing stats')
        yield gen.sleep(random.random() * 20)

  @gen.coroutine
  def _project_stats_dir(self, tr, project_id):
    path = ProjectStatsDir.directory_path(project_id)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(ProjectStatsDir(directory))
