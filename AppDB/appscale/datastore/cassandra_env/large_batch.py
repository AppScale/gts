import uuid

from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from .retry_policies import (BASIC_RETRIES,
                             NO_RETRIES)
from ..dbconstants import TRANSIENT_CASSANDRA_ERRORS
from ..utils import (logger,
                     tx_partition)


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
