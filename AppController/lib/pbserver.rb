#!/usr/bin/ruby -w


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'


# To support the Google App Engine Datastore API in a way that is
# database-agnostic, App Engine applications store and retrieve data
# via the PBServer. The server inherits this name from the storage
# format of requests in the Datastore API: Protocol Buffers.
module PbServer


  # As PBServers are single-threaded, we run more than one and put
  # nginx in front of it to load balance requests. This constant
  # indicates how many PBServers should be run on each node.
  NUM_PBSERVERS = 3


  # The first port that should be used to host PBServers.
  STARTING_PORT = 4000


  # The port that we should run nginx on, to load balance requests to the
  # various PBServers running on this node.
  PROXY_PORT = 3999


  # The port that nginx should be listening to for non-encrypted requests to
  # the PBServers.
  LISTEN_PORT_NO_SSL = 8888


  # The port that nginx should be listening to for encrypted requests to the
  # PBServers.
  LISTEN_PORT_WITH_SSL = 8443


  # A list of databases that we cannot spawn multiple PBServers for and stick
  # nginx in front of, usually because they have locks or other database state
  # stored in memory.
  DBS_NEEDING_ONE_PBSERVER = ["mysql"]


  # A list of databases that we have native (not database agnostic) support for
  # within AppScale.
  DBS_WITH_NATIVE_PBSERVER = ["mysql"]


  # The name that nginx should use as the identifier for the PBServer when it
  # we write its configuration files.
  NAME = "as_pbserver"


  # Starts a Protocol Buffer Server on this machine. We don't want to monitor
  # it ourselves, so just tell god to start it and watch it.
  def self.start(master_ip, db_local_ip, my_ip, table, zklocations)
    pbserver = self.get_executable_name(table)
    ports = self.get_server_ports(table)

    env_vars = { 
      'APPSCALE_HOME' => APPSCALE_HOME,
      "MASTER_IP" => master_ip, 
      "LOCAL_DB_IP" => db_local_ip 
    }
  
    if table == "cassandra"
      ports.each { |port|
        start_cmd = "/usr/bin/python2.6 #{pbserver} -p #{port} " +
            "--no_encryption --type #{table} -z \'#{zklocations}\' "
        # stop command doesn work, relies on terminate.rb
        stop_cmd = "pkill -9 datastore_server"
        GodInterface.start(:pbserver, start_cmd, stop_cmd, port, env_vars)
      }
    else
      ports.each { |port|
        start_cmd = "/usr/bin/python2.6 #{pbserver} -p #{port} " +
            "--no_encryption --type #{table} -z \'#{zklocations}\' "
          "--no_encryption --type #{table} -z \'#{zklocations}\' " +
          "-s #{HelperFunctions.get_secret()} -a #{my_ip} --key"
        # stop command doesn work, relies on terminate.rb
        stop_cmd = "pkill -9 appscale_server"
        GodInterface.start(:pbserver, start_cmd, stop_cmd, port, env_vars)
      }
    end
  end


  # Stops the Protocol Buffer Server running on this machine. Since it's
  # managed by god, just tell god to shut it down.
  def self.stop(table)
     GodInterface.stop(:pbserver)
  end


  # Restarts the Protocol Buffer Server on this machine by doing a hard
  # stop (killing it) and starting it.
  def self.restart(master_ip, my_ip, table, zklocations)
    self.stop()
    self.start(master_ip, my_ip, table, zklocations)
  end


  # Returns a list of ports that should be used to host PBServers.
  def self.get_server_ports(table)
    if DBS_NEEDING_ONE_PBSERVER.include?(table)
      num_pbservers = 1
    else
      num_pbservers = NUM_PBSERVERS
    end

    server_ports = []
    num_pbservers.times { |i|
      server_ports << STARTING_PORT + i
    }
    return server_ports
  end

  
  def self.is_running(my_ip)
    `curl http://#{my_ip}:#{PROXY_PORT}` 
  end 


  # Since we have two different versions of the Protocol Buffer Server
  # (one that's database agnostic and one that's native to the DB), return
  # the right version for the database selected.
  def self.get_executable_name(table)
    if DBS_WITH_NATIVE_PBSERVER.include?(table)
      return "#{APPSCALE_HOME}/AppDB/appscale_server_#{table}.py"
    elsif table == "cassandra"
      return "#{APPSCALE_HOME}/AppDB/datastore_server.py"
    #elsif table == "hypertable"
    #  return "#{APPSCALE_HOME}/AppDB/datastore_server.py"
    else
      return "#{APPSCALE_HOME}/AppDB/appscale_server.py"
    end
  end
end

