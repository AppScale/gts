""" Performs schema upgrades. """

import logging
import time

from cassandra.cluster import Cluster

from appscale.common import appscale_info
from ..cassandra_env.cassandra_interface import KEYSPACE
from ..cassandra_env.constants import LB_POLICY

# The number of rows to copy at a time.
BATCH_SIZE = 100

# The number of seconds to wait before logging progress.
LOGGING_INTERVAL = 5

logger = logging.getLogger(__name__)


def copy_column(session, table, key_column, old_column, new_column):
  """ Copies values from one column to another.

  Args:
    session: A cassandra-driver session.
    table: A string specifying the table.
    key_column: A string specifying the partition key column.
    old_column: A string specifying the column that should be copied from.
    new_column: A string specifying the column that should be copied to.
  """
  select = session.prepare("""
    SELECT {key}, {old_column}
    FROM {table}
    WHERE {key} > ?
    LIMIT {batch_size}
    ALLOW FILTERING
  """.format(table=table, key=key_column, old_column=old_column,
             batch_size=BATCH_SIZE))
  insert = session.prepare("""
    INSERT INTO {table} ({key}, {new_column})
    VALUES (?, ?)
  """.format(table=table, key=key_column, new_column=new_column))

  logger.info('Populating {}.{}'.format(table, new_column))
  start_row = ''
  last_logged = time.time()
  total_copied = 0
  while True:
    results = session.execute(select, (start_row,))
    futures = []
    last_row = None
    for result in results:
      futures.append(
        session.execute_async(insert, (result[0], result[1])))
      last_row = result[0]

    if last_row is None:
      break

    for future in futures:
      future.result()
      total_copied += 1

    if time.time() > last_logged + LOGGING_INTERVAL:
      logger.info('Copied {} rows'.format(total_copied))

    start_row = last_row

  logger.info('Copied {} rows'.format(total_copied))


def main():
  """ Performs schema upgrades. """
  hosts = appscale_info.get_db_ips()
  cluster = Cluster(hosts, load_balancing_policy=LB_POLICY)
  session = cluster.connect(KEYSPACE)

  table = 'group_updates'
  column = 'last_update'
  temp_column = 'last_update_temp'
  key_column = 'group'
  tables = cluster.metadata.keyspaces[KEYSPACE].tables

  assert table in tables, 'The table {} was not found'.format(table)

  columns = tables[table].columns
  assert column in columns or temp_column in columns,\
    '{}.{} was not found'.format(table, column)

  if (column in columns and columns[column].cql_type == 'bigint' and
      temp_column not in columns):
    logger.info('{}.{} is already the correct type'.format(table, column))
    return

  if column in columns and columns[column].cql_type != 'bigint':
    if temp_column not in columns:
      logger.info('Adding new column with correct type')
      statement = 'ALTER TABLE {} ADD {} int'.format(table, temp_column)
      session.execute(statement)

    copy_column(session, table, 'group', column, temp_column)

    logger.info('Dropping {}.{}'.format(table, column))
    session.execute('ALTER TABLE {} DROP {}'.format(table, column))

    logger.info('Creating {}.{}'.format(table, column))
    session.execute('ALTER TABLE {} ADD {} bigint'.format(table, column))

  copy_column(session, table, key_column, temp_column, column)

  logger.info('Dropping {}.{}'.format(table, temp_column))
  session.execute('ALTER TABLE {} DROP {}'.format(table, temp_column))

  logger.info('Schema upgrade complete')
