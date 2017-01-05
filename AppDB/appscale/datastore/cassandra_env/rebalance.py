from __future__ import division
import logging
import os
import sys

from subprocess import (CalledProcessError,
                        check_output)
from ..cassandra_env.cassandra_interface import NODE_TOOL
from ..cassandra_env.cassandra_interface import KEYSPACE
from ..unpackaged import APPSCALE_LIB_DIR
from ..unpackaged import INFRASTRUCTURE_MANAGER_DIR

sys.path.append(APPSCALE_LIB_DIR)
from constants import LOG_FORMAT

sys.path.append(INFRASTRUCTURE_MANAGER_DIR)
from utils.utils import KEY_DIRECTORY
from utils.utils import ssh

# The percentage difference allowed between an actual and ideal load.
MAX_DRIFT = .3


class InvalidUnits(Exception):
  """ Indicates an unexpected units value. """
  pass


def load_bytes(value, units):
  """ Convert a human-friendly size to bytes.

  Args:
    value: A float containing a size.
    units: A string specifying the units.
  Returns:
    An integer representing the number of bytes.
  Raises:
    InvalidUnits if the units string is not recognized.
  """
  magnitudes = {'KiB': 1, 'MiB': 2, 'GiB': 3, 'TiB': 4}
  if units not in magnitudes:
    raise InvalidUnits('{} not a recognized unit'.format(units))
  return int(value * 1024 ** magnitudes[units])


def get_status():
  """ Return the cluster status in a structured way.

  Returns:
    A list of nodes represented by dictionaries.
  """
  nodes = []
  for line in check_output([NODE_TOOL, 'status', KEYSPACE]).splitlines():
    fields = line.split()
    if len(fields) != 8:
      continue
    nodes.append({
      'state': fields[0],
      'ip': fields[1],
      'tokens': int(fields[4]),
      'owns': float(fields[5][:-1])
    })
  return nodes


def get_ring():
  """ Return the ring status in a structured way.

  Returns:
    A list of nodes represented by dictionaries.
  """
  ring_output = check_output([NODE_TOOL, 'ring', KEYSPACE])
  ring = []
  index = 0
  for line in ring_output.splitlines():
    fields = line.split()
    if len(fields) != 8:
      continue

    ring.append({
      'index': index,
      'ip': fields[0],
      'status': fields[2],
      'state': fields[3],
      'load': load_bytes(float(fields[4]), fields[5]),
      'token': fields[7]
    })
    index += 1

  assert len(ring) > 0

  # Calculate skew and diff for each node in ring.
  ideal_load = sum(node['load'] for node in ring) / len(ring)
  for index, node in enumerate(ring):
    try:
      node['skew'] = abs(node['load'] - ideal_load) / ideal_load
    except ZeroDivisionError:
      node['skew'] = 0
    node['diff'] = abs(node['load'] - ring[index - 1]['load'])

  return ring


def equalize(node1, node2):
  """ Move data from the node with a larger load to the other one.

  Args:
    node1: A dictionary representing a node.
    node2: A dictionary representing a neighbor of node1.
  """
  keys = [key for key in os.listdir(KEY_DIRECTORY) if key.endswith('.key')]
  keyname = keys[0].split('.')[0]

  to_move = abs(node1['load'] - node2['load']) / 2
  mb_to_move = round(to_move / 1024 ** 2, 2)
  if node1['load'] > node2['load']:
    logging.info('Moving {} MiB from {} to {}'.format(
      mb_to_move, node1['ip'], node2['ip']))
    percentile = 100 - int((to_move / node1['load']) * 100)
    new_token = ssh(node1['ip'], keyname,
                    'appscale-get-token {}'.format(percentile),
                    method=check_output).strip()
    repair = [new_token, node1['token']]
    cleanup_ip = node1['ip']
  else:
    logging.info('Moving {} MiB from {} to {}'.format(
      mb_to_move, node2['ip'], node1['ip']))
    percentile = int((to_move / node2['load']) * 100)
    new_token = ssh(node2['ip'], keyname,
                    'appscale-get-token {}'.format(percentile),
                    method=check_output).strip()
    repair = [node1['token'], new_token]
    cleanup_ip = node2['ip']

  logging.info('Moving {} to {}'.format(node1['ip'], new_token[:60] + '...'))
  ssh(node1['ip'], keyname, '{} move {}'.format(NODE_TOOL, new_token))

  start = repair[0][:60] + '...'
  end = repair[1][:60] + '...'
  logging.info('Repairing {} to {}'.format(start, end))
  check_output([NODE_TOOL, 'repair', '-st', repair[0], '-et', repair[1]])

  logging.info('Cleaning up {}'.format(cleanup_ip))
  ssh(cleanup_ip, keyname, '{} cleanup'.format(NODE_TOOL))


def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  logging.info('Fetching status')
  status = get_status()

  # All nodes must have just one token.
  assert {node['tokens'] for node in status} == {1}

  # There must be more than one node up to balance.
  assert len([node for node in status if node['state'] == 'UN']) > 1

  # If all nodes own everything, a rebalance is not possible.
  assert {node['owns'] for node in status} != {float(100)}

  logging.info('Fetching ring')
  ring = get_ring()
  if max(node['skew'] for node in ring) < MAX_DRIFT:
    logging.info('All nodes within {}% of ideal load'.format(MAX_DRIFT * 100))
    return

  # Pick two neighboring nodes with the largest difference in load. If the
  # equalization process fails, try the next largest difference.
  ring_by_diff = sorted(ring, key=lambda node: node['diff'], reverse=True)
  for node in ring_by_diff:
    try:
      equalize(ring[node['index'] - 1], ring[node['index']])
      # If data has been moved, the load needs to be re-evaluated. Load gets
      # updated after 90 seconds.
      break
    except CalledProcessError:
      continue
