from __future__ import division
import argparse
import sys

from cassandra.cluster import Cluster
from random import choice
from random import shuffle
from subprocess import check_output
from ..cassandra_env.cassandra_interface import KEYSPACE
from ..cassandra_env.cassandra_interface import NODE_TOOL
from ..cassandra_env.cassandra_interface import ThriftColumn
from ..cassandra_env.retry_policies import BASIC_RETRIES
from ..dbconstants import APP_ENTITY_TABLE
from ..dbconstants import APP_ENTITY_SCHEMA
from ..dbconstants import KEY_DELIMITER
from ..dbconstants import KIND_SEPARATOR
from ..unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info


def is_entity(key):
  """ Determines whether a given string is an entity key.

  Args:
    key: A string containing a key from 'rangekeysample'.
  Returns:
    A boolean indicating whether or not the string is an entity key.
  """
  key_parts = key.split(KEY_DELIMITER)
  if len(key_parts) != 3:
    return False

  last_part = key_parts[-1]
  if not last_part.endswith(KIND_SEPARATOR):
    return False

  last_part = last_part[:-len(KIND_SEPARATOR)]
  if KIND_SEPARATOR in last_part:
    return False

  return ':' in last_part


def get_kind_averages(keys):
  """ Get an average size for each kind.

  Args:
    keys: A list of dictionaries containing keys.
  Returns:
    A dictionary listing the average size of each kind.
  """
  hosts = appscale_info.get_db_ips()
  cluster = Cluster(hosts, default_retry_policy=BASIC_RETRIES)
  session = cluster.connect(KEYSPACE)

  entities_by_kind = {}
  for key_dict in keys:
    key = key_dict['key']
    if is_entity(key):
      key_parts = key.split(KEY_DELIMITER)
      kind = key_parts[2].split(':')[0]
      kind_id = KEY_DELIMITER.join([key_parts[0], key_parts[1], kind])
      if kind_id not in entities_by_kind:
        entities_by_kind[kind_id] = {'keys': [], 'size': 0, 'fetched': 0}
      entities_by_kind[kind_id]['keys'].append(key)

  for kind_id, kind in entities_by_kind.iteritems():
    shuffle(kind['keys'])

  if not entities_by_kind:
    return {}

  futures = []
  for _ in range(50):
    kind = choice(entities_by_kind.keys())
    try:
      key = entities_by_kind[kind]['keys'].pop()
    except IndexError:
      continue

    select = """
      SELECT {value} FROM "{table}"
      WHERE {key}=%(key)s AND {column}=%(column)s
    """.format(value=ThriftColumn.VALUE, table=APP_ENTITY_TABLE,
               key=ThriftColumn.KEY, column=ThriftColumn.COLUMN_NAME)
    parameters = {'key': bytearray(key), 'column': APP_ENTITY_SCHEMA[0]}
    future = session.execute_async(select, parameters)
    futures.append({'future': future, 'kind': kind})

  for future_dict in futures:
    future = future_dict['future']
    kind = future_dict['kind']
    try:
      entity = future.result()[0].value
    except IndexError:
      continue

    entities_by_kind[kind]['size'] += len(entity)
    entities_by_kind[kind]['fetched'] += 1

  kind_averages = {}
  for kind_id, kind in entities_by_kind.iteritems():
    try:
      kind_averages[kind_id] = int(kind['size'] / kind['fetched'])
    except ZeroDivisionError:
      kind_averages[kind_id] = 0

  return kind_averages


def get_sample():
  """ Gets a sorted sample of keys on this node.

  Returns:
    A list of dictionaries containing keys.
  """
  sample_output = check_output([NODE_TOOL, 'rangekeysample'])
  keys = [{'key': key.strip().decode('hex'), 'size': 0}
          for key in sample_output.splitlines()[1:]]
  sorted(keys, key=lambda key: key['key'])
  return keys


def main():
  """ Run appscale-get-token script. """
  parser = argparse.ArgumentParser(
    description='Retrieve a Cassandra token owned by this node')
  parser.add_argument('percentile', type=int)
  args = parser.parse_args()

  keys = get_sample()
  kind_averages = get_kind_averages(keys)

  for key_dict in keys:
    key = key_dict['key']
    key_dict['size'] += len(key)
    if not is_entity(key):
      continue

    key_parts = key.split(KEY_DELIMITER)
    kind = key_parts[2].split(':')[0]
    kind_id = KEY_DELIMITER.join([key_parts[0], key_parts[1], kind])
    if kind_id in kind_averages:
      key_dict['size'] += kind_averages[kind_id]

  total_size = sum(key['size'] for key in keys)
  desired_size = int(total_size * (args.percentile / 100))

  size_seen = 0
  for key in keys:
    size_seen += key['size']
    if size_seen >= desired_size:
      print(key['key'].encode('hex'))
      return

  # If we still haven't reached the desired size, just select the last key.
  print(keys[-1]['key'].encode('hex'))
