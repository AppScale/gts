#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'


# To support the Google App Engine Blobstore API, we have a custom server that
# handles Blobstore API requests, known as the Blobstore Server. This module
# abstracts away interactions with our Blobstore Server, providing methods to 
# start, stop, and monitor the Blobstore Server as needed.
module BlobServer


  SERVER_PORTS = [6107]


  def self.start(db_local_ip, db_local_port)
    blobserver = self.blob_script
    ports = self.server_ports
    ports.each { |blobserver_port|
      start_cmd = ["python #{blobserver}",
            "-d #{db_local_ip}:#{db_local_port}",
            "-p #{blobserver_port}"].join(' ')

      stop_cmd = "/usr/bin/pkill -9 blobstore_server"

      MonitInterface.start(:blobstore, start_cmd, stop_cmd, blobserver_port)
    }
  end

  def self.stop
     MonitInterface.stop(:blobstore)
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

