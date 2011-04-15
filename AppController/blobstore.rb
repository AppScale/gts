#!/usr/bin/ruby -w
require 'helperfunctions'

# A class to wrap all the interactions with the blobstore server
class BlobServer
  SERVER_PORTS = [6106]
  def self.start(db_local_ip, db_local_port)
    blobserver = self.blob_script
    ports = self.server_ports
    ports.each { |blobserver_port|
      cmd = [ "start-stop-daemon --start",
            "--exec /usr/bin/python2.6",
            "--name blob_server",
            "--make-pidfile",
            "--pidfile /var/appscale/appscale-blobstoreserver-#{blobserver_port}.pid",
            "--background",
            "--",
            "#{blobserver}",
            "-d #{db_local_ip}:#{db_local_port}",
            "-p #{blobserver_port}"]
      Djinn.log_debug(cmd.join(" "))
      Kernel.system cmd.join(" ")
    }
  end

  def self.stop
     ports = self.server_ports
     ports.each { |blobserver_port|
       Kernel.system "start-stop-daemon --stop --pidfile /var/appscale/appscale-blobstoreserver-#{blobserver_port}.pid"
     }
  end

  def self.restart(my_ip, db_port)
    self.stop
    self.start(my_ip, db_port)
  end

  def self.name
    "as_blobserver"
  end


  def self.server_ports
      return SERVER_PORTS
  end

  def self.is_running(my_ip)
    ports = self.server_ports
    ports.each { |blobserver_port|
     `curl http://#{my_ip}:#{blobserver_port}/` 
    }
  end 

  def self.blob_script
    return "#{APPSCALE_HOME}/AppDB/blobstore/blobstore_server.py"
  end
end

