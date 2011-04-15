#!/usr/bin/ruby -w

require 'helperfunctions'

# A class to wrap all the interactions with the AppMonitoring rails app
class Monitoring
  SERVER_PORTS = [8003]
  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8061
  # The port which requests to this app will be served from
  LISTEN_PORT = 8050
  ENVIRONMENT = "RAILS_ENV=production "

  def self.start
    `service appscale-monitoring start`
  end

  def self.stop
    `service appscale-monitoring stop`
  end

  def self.restart
    self.stop
    self.start
  end

  # Clear out the entire database so no old meta-data is left over
  def self.reset
    `cd #{APPSCALE_HOME}/AppMonitoring; #{ENVIRONMENT} rake db:drop;`
    `cd #{APPSCALE_HOME}/AppMonitoring; #{ENVIRONMENT} rake db:migrate;`
  end

  def self.name
    "as_mon"
  end

  def self.public_directory
    "/root/appscale/AppMonitoring/public"
  end

  def self.listen_port
    LISTEN_PORT
  end

  def self.server_ports
    SERVER_PORTS
  end
  
  def self.proxy_port
    PROXY_PORT
  end
end
