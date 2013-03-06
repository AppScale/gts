#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'


# To support the Google App Engine Datastore API in a way that is
# database-agnostic, App Engine applications store and retrieve data
# via the DatastoreServer. The server inherits this name from the storage
# format of requests in the Datastore API: Datastore Buffers.
module DatastoreServer


  # As DatastoreServers are single-threaded, we run more than one and put
  # nginx in front of it to load balance requests. This constant
  # indicates how many DatastoreServers should be run on each node.
  NUM_DATASTORESERVERS = 1


  # The first port that should be used to host DatastoreServers.
  STARTING_PORT = 4000


  # The port that we should run nginx on, to load balance requests to the
  # various DatastoreServers running on this node.
  PROXY_PORT = 3999


  # The port that nginx should be listening to for non-encrypted requests to
  # the DatastoreServers.
  LISTEN_PORT_NO_SSL = 8888


  # The port that nginx should be listening to for encrypted requests to the
  # DatastoreServers.
  LISTEN_PORT_WITH_SSL = 8443


  # The name that nginx should use as the identifier for the DatastoreServer when it
  # we write its configuration files.
  NAME = "as_datastore_server"


  # Starts a Datastore Server on this machine. We don't want to monitor
  # it ourselves, so just tell god to start it and watch it.
  def self.start(master_ip, db_local_ip, my_ip, table, zklocations)
    datastore_server = self.get_executable_name(table)
    ports = self.get_server_ports(table)

    env_vars = { 
      'APPSCALE_HOME' => APPSCALE_HOME,
      "MASTER_IP" => master_ip, 
      "LOCAL_DB_IP" => db_local_ip 
    }
  
    ports.each { |port|
      start_cmd = "/usr/bin/python2.6 #{datastore_server} -p #{port} " +
          "--no_encryption --type #{table} -z \'#{zklocations}\' "
      # stop command doesn't work, relies on terminate.rb
      stop_cmd = "pkill -9 datastore_server"
      GodInterface.start(:datastore_server, start_cmd, stop_cmd, port, env_vars)
    }
  end


  # Stops the Datastore Buffer Server running on this machine. Since it's
  # managed by god, just tell god to shut it down.
  def self.stop(table)
     GodInterface.stop(:datastore_server)
  end


  # Restarts the Datastore Buffer Server on this machine by doing a hard
  # stop (killing it) and starting it.
  def self.restart(master_ip, my_ip, table, zklocations)
    self.stop()
    self.start(master_ip, my_ip, table, zklocations)
  end


  # Returns a list of ports that should be used to host DatastoreServers.
  def self.get_server_ports(table)
    num_datastore_servers = NUM_DATASTORESERVERS

    server_ports = []
    num_datastore_servers.times { |i|
      server_ports << STARTING_PORT + i
    }
    return server_ports
  end

  
  def self.is_running(my_ip)
    `curl http://#{my_ip}:#{PROXY_PORT}` 
  end 


  # Return the name of the executable of the datastore server.
  def self.get_executable_name(table)
    return "#{APPSCALE_HOME}/AppDB/datastore_server.py"
  end
end

