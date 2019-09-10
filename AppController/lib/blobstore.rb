#!/usr/bin/ruby -w

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'service_helper'

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

  # Service name for use with helper
  SERVICE_NAME = 'appscale-blobstore'.freeze

  # The server name used for HAProxy configuration.
  NAME = 'as_blob_server'.freeze

  def self.start(db_local_ip, db_local_port)
    service_env = {
        APPSCALE_BLOBSTORE_PORT: SERVER_PORT,
        APPSCALE_DATASTORE_SERVICE: "#{db_local_ip}:#{db_local_port}"
    }
    ServiceHelper.write_environment(SERVICE_NAME, service_env)
    ServiceHelper.start(SERVICE_NAME)
  end

  def self.stop
    ServiceHelper.stop(SERVICE_NAME)
  end

  def self.is_running?
    output = ServiceHelper.is_running?(SERVICE_NAME)
    Djinn.log_debug("Checking if blobstore is already monitored: #{output}")
    output
  end
end
