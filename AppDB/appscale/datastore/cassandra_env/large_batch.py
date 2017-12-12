import sys
import uuid

from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.cassandra_env.retry_policies import (
  BASIC_RETRIES, NO_RETRIES)
from appscale.datastore.cassandra_env.tornado_cassandra import TornadoCassandra
from appscale.datastore.cassandra_env.utils import (
  deletions_for_entity, mutations_for_entity)
from appscale.datastore.dbconstants import TRANSIENT_CASSANDRA_ERRORS
from appscale.datastore.utils import logger, tx_partition

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb


class BatchNotFound(Exception):
  """ Indicates that the batch status is not defined. """


class BatchNotOwned(Exception):
  """ Indicates that a different process owns the batch. """
  pass


class FailedBatch(Exception):
  """ Indicates that the datastore failed to apply a large batch. """
  pass


class LargeBatch(object):
  def __init__(self, session, project, txid):
    """ Create a new LargeBatch object.

    Args:
      session: A cassandra-driver session.
      project: A string specifying a project ID.
      txid: An integer specifying a transaction ID.
    """
    self.session = session
    self.project = project
    self.txid = txid

    # Create an identifier so that it's possible to check if operations succeed
    # after a timeout.
    self.op_id = uuid.uuid4()

    # This value is used when claiming an existing failed batch.
    self.read_op_id = None

    # Indicates if the batch has been applied.
    self.applied = False

  def is_applied(self, retries=5):
    """ Fetch the status of the batch.

    Args:
      retries: The number of times to retry after failures.
    Returns:
      A boolean indicating whether or not the batch has been applied.
    Raises:
      BatchNotFound if the batch cannot be found.
      BatchNotOwned if a different process owns the batch.
    """
    get_status = """
      SELECT applied, op_id FROM batch_status
      WHERE txid_hash = %(txid_hash)s
    """
    query = SimpleStatement(get_status, retry_policy=BASIC_RETRIES,
                            consistency_level=ConsistencyLevel.SERIAL)
    parameters = {'txid_hash': tx_partition(self.project, self.txid)}

    try:
      result = self.session.execute(query, parameters=parameters)[0]
      if result.op_id != self.op_id:
        self.read_op_id = result.op_id
        raise BatchNotOwned(
          '{} does not match {}'.format(self.op_id, result.op_id))
      return result.applied
    except TRANSIENT_CASSANDRA_ERRORS:
      retries_left = retries - 1
      if retries_left < 0:
        raise

      logger.debug('Unable to read batch status. Retrying.')
      return self.is_applied(retries=retries_left)
    except IndexError:
      raise BatchNotFound(
        'Batch for {}:{} not found'.format(self.project, self.txid))

  def start(self, retries=5):
    """ Mark the batch as being in progress.

    Args:
      retries: The number of times to retry after failures.
    Raises:
      FailedBatch if the batch cannot be marked as being started.
    """
    if retries < 0:
      raise FailedBatch('Retries exhausted while starting batch')

    insert = SimpleStatement("""
      INSERT INTO batch_status (txid_hash, applied, op_id)
      VALUES (%(txid_hash)s, False, %(op_id)s)
      IF NOT EXISTS
    """, retry_policy=NO_RETRIES)
    parameters = {'txid_hash': tx_partition(self.project, self.txid),
                  'op_id': self.op_id}

    try:
      result = self.session.execute(insert, parameters)
    except TRANSIENT_CASSANDRA_ERRORS:
      return self.start(retries=retries - 1)

    if result.was_applied:
      return

    # Make sure this process was responsible for the insert.
    try:
      self.is_applied()
    except (BatchNotOwned, TRANSIENT_CASSANDRA_ERRORS) as batch_failure:
      raise FailedBatch(str(batch_failure))
    except BatchNotFound:
      return self.start(retries=retries - 1)

  def set_applied(self, retries=5):
    """ Mark the batch as being applied.

    Args:
      retries: The number of times to retry after failures.
    Raises:
      FailedBatch if the batch cannot be marked as applied.
    """
    if retries < 0:
      raise FailedBatch('Retries exhausted while updating batch')

    update_status = SimpleStatement("""
      UPDATE batch_status
      SET applied = True
      WHERE txid_hash = %(txid_hash)s
      IF op_id = %(op_id)s
    """, retry_policy=NO_RETRIES)
    parameters = {'txid_hash': tx_partition(self.project, self.txid),
                  'op_id': self.op_id}

    try:
      result = self.session.execute(update_status, parameters)
      if result.was_applied:
        self.applied = True
        return
    except TRANSIENT_CASSANDRA_ERRORS:
      pass  # Application is confirmed below.

    try:
      if self.is_applied():
        self.applied = True
        return
      return self.set_applied(retries=retries - 1)
    except (BatchNotFound, BatchNotOwned, TRANSIENT_CASSANDRA_ERRORS) as error:
      raise FailedBatch(str(error))

  def cleanup(self, retries=5):
    """ Clean up the batch status entry.

    Args:
      retries: The number of times to retry after failures.
    Raises:
      FailedBatch if the batch cannot be marked as applied.
    """
    if retries < 0:
      raise FailedBatch('Retries exhausted while cleaning up batch')

    clear_status = SimpleStatement("""
      DELETE FROM batch_status
      WHERE txid_hash = %(txid_hash)s
      IF op_id = %(op_id)s
    """, retry_policy=NO_RETRIES)
    parameters = {'txid_hash': tx_partition(self.project, self.txid),
                  'op_id': self.op_id}

    try:
      result = self.session.execute(clear_status, parameters)
    except TRANSIENT_CASSANDRA_ERRORS:
      return self.cleanup(retries=retries - 1)

    if not result.was_applied:
      raise FailedBatch(
        'Unable to clean up batch for {}:{}'.format(self.project, self.txid))

  def claim(self):
    """ Claim a batch so that other processes don't work on it.

    Raises:
      FailedBatch if the batch cannot be claimed.
    """
    try:
      if self.is_applied():
        self.applied = True
    except TRANSIENT_CASSANDRA_ERRORS as error:
      raise FailedBatch(str(error))
    except BatchNotOwned:
      # This process does not own the batch yet.
      pass
    except BatchNotFound:
      # Make sure another process doesn't try to start.
      return self.start()

    update_id = SimpleStatement("""
      UPDATE batch_status
      SET op_id = %(new_op_id)s
      WHERE txid_hash = %(txid_hash)s
      IF op_id = %(old_op_id)s
    """, retry_policy=NO_RETRIES)
    parameters = {'txid_hash': tx_partition(self.project, self.txid),
                  'new_op_id': self.op_id, 'old_op_id': self.read_op_id}

    try:
      result = self.session.execute(update_id, parameters)
      assert result.was_applied
    except (TRANSIENT_CASSANDRA_ERRORS, AssertionError):
      raise FailedBatch('Unable to claim batch')


