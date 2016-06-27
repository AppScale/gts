#!/usr/bin/env python2
""" Create Cassandra keyspace and initial tables. """

import argparse
import dbconstants
import logging
import os
import sys

from cassandra.cluster import Cluster
from cassandra_env.cassandra_interface import KEYSPACE
from cassandra_env.cassandra_interface import ThriftColumn

sys.path.append(os.path.join(os.path.dirname(__file__), '../../lib/'))
from constants import LOG_FORMAT
from constants import MASTERS_FILE_LOC
from constants import SLAVES_FILE_LOC


def define_ua_schema(session):
  """ Populate the schema table for the UAServer.

  Args:
    session: A cassandra-driver session.
  """
  uaserver_tables = [
    {'name': dbconstants.APPS_TABLE, 'schema': dbconstants.APPS_SCHEMA},
    {'name': dbconstants.USERS_TABLE, 'schema': dbconstants.USERS_SCHEMA}
  ]
  for table in uaserver_tables:
    key = bytearray('/'.join([dbconstants.SCHEMA_TABLE, table['name']]))
    columns = bytearray(':'.join(table['schema']))
    define_schema = """
        INSERT INTO "{table}" ({key}, {column}, {value})
        VALUES (%(key)s, %(column)s, %(value)s)
      """.format(table=dbconstants.SCHEMA_TABLE,
                 key=ThriftColumn.KEY,
                 column=ThriftColumn.COLUMN_NAME,
                 value=ThriftColumn.VALUE)
    values = {'key': key,
              'column': dbconstants.SCHEMA_TABLE_SCHEMA[0],
              'value': columns}
    session.execute(define_schema, values)


def prime_cassandra(replication):
  """ Create Cassandra keyspace and initial tables.

  Args:
    replication: An integer specifying the replication factor for the keyspace.
  Raises:
    AppScaleBadArg if replication factor is not greater than 0.
    TypeError if replication is not an integer.
  """
  if not isinstance(replication, int):
    raise TypeError('replication must be an integer')

  if int(replication) <= 0:
    raise dbconstants.AppScaleBadArg('Replication must be greater than zero')

  with open(MASTERS_FILE_LOC) as masters_file:
    db_master = masters_file.read().split()

  with open(SLAVES_FILE_LOC) as slaves_file:
    db_slaves = slaves_file.read().split()

  hosts = list(set(db_master + db_slaves))
  cluster = Cluster(hosts, protocol_version=2)
  session = cluster.connect()

  create_keyspace = """
    CREATE KEYSPACE IF NOT EXISTS "{keyspace}"
    WITH REPLICATION = %(replication)s
  """.format(keyspace=KEYSPACE)
  keyspace_replication = {'class': 'SimpleStrategy',
                          'replication_factor': replication}
  session.execute(create_keyspace, {'replication': keyspace_replication})
  session.set_keyspace(KEYSPACE)

  for table in dbconstants.INITIAL_TABLES:
    create_table = """
      CREATE TABLE IF NOT EXISTS "{table}" (
        {key} blob,
        {column} text,
        {value} blob,
        PRIMARY KEY ({key}, {column})
      ) WITH COMPACT STORAGE
    """.format(table=table,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)
    session.execute(create_table)

  first_entity = session.execute(
    'SELECT * FROM "{}" LIMIT 1'.format(dbconstants.APP_ENTITY_TABLE))
  existing_entities = len(list(first_entity)) == 1

  define_ua_schema(session)

  if existing_entities:
    logging.info('The necessary keyspace and tables are present.')
  else:
    logging.info('Successfully created initial keyspace and tables.')


if __name__ == "__main__":
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument('replication', type=int,
                      help='The replication factor for the keyspace')
  args = parser.parse_args()

  prime_cassandra(args.replication)
