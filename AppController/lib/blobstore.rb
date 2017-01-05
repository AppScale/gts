#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'monit_interface'


# To support the Google App Engine Blobstore API, we have a custom server that
# handles Blobstore API requests, known as the Blobstore Server. This module
# abstracts away interactions with our Blobstore Server, providing methods to 
# start, stop, and monitor the Blobstore Server as needed.
module BlobServer

  # The BlobServer listens to this port.
  SERVER_PORT = 6107

  # HAProxy on the head node forwards this port to the server port on an app
  # engine node.
  HAPROXY_PORT = 6106

  # The server name used for HAProxy configuration.
  NAME = 'as_blob_server'

  def self.start(db_local_ip, db_local_port)
    start_cmd = [
      "#{self.scriptname}",
      "-d #{db_local_ip}:#{db_local_port}",
      "-p #{self::SERVER_PORT}"
    ].join(' ')
    stop_cmd = "/usr/bin/python2 #{APPSCALE_HOME}/scripts/stop_service.py " +
      "#{self.scriptname} /usr/bin/python"

    MonitInterface.start(:blobstore, start_cmd, stop_cmd, [self::SERVER_PORT],
                         nil, start_cmd, nil, nil, nil)
  end

  def self.stop()
     MonitInterface.stop(:blobstore)
  end

  def self.is_running?(my_ip)
    output = MonitInterface.is_running?(:blobstore)
    Djinn.log_debug("Checking if blobstore is already monitored: #{output}")
    return output
  end 

  def self.scriptname()
    return `which appscale-blobstore-server`.chomp
  end
end
