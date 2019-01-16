from __future__ import division
import argparse
import logging
import os

from appscale.common.appscale_utils import ssh
from appscale.common.constants import KEY_DIRECTORY
from appscale.common.constants import LOG_FORMAT
from subprocess import (CalledProcessError,
                        check_output)
from ..cassandra_env.cassandra_interface import NODE_TOOL
from ..cassandra_env.cassandra_interface import KEYSPACE


# The percentage difference allowed between an actual and ideal load.
MAX_DRIFT = .3

logger = logging.getLogger(__name__)


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


def get_gossip():
  """ Return the cluster gossip in a structured way.

  Returns:
    A list of nodes represented by dictionaries.
  """
  nodes = []
  current_node = None
  for line in check_output([NODE_TOOL, 'gossipinfo']).splitlines():
    if line.startswith('/'):
      if current_node is not None:
        nodes.append(current_node)

      current_node = {'ip': line.strip()[1:]}

    if line.strip().startswith('STATUS'):
      current_node['ready'] = 'NORMAL' in line
      current_node['token'] = line.split(',')[-1]

    if line.strip().startswith('LOAD'):
      current_node['load'] = float(line.split(':')[-1])

  if current_node is not None:
    nodes.append(current_node)

  if not nodes:
    raise Exception('Unable to collect gossip for any nodes')

  required_fields = ['ip', 'ready', 'load', 'token']
  for node in nodes:
    for required_field in required_fields:
      if required_field not in node:
        raise Exception('Unable to parse all fields for {}'.format(node))

  return nodes


def get_ring(gossip):
  """ Return the ring status in a structured way.

  Args:
    gossip: A list of gossip info for each node.

  Returns:
    A list of nodes represented by dictionaries.
  """
  nodes = sorted(gossip, key=lambda node: node['token'])
  for index, node in enumerate(nodes):
    node['index'] = index

  if not nodes:
    raise Exception('Unable to find nodes in ring')

  # Calculate skew and diff for each node in ring.
  ideal_load = sum(node['load'] for node in nodes) / len(nodes)
  for index, node in enumerate(nodes):
    try:
      node['skew'] = abs(node['load'] - ideal_load) / ideal_load
    except ZeroDivisionError:
      node['skew'] = 0

    node['diff'] = abs(node['load'] - nodes[index - 1]['load'])

  return nodes


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
    logger.info('Moving {} MiB from {} to {}'.format(
      mb_to_move, node1['ip'], node2['ip']))
    percentile = 100 - int((to_move / node1['load']) * 100)
    new_token = ssh(node1['ip'], keyname,
                    'appscale-get-token {}'.format(percentile),
                    method=check_output).strip()
    repair = [new_token, node1['token']]
    cleanup_ip = node1['ip']
  else:
    logger.info('Moving {} MiB from {} to {}'.format(
      mb_to_move, node2['ip'], node1['ip']))
    percentile = int((to_move / node2['load']) * 100)
    new_token = ssh(node2['ip'], keyname,
                    'appscale-get-token {}'.format(percentile),
                    method=check_output).strip()
    repair = [node1['token'], new_token]
    cleanup_ip = node2['ip']

  logger.info('Moving {} to {}'.format(node1['ip'], new_token[:60] + '...'))
  ssh(node1['ip'], keyname, '{} move {}'.format(NODE_TOOL, new_token))

  start = repair[0][:60] + '...'
  end = repair[1][:60] + '...'
  logger.info('Repairing {} to {}'.format(start, end))
  check_output([NODE_TOOL, 'repair', '-st', repair[0], '-et', repair[1]])

  logger.info('Cleaning up {}'.format(cleanup_ip))
  ssh(cleanup_ip, keyname, '{} cleanup'.format(NODE_TOOL))


def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--skip-tokens-check', action='store_true',
    help='Assume that all nodes own one token')
  parser.add_argument(
    '--skip-ownership-check', action='store_true',
    help='Assume that the node count exceeds the replication factor')
  args = parser.parse_args()

  if not args.skip_tokens_check or not args.skip_ownership_check:
    logger.info('Fetching status')
    status = get_status()

    if (not args.skip_tokens_check and
        any(node['tokens'] != 1 for node in status)):
      raise Exception('All nodes must have exactly one token')

    if (not args.skip_ownership_check and
        any(node['owns'] != float(100) for node in status)):
      raise Exception('All nodes already own every key')

  logger.info('Fetching gossip')
  gossip = get_gossip()

  if sum(node['ready'] for node in gossip) <= 1:
    raise Exception('There must be more than one node up to balance')

  ring = get_ring(gossip)
  if max(node['skew'] for node in ring) < MAX_DRIFT:
    logger.info('All nodes within {}% of ideal load'.format(MAX_DRIFT * 100))
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
