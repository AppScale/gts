import sys
import uuid

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from cassandra.query import (
  ConsistencyLevel,
  SimpleStatement
)
from tornado import gen

from appscale.datastore.cassandra_env.retry_policies import NO_RETRIES
from appscale.datastore.cassandra_env.tornado_cassandra import TornadoCassandra
from appscale.datastore.dbconstants import (
  AppScaleBadArg,
  AppScaleDBConnectionError,
  TRANSIENT_CASSANDRA_ERRORS
)
from appscale.datastore.utils import logger

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore.datastore_stub_util import (
  _MAX_SCATTERED_COUNTER,
  _MAX_SEQUENTIAL_COUNTER,
  ToScatteredId
)

# The number of scattered IDs the datastore should reserve at a time.
DEFAULT_RESERVATION_SIZE = 10000


class ReservationFailed(Exception):
  """ Indicates that a block of IDs could not be reserved. """
  pass


class EntityIDAllocator(object):
  """ Keeps track of reserved entity IDs for a project. """

  def __init__(self, session, project, scattered=False):
    """ Creates a new EntityIDAllocator object.

    Args:
      session: A cassandra-drivers session object.
      project: A string specifying a project ID.
    """
    self.project = project
    self.session = session
    self.tornado_cassandra = TornadoCassandra(self.session)
    self.scattered = scattered
    if scattered:
      self.max_allowed = _MAX_SCATTERED_COUNTER
    else:
      self.max_allowed = _MAX_SEQUENTIAL_COUNTER

    # Allows the allocator to avoid making unnecessary Cassandra requests when
    # setting the minimum counter value.
    self._last_reserved_cache = None

  @gen.coroutine
  def _ensure_entry(self, retries=5):
    """ Ensures an entry exists for a reservation.

    Args:
      retries: The number of times to retry the insert.
    Raises:
      AppScaleDBConnectionError if the insert is tried too many times.
    """
    if retries < 0:
      raise AppScaleDBConnectionError('Unable to create reserved_ids entry')

    logger.debug('Creating reserved_ids entry for {}'.format(self.project))
    insert = SimpleStatement("""
      INSERT INTO reserved_ids (project, scattered, last_reserved, op_id)
      VALUES (%(project)s, %(scattered)s, 0, uuid())
      IF NOT EXISTS
    """, retry_policy=NO_RETRIES)
    parameters = {'project': self.project, 'scattered': self.scattered}
    try:
      yield self.tornado_cassandra.execute(insert, parameters)
    except TRANSIENT_CASSANDRA_ERRORS:
      yield self._ensure_entry(retries=retries-1)

  @gen.coroutine
  def _get_last_reserved(self):
    """ Retrieves the last entity ID that was reserved.

    Returns:
      An integer specifying an entity ID.
    """
    get_reserved = SimpleStatement("""
      SELECT last_reserved
      FROM reserved_ids
      WHERE project = %(project)s
      AND scattered = %(scattered)s
    """, consistency_level=ConsistencyLevel.SERIAL)
    parameters = {'project': self.project, 'scattered': self.scattered}
    try:
      results = yield self.tornado_cassandra.execute(get_reserved, parameters)
      result = results[0]
    except IndexError:
      yield self._ensure_entry()
      last_reserved = yield self._get_last_reserved()
      raise gen.Return(last_reserved)

    self._last_reserved_cache = result.last_reserved
    raise gen.Return(result.last_reserved)

  @gen.coroutine
  def _get_last_op_id(self):
    """ Retrieve the op_id that was last written during a reservation.

    Returns:
      A UUID4 containing the latest op_id.
    """
    get_op_id = SimpleStatement("""
      SELECT op_id
      FROM reserved_ids
      WHERE project = %(project)s
      AND scattered = %(scattered)s
    """, consistency_level=ConsistencyLevel.SERIAL)
    parameters = {'project': self.project, 'scattered': self.scattered}
    results = yield self.tornado_cassandra.execute(get_op_id, parameters)
    raise gen.Return(results[0].op_id)

  @gen.coroutine
  def _set_reserved(self, last_reserved, new_reserved):
    """ Update the last reserved value to allocate that block.

    Args:
      last_reserved: An integer specifying the last reserved value.
      new_reserved: An integer specifying the new reserved value.
    Raises:
      ReservationFailed if the update statement fails.
    """
    op_id = uuid.uuid4()
    set_reserved = SimpleStatement("""
      UPDATE reserved_ids
      SET last_reserved = %(new_reserved)s,
          op_id = %(op_id)s
      WHERE project = %(project)s
      AND scattered = %(scattered)s
      IF last_reserved = %(last_reserved)s
    """, retry_policy=NO_RETRIES)
    parameters = {
      'last_reserved': last_reserved, 'new_reserved': new_reserved,
      'project': self.project, 'scattered': self.scattered, 'op_id': op_id}
    try:
      result = yield self.tornado_cassandra.execute(set_reserved, parameters)
    except TRANSIENT_CASSANDRA_ERRORS as error:
      last_op_id = yield self._get_last_op_id()
      if last_op_id == op_id:
        return
      raise ReservationFailed(str(error))

    if not result.was_applied:
      raise ReservationFailed('Last reserved value changed')

    self._last_reserved_cache = new_reserved

  @gen.coroutine
  def allocate_size(self, size, retries=5, min_counter=None):
    """ Reserve a block of IDs for this project.

    Args:
      size: The number of IDs to reserve.
      retries: The number of times to retry the reservation.
      min_counter: The minimum counter value that should be reserved.
    Returns:
      A tuple of integers specifying the start and end ID.
    Raises:
      AppScaleDBConnectionError if the reservation is tried too many times.
      AppScaleBadArg if the ID space has been exhausted.
    """
    if retries < 0:
      raise AppScaleDBConnectionError('Unable to reserve new block')

    try:
      last_reserved = yield self._get_last_reserved()
    except TRANSIENT_CASSANDRA_ERRORS:
      raise AppScaleDBConnectionError('Unable to get last reserved ID')

    if min_counter is None:
      new_reserved = last_reserved + size
    else:
      new_reserved = max(last_reserved, min_counter) + size

    if new_reserved > self.max_allowed:
      raise AppScaleBadArg('Exceeded maximum allocated IDs')

    try:
      yield self._set_reserved(last_reserved, new_reserved)
    except ReservationFailed:
      start_id, end_id = yield self.allocate_size(size, retries=retries-1)
      raise gen.Return((start_id, end_id))

    start_id = last_reserved + 1
    end_id = new_reserved
    raise gen.Return((start_id, end_id))

  @gen.coroutine
  def allocate_max(self, max_id, retries=5):
    """ Reserves all IDs up to the one given.

    Args:
      max_id: An integer specifying the maximum ID to allocated.
      retries: The number of times to retry the reservation.
    Returns:
      A tuple of integers specifying the start and end ID.
    Raises:
      AppScaleDBConnectionError if the reservation is tried too many times.
      AppScaleBadArg if the ID space has been exhausted.
    """
    if retries < 0:
      raise AppScaleDBConnectionError('Unable to reserve new block')

    if max_id > self.max_allowed:
      raise AppScaleBadArg('Exceeded maximum allocated IDs')

    try:
      last_reserved = yield self._get_last_reserved()
    except TRANSIENT_CASSANDRA_ERRORS:
      raise AppScaleDBConnectionError('Unable to get last reserved ID')

    # Instead of returning an error, the API returns an invalid range.
    if last_reserved >= max_id:
      raise gen.Return((last_reserved + 1, last_reserved))

    try:
      yield self._set_reserved(last_reserved, max_id)
    except ReservationFailed:
      start_id, end_id = yield self.allocate_max(max_id, retries=retries-1)
      raise gen.Return((start_id, end_id))

    start_id = last_reserved + 1
    end_id = max_id
    raise gen.Return((start_id, end_id))

  @gen.coroutine
  def set_min_counter(self, counter):
    """ Ensures the counter is at least as large as the given value.

    Args:
      counter: An integer specifying the minimum counter value.
    """
    if (self._last_reserved_cache is not None and
        self._last_reserved_cache >= counter):
      return

    yield self.allocate_max(counter)


