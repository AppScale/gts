#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'
require 'net/http'

# To support the Google App Engine Datastore API in a way that is
# database-agnostic, App Engine applications store and retrieve data
# via the DatastoreServer. The server inherits this name from the storage
# format of requests in the Datastore API: Datastore Buffers.
module DatastoreServer
  # The first port that should be used to host DatastoreServers.
  STARTING_PORT = 4000

  # The port that we should run nginx on, to load balance requests to the
  # various DatastoreServers running on this node.
  PROXY_PORT = 8888

  # The name that nginx should use as the identifier for the DatastoreServer when it
  # we write its configuration files.
  NAME = 'appscale-datastore_server'.freeze

  # If we fail to get the number of processors we set our default number of
  # datastore servers to this value.
  DEFAULT_NUM_SERVERS = 3

  # Maximum number of concurrent requests that can be served
  # by instance of datastore
  MAXCONN = 2

  # Datastore server processes to core multiplier.
  MULTIPLIER = 1

  # Starts a Datastore Server on this machine. We don't want to monitor
  # it ourselves, so just tell monit to start it and watch it.
  def self.start(master_ip, db_local_ip, table, verbose = false)
    datastore_server = get_executable_name
    ports = get_server_ports

    env_vars = {
      'APPSCALE_HOME' => APPSCALE_HOME,
      'MASTER_IP' => master_ip,
      'LOCAL_DB_IP' => db_local_ip
    }

    start_cmd = "#{datastore_server} --type #{table}"
    start_cmd << ' --verbose' if verbose
    MonitInterface.start(:datastore_server, start_cmd, ports, env_vars)
  end

  # Stops the Datastore Buffer Server running on this machine. Since it's
  # managed by monit, just tell monit to shut it down.
  def self.stop
    MonitInterface.stop(:datastore_server)
  end

  # Restarts the Datastore Buffer Server on this machine by doing a hard
  # stop (killing it) and starting it.
  def self.restart(master_ip, my_ip, table)
    stop
    start(master_ip, my_ip, table)
  end

  # Number of servers is based on the number of CPUs.
  def self.number_of_servers
    # If this is NaN then it returns 0
    num_procs = `grep -c processor /proc/cpuinfo`.to_i
    return DEFAULT_NUM_SERVERS if num_procs.zero?
    servers = num_procs * MULTIPLIER
    return 1 if servers.zero?
    return servers
  end

  # Returns a list of ports that should be used to host DatastoreServers.
  def self.get_server_ports
    num_datastore_servers = number_of_servers

    server_ports = []
    num_datastore_servers.times { |i|
      server_ports << STARTING_PORT + i
    }
    server_ports
  end

  # Return the name of the executable of the datastore server.
  def self.get_executable_name
    `which appscale-datastore`.chomp
  end
end
