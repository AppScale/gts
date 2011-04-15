#!/usr/bin/ruby -w
require 'helperfunctions'

# A class to wrap all the interactions with the PbServer
class PbServer
  SERVER_PORTS = [4000, 4001, 4002,4003, 4004, 4005]
  PROXY_PORT = 3999
  LISTEN_PORT = 8888
  LISTEN_SSL_PORT = 8443
  DBS_NEEDING_ONE_PBSERVER = ["mysql"]
  DBS_WITH_NATIVE_TRANSACTIONS = ["mysql"]

  def self.start(master_ip, db_local_ip, my_ip, table, zklocations)
    pbserver = self.pb_script(table)
    ports = self.server_ports(table)
    ports.each { |pbserver_port|
      cmd = [ "MASTER_IP=#{master_ip} LOCAL_DB_IP='#{db_local_ip}'",
            "start-stop-daemon --start",
            "--exec /usr/bin/python2.6",
            "--name appscale_server",
            "--make-pidfile",
            "--pidfile /var/appscale/appscale-appscaleserver-#{pbserver_port}.pid",
            "--background",
            "--",
            "#{pbserver}",
            "-p #{pbserver_port}",
            "--no_encryption",
            "--type #{table}",
            "-z \"#{zklocations}\"",
            "-s #{HelperFunctions.get_secret}",
            "-a #{my_ip} --key"]
      Djinn.log_debug(cmd.join(" "))
      Kernel.system cmd.join(" ")
    }
  end

  def self.stop(table)
     ports = self.server_ports(table)
     ports.each { |pbserver_port|
       Kernel.system "start-stop-daemon --stop --pidfile /var/appscale/appscale-appscaleserver-#{pbserver_port}.pid"
     }
  end

  def self.restart(master_ip, my_ip, table, zklocations)
    self.stop
    self.start(master_ip, my_ip, table, zklocations)
  end

  def self.name
    "as_pbserver"
  end

  def self.public_directory
    "/root/appscale/AppDB/public"
  end

  def self.listen_port
    LISTEN_PORT
  end

  def self.listen_ssl_port
    LISTEN_SSL_PORT
  end

  def self.server_ports(table)
    if DBS_NEEDING_ONE_PBSERVER.include?(table)
      return SERVER_PORTS.first(1)
    else
      return SERVER_PORTS
    end
  end

  def self.proxy_port
    PROXY_PORT
  end
  
  def self.is_running(my_ip)
    `curl http://#{my_ip}:#{PROXY_PORT}` 
  end 

  def self.pb_script(table)
    if DBS_WITH_NATIVE_TRANSACTIONS.include?(table)
      return "#{APPSCALE_HOME}/AppDB/appscale_server_native_trans.py"
    else
      return "#{APPSCALE_HOME}/AppDB/appscale_server.py"
    end
  end
end