class ScatteredAllocator(EntityIDAllocator):
  """ An iterator that generates evenly-distributed entity IDs. """
  def __init__(self, session, project):
    """ Creates a new ScatteredAllocator instance. Each project should just
    have one instance since it reserves a large block of IDs at a time.

    Args:
      session: A cassandra-driver session.
      project: A string specifying a project ID.
    """
    super(ScatteredAllocator, self).__init__(session, project, scattered=True)

    # The range that this datastore has already reserved for scattered IDs.
    self.start_id = None
    self.end_id = None

  def __iter__(self):
    """ Returns a new iterator object. """
    return self

  @gen.coroutine
  def next(self):
    """ Generates a new entity ID.

    Returns:
      An integer specifying an entity ID.
    """
    # This function will require a tornado lock when made asynchronous.
    if self.start_id is None or self.start_id > self.end_id:
      size = DEFAULT_RESERVATION_SIZE
      self.start_id, self.end_id = yield self.allocate_size(size)

    next_id = ToScatteredId(self.start_id)
    self.start_id += 1
    raise gen.Return(next_id)

  @gen.coroutine
  def set_min_counter(self, counter):
    """ Ensures the counter is at least as large as the given value.

    Args:
      counter: An integer specifying the minimum counter value.
    """
    # If there's no chance the ID could be allocated, do nothing.
    if self.start_id is not None and self.start_id >= counter:
      return

    # If the ID is in the allocated block, adjust the block.
    if self.end_id is not None and self.end_id > counter:
      self.start_id = counter

    # If this server has never allocated a block, adjust the minimum for
    # future blocks.
    if self.start_id is None:
      if (self._last_reserved_cache is not None and
          self._last_reserved_cache >= counter):
        return

      yield self.allocate_max(counter)
      return

    # If this server has allocated a block, but the relevant ID is greater than
    # the end ID, get a new block that starts at least as high as the ID.
    self.start_id, self.end_id = yield self.allocate_size(
      DEFAULT_RESERVATION_SIZE, min_counter=counter
    )
