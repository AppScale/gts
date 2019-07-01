# Programmer: Navraj Chohan <nlake44@gmail.com>
require 'djinn'
require 'node_info'
require 'helperfunctions'
require 'monit_interface'
require 'set'

# A String that indicates where we write the process ID that Cassandra runs
# on at this machine.
PID_FILE = '/tmp/appscale-cassandra.pid'.freeze

# A String that indicates where we install Cassandra on this machine.
CASSANDRA_DIR = '/opt/cassandra'.freeze

# A String that indicates where the Cassandra binary is located on this
# machine.
CASSANDRA_EXECUTABLE = "#{CASSANDRA_DIR}/cassandra/bin/cassandra".freeze

# The location of the script that sets up Cassandra's config files.
SETUP_CONFIG_SCRIPT = "#{APPSCALE_HOME}/scripts/setup_cassandra_config_files.py".freeze

# The location of the nodetool binary.
NODETOOL = "#{CASSANDRA_DIR}/cassandra/bin/nodetool".freeze

# The location of the script that creates the initial tables.
PRIME_SCRIPT = `which appscale-prime-cassandra`.chomp

# The number of seconds Monit should allow Cassandra to take while starting up.
START_TIMEOUT = 60

# The location of the Cassandra data directory.
CASSANDRA_DATA_DIR = '/opt/appscale/cassandra'.freeze

# Writes all the configuration files necessary to start Cassandra on this
# machine.
#
# Args:
#   master_ip: A String corresponding to the private FQDN or IP address of the
#     machine hosting the Database Master role.
def setup_db_config_files(master_ip, local_ip)
  setup_script = "#{SETUP_CONFIG_SCRIPT} --local-ip #{local_ip} "\
                 "--master-ip #{master_ip}"
  until system(setup_script)
    Djinn.log_warn('Error while setting up Cassandra configuration. Retrying.')
    sleep(Djinn::SMALL_WAIT)
  end
end

# Starts Cassandra on this machine. Because this machine runs the DB Master
# role, it starts Cassandra first.
#
# Args:
#   clear_datastore: Remove any pre-existent data in the database.
#   needed: The number of nodes required for quorum.
#   desired: The total number of database nodes.
#   heap_reduction: A decimal representing a reduction factor for max heap
#     (eg. .2 = 80% of normal calculation).
def start_db_master(clear_datastore, needed, desired, heap_reduction)
  @state = 'Starting up Cassandra seed node'
  Djinn.log_info(@state)
  start_cassandra(clear_datastore, needed, desired, heap_reduction)
end

# Starts Cassandra on this machine. This is identical to starting Cassandra as a
# Database Master role, with the extra step of waiting for the DB Master to boot
# Cassandra up.
#
# Args:
#   clear_datastore: Remove any pre-existent data in the database.
#   needed: The number of nodes required for quorum.
#   desired: The total number of database nodes.
#   heap_reduction: A decimal representing a reduction factor for max heap
#     (eg. .2 = 80% of normal calculation).
def start_db_slave(clear_datastore, needed, desired, heap_reduction)
  seed_node = get_db_master.private_ip
  @state = "Waiting for Cassandra seed node at #{seed_node} to start"
  Djinn.log_info(@state)
  acc = AppControllerClient.new(seed_node, HelperFunctions.get_secret)
  loop do
    begin
      break if acc.primary_db_is_up == 'true'
    rescue FailedNodeException
      Djinn.log_warn(
          "Failed to check if Cassandra is up at #{seed_node}")
    end
    sleep(Djinn::SMALL_WAIT)
  end

  start_cassandra(clear_datastore, needed, desired, heap_reduction)
end

# Waits for enough database nodes to be up.
def wait_for_desired_nodes(needed, desired)
  sleep(Djinn::SMALL_WAIT) until system("#{NODETOOL} status > /dev/null 2>&1")
  loop do
    ready = nodes_ready.length
    Djinn.log_debug("#{ready} nodes are up. #{needed} are needed.")
    break if ready >= needed
    sleep(Djinn::SMALL_WAIT)
  end

  # Wait longer for all the nodes. This reduces errors during table creation.
  begin
    Timeout.timeout(60) {
      loop do
        ready = nodes_ready.length
        Djinn.log_debug("#{ready} nodes are up. #{desired} are desired.")
        break if ready >= desired
        sleep(Djinn::SMALL_WAIT)
      end
    }
  rescue Timeout::Error
    Djinn.log_info('Not all database nodes are ready, but there are enough ' \
                   'to achieve a quorum for every key.')
  end
end

# Starts Cassandra, and waits for enough nodes to be "Up Normal".
#
# Args:
#   clear_datastore: Remove any pre-existent data in the database.
#   needed: The number of nodes required for quorum.
#   desired: The total number of database nodes.
#   heap_reduction: A decimal representing a reduction factor for max heap
#     (eg. .2 = 80% of normal calculation).
def start_cassandra(clear_datastore, needed, desired, heap_reduction)
  if clear_datastore
    Djinn.log_info('Erasing datastore contents')
    Djinn.log_run("rm -rf #{CASSANDRA_DATA_DIR}")
  end

  # Create Cassandra data directory.
  Djinn.log_run("mkdir -p #{CASSANDRA_DATA_DIR}")
  Djinn.log_run("chown -R cassandra #{CASSANDRA_DATA_DIR}")

  su = `which su`.chomp
  cmd = "#{CASSANDRA_EXECUTABLE} -p #{PID_FILE}"
  if heap_reduction > 0
    cmd = "HEAP_REDUCTION=#{heap_reduction} #{cmd}"
  end

  start_cmd = "#{su} -c '#{cmd}' cassandra"
  stop_cmd = "/bin/bash -c 'kill $(cat #{PID_FILE})'"
  MonitInterface.start_daemon(:cassandra, start_cmd, stop_cmd, PID_FILE)

  # Ensure enough Cassandra nodes are available.
  Djinn.log_info('Waiting for Cassandra to start')
  wait_for_desired_nodes(needed, desired)
end

# Kills Cassandra on this machine.
def stop_db_master
  Djinn.log_info('Stopping Cassandra master')
  MonitInterface.stop(:cassandra)
end

# Kills Cassandra on this machine.
def stop_db_slave
  Djinn.log_info('Stopping Cassandra slave')
  MonitInterface.stop(:cassandra)
end

# Calculates the number of nodes needed for a quorum for every token.
def needed_for_quorum(total_nodes, replication)
  if total_nodes < 1 || replication < 1
    raise Exception('At least 1 database machine is needed.')
  end
  if replication > total_nodes
    raise Exception(
      'The replication factor cannot exceed the number of database machines.')
  end

  can_fail = (replication / 2.0 - 1).ceil
  total_nodes - can_fail
end

# Returns an array of nodes in 'Up Normal' state.
def nodes_ready
  # Example output of `nodetool gossipinfo`:
  # /192.168.33.10
  #   ...
  #   STATUS:15272:NORMAL,f02dd17...
  #   LOAD:263359:1.29168682182E11
  #   ...
  # /192.168.33.11
  # ...
  output = `"#{NODETOOL}" gossipinfo`
  return [] unless $?.exitstatus == 0

  live_nodes = Set[]
  current_node = nil
  output.split("\n").each { |line|
    current_node = line[1..-1] if line.start_with?('/')
    next if current_node.nil?
    if line.include?('STATUS') && line.include?('NORMAL')
      live_nodes.add(current_node)
    end
  }
  live_nodes.to_a
end
