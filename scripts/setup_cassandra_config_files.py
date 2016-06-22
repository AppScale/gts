""" This script writes all the configuration files necessary to start Cassandra
on this machine."""

import os
import sys

# The template files in the cassandra env to replace with the actual config values.
CASSANDRA_ENV_TEMPLATES = "/root/appscale/AppDB/cassandra_env/templates/"

# The directory where Cassandra is installed to and has all the config files at.
CASSANDRA_DIR = "/opt/cassandra/cassandra/conf/"

def setup_config_files(local_ip, master_ip, local_token, replication, jmx_port):
  """ Goes through all the cassandra template config files, replaces them with
  the actual values and copies the modified files to the Cassandra directory.
  Args:
    local_ip: The IP address associated with this machine.
    master_ip: The IP address associated with the master database node.
    local_token: The token that should be set on this machine, which dictates
      how data should be partitioned between machines.
    replication: The replication factor of the data on the database nodes.
    jmx-port: The default port over which Cassandra will be available for
      JMX connections.
  """
  replacements = {'APPSCALE-LOCAL':local_ip, 'APPSCALE-MASTER': master_ip,
    'APPSCALE-TOKEN': local_token, 'REPLICATION': replication,
    'APPSCALE-JMX-PORT':jmx_port}

  for filename in os.listdir(CASSANDRA_ENV_TEMPLATES):
    source_file_path = CASSANDRA_ENV_TEMPLATES + filename
    dest_file_path = CASSANDRA_DIR + filename
    with open(source_file_path) as source_file:
      contents = source_file.read()
    for key, replacement in replacements.items():
      contents = contents.replace(key, replacement)
    with open(dest_file_path, "w") as dest_file:
      dest_file.write(contents)

def usage():
  print ""
  print "Creates the configuration files before starting Cassandra."
  print "Args: local-ip "
  print "      master-ip"
  print "      local-token (Empty for database master node)"
  print "      replication"
  print "      jmx-port"
  print ""
  print "Examples:"
  print " python ~/appscale/scripts/setup_cassandra_config_files.py --local-ip 192.xxx.xx.xx " \
        "--master-ip 192.xxx.xx.xx --local-token xxxxxxxx --replication 1 --jmx-port 7070 "
  print ""

if __name__ == "__main__":
  args_length = len(sys.argv)
  if args_length < 10:
    usage()
    sys.exit(1)

  for index in range(args_length):
    if index == 0:
      continue

    if (str(sys.argv[index])) == "--local-ip":
      local_ip = str(sys.argv[index+1])

    if (str(sys.argv[index])) == "--master-ip":
      master_ip = str(sys.argv[index+1])

    if (str(sys.argv[index])) == "--local-token":
      local_token = str(sys.argv[index + 1])
      # Local token is empty for database master node.
      if local_token == "--replication":
        local_token = ""

    if (str(sys.argv[index])) == "--replication":
      replication = str(sys.argv[index + 1])

    if (str(sys.argv[index])) == "--jmx-port":
      jmx_port = str(sys.argv[index + 1])

  setup_config_files(local_ip, master_ip, local_token, replication, jmx_port)
  sys.exit(0)
