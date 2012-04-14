#!/usr/bin/ruby -w


# Monitr is a Ruby on Rails application that displays system information
# written by collectd. This module configures and deploys that service.
module Monitoring


  SERVER_PORTS = [8003]


  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8061


  # The port which requests to this app will be served from
  LISTEN_PORT = 8050


  ENVIRONMENT = "RAILS_ENV=production "


  RAILS_ROOT = File.expand_path("#{APPSCALE_HOME}/AppMonitoring")


  def self.start
    env_vars = { "RAILS_ENV" => "production", "APPSCALE_HOME" => APPSCALE_HOME }

    SERVER_PORTS.each { |port|
      start_cmd = "/usr/bin/mongrel_rails start -c #{RAILS_ROOT} -e production -p #{port} " +
        "-P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
      stop_cmd = "/usr/bin/mongrel_rails stop -P #{RAILS_ROOT}/log/mongrel.#{port}.pid"

      GodInterface.start(:monitr, start_cmd, stop_cmd, port, env_vars)
    }
  end

  def self.stop
    GodInterface.stop(:monitr)
    #`service appscale-monitoring stop`
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
    "#{APPSCALE_HOME}/AppMonitoring/public"
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