class BatchResolver(object):
  """ Resolves large batches. """
  def __init__(self, project_id, db_access):
    """ Creates a new BatchResolver.

    Args:
      project_id: A string specifying a project ID.
      db_access: A DatastoreProxy.
    """
    self.project_id = project_id

    self._db_access = db_access
    self._session = self._db_access.session
    self._tornado_cassandra = TornadoCassandra(self._session)
    self._prepared_statements = {}

  @gen.coroutine
  def resolve(self, txid, composite_indexes):
    """ Resolves a large batch for a given transaction.

    Args:
      txid: An integer specifying a transaction ID.
      composite_indexes: A list of CompositeIndex objects.
    """
    txid_hash = tx_partition(self.project_id, txid)
    new_op_id = uuid.uuid4()
    try:
      batch_status = yield self._get_status(txid_hash)
    except BatchNotFound:
      # Make sure another process doesn't try to commit the transaction.
      yield self._insert(txid_hash, new_op_id)
      raise gen.Return()

    old_op_id = batch_status.op_id
    yield self._update_op_id(txid_hash, batch_status.applied, old_op_id,
                             new_op_id)

    if batch_status.applied:
      # Make sure all the mutations in the batch have been applied.
      yield self._apply_mutations(txid, composite_indexes)

  @gen.coroutine
  def cleanup(self, txid):
    """ Cleans up the metadata from the finished batch.

    Args:
      txid: An integer specifying a transaction ID.
    """
    txid_hash = tx_partition(self.project_id, txid)
    yield self._delete_mutations(txid)
    yield self._delete_status(txid_hash)

  def _get_prepared(self, statement):
    """ Caches prepared statements.

    Args:
      statement: A string containing a Cassandra statement.
    """
    if statement not in self._prepared_statements:
      self._prepared_statements[statement] = self._session.prepare(statement)

    return self._prepared_statements[statement]

  @gen.coroutine
  def _get_status(self, txid_hash):
    """ Gets the current status of a large batch.

    Args:
      txid_hash: A byte array identifying the transaction.
    Returns:
      A Cassandra result for the batch entry.
    """
    statement = self._get_prepared("""
      SELECT applied, op_id FROM batch_status
      WHERE txid_hash = ?
    """)
    bound_statement = statement.bind((txid_hash,))
    bound_statement.consistency_level = ConsistencyLevel.SERIAL
    bound_statement.retry_policy = BASIC_RETRIES
    results = yield self._tornado_cassandra.execute(bound_statement)
    try:
      raise gen.Return(results[0])
    except IndexError:
      raise BatchNotFound('Batch not found')

  @gen.coroutine
  def _insert(self, txid_hash, op_id):
    """ Claims the large batch.

    Args:
      txid_hash: A byte array identifying the transaction.
      op_id: A uuid4 specifying the process ID.
    """
    statement = self._get_prepared("""
      INSERT INTO batch_status (txid_hash, applied, op_id)
      VALUES (?, ?, ?)
      IF NOT EXISTS
    """)
    bound_statement = statement.bind((txid_hash, False, op_id))
    bound_statement.retry_policy = NO_RETRIES
    results = yield self._tornado_cassandra.execute(bound_statement)
    if not results[0].applied:
      raise BatchNotOwned('Another process started applying the transaction')

  @gen.coroutine
  def _select_mutations(self, txid):
    """ Fetches a list of the mutations for the batch.

    Args:
      txid: An integer specifying a transaction ID.
    Returns:
      An iterator of Cassandra results.
    """
    statement = self._get_prepared("""
      SELECT old_value, new_value FROM batches
      WHERE app = ? AND transaction = ?
    """)
    bound_statement = statement.bind((self.project_id, txid))
    bound_statement.retry_policy = BASIC_RETRIES
    results = yield self._tornado_cassandra.execute(bound_statement)
    raise gen.Return(results)

  @gen.coroutine
  def _apply_mutations(self, txid, composite_indexes):
    """ Applies all the mutations in the batch.

    Args:
      txid: An integer specifying a transaction ID.
      composite_indexes: A list of CompositeIndex objects.
    """
    results = yield self._select_mutations(txid)
    futures = []
    for result in results:
      old_entity = result.old_value
      if old_entity is not None:
        old_entity = entity_pb.EntityProto(old_entity)

      new_entity = result.new_value

      if new_entity is None:
        mutations = deletions_for_entity(old_entity, composite_indexes)
      else:
        new_entity = entity_pb.EntityProto(new_entity)
        mutations = mutations_for_entity(new_entity, txid, old_entity,
                                         composite_indexes)

      statements_and_params = self._db_access.statements_for_mutations(
        mutations, txid)
      for statement, params in statements_and_params:
        futures.append(self._tornado_cassandra.execute(statement, params))

    for future in futures:
      yield future

  @gen.coroutine
  def _update_op_id(self, txid_hash, applied_status, old_op_id, new_op_id):
    """ Claims a batch that is in progress.

    Args:
      txid_hash: A byte array identifying the transaction.
      applied_status: A boolean indicating that the batch has been committed.
      old_op_id: A uuid4 specifying the last read process ID.
      new_op_id: A uuid4 specifying the new process ID.
    """
    statement = self._get_prepared("""
      UPDATE batch_status
      SET op_id = ?
      WHERE txid_hash = ?
      IF op_id = ?
      AND applied = ?
    """)
    params = (new_op_id, txid_hash, old_op_id, applied_status)
    bound_statement = statement.bind(params)
    bound_statement.retry_policy = NO_RETRIES
    results = yield self._tornado_cassandra.execute(bound_statement)
    if not results[0].applied:
      raise BatchNotOwned('Batch status changed after checking')

  @gen.coroutine
  def _delete_mutations(self, txid):
    """ Removes mutation entries for the batch.

    Args:
      txid: An integer specifying a transaction ID.
    """
    statement = self._get_prepared("""
      DELETE FROM batches
      WHERE app = ? AND transaction = ?
    """)
    params = (self.project_id, txid)
    bound_statement = statement.bind(params)
    bound_statement.retry_policy = BASIC_RETRIES
    yield self._tornado_cassandra.execute(bound_statement)

  @gen.coroutine
  def _delete_status(self, txid_hash):
    """ Removes the batch status entry.

    Args:
      txid_hash: A byte array identifying a transaction.
    """
    statement = self._get_prepared("""
      DELETE FROM batch_status
      WHERE txid_hash = ?
      IF EXISTS
    """)
    bound_statement = statement.bind((txid_hash,))
    bound_statement.retry_policy = NO_RETRIES
    yield self._tornado_cassandra.execute(bound_statement)
