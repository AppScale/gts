from __future__ import division
import argparse

from subprocess import check_output
from ..cassandra_env.cassandra_interface import NODE_TOOL


def main():
  """ Run appscale-get-token script. """
  parser = argparse.ArgumentParser(
    description='Retrieve a Cassandra token owned by this node')
  parser.add_argument('percentile', type=int)
  args = parser.parse_args()

  sample_output = check_output([NODE_TOOL, 'rangekeysample'])
  keys = [key.strip() for key in sample_output.splitlines()[1:]]
  keys.sort()
  index = int(len(keys) * (args.percentile / 100))
  print(keys[index])
