#!/usr/bin/env python2
""" This script writes all the configuration files necessary to start Cassandra
on this machine."""

import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
from appscale.datastore.cassandra_env.cassandra_interface import\
  CASSANDRA_INSTALL_DIR

# Cassandra configuration files to modify.
CASSANDRA_TEMPLATES = os.path.join(
  os.path.dirname(sys.modules['appscale.datastore.cassandra_env'].__file__),
  'templates')


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description="Creates Cassandra's Monit configuration files")
  parser.add_argument('--local-ip',
                      help='The private IP address of this machine.')
  parser.add_argument('--master-ip',
                      help='The private IP address of the database master.')
  args = parser.parse_args()

  replacements = {'APPSCALE-LOCAL': args.local_ip,
                  'APPSCALE-MASTER': args.master_ip}

  for filename in os.listdir(CASSANDRA_TEMPLATES):
    source_file_path = os.path.join(CASSANDRA_TEMPLATES, filename)
    dest_file_path = os.path.join(CASSANDRA_INSTALL_DIR, 'cassandra', 'conf',
                                  filename)
    with open(source_file_path) as source_file:
      contents = source_file.read()
    for key, replacement in replacements.items():
      if replacement is None:
        replacement = ''
      contents = contents.replace(key, replacement)
    with open(dest_file_path, 'w') as dest_file:
      dest_file.write(contents)
