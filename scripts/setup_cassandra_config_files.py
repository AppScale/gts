#!/usr/bin/env python2
""" This script writes all the configuration files necessary to start Cassandra
on this machine."""

import argparse
import os
import pkgutil
import sys

from kazoo.client import KazooClient

from appscale.common import appscale_info
from appscale.common.deployment_config import DeploymentConfig
from appscale.common.deployment_config import InvalidConfig

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppDB'))
from appscale.datastore.cassandra_env.cassandra_interface import\
  CASSANDRA_INSTALL_DIR


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description="Creates Cassandra's configuration files")
  parser.add_argument('--local-ip', required=True,
                      help='The private IP address of this machine.')
  parser.add_argument('--master-ip', required=True,
                      help='The private IP address of the database master.')
  parser.add_argument('--zk-locations', required=False,
                      help='The location of Zookeeper.')
  args = parser.parse_args()
  zk_locations = args.zk_locations if args.zk_locations else \
    appscale_info.get_zk_locations_string()
  zk_client = KazooClient(hosts=zk_locations)
  zk_client.start()
  deployment_config = DeploymentConfig(zk_client)
  cassandra_config = deployment_config.get_config('cassandra')
  if 'num_tokens' not in cassandra_config:
    raise InvalidConfig('num_tokens not specified in deployment config.')
  num_tokens = cassandra_config['num_tokens']

  replacements = {'APPSCALE-LOCAL': args.local_ip,
                  'APPSCALE-MASTER': args.master_ip,
                  'APPSCALE-NUM-TOKENS': num_tokens}

  for filename in ('cassandra.yaml', 'cassandra-env.sh'):
    dest_file_path = os.path.join(CASSANDRA_INSTALL_DIR, 'cassandra', 'conf',
                                  filename)
    contents = pkgutil.get_data('appscale.datastore.cassandra_env',
                                'templates/{}'.format(filename))
    for key, replacement in replacements.items():
      if replacement is None:
        replacement = ''
      contents = contents.replace(key, str(replacement))
    with open(dest_file_path, 'w') as dest_file:
      dest_file.write(contents)
