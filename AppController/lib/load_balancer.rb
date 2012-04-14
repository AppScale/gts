#!/usr/bin/ruby -w


# As we can't rely on DNS in AppScale, we have a Rails app, called the
# AppLoadBalancer, that provides a single place to route users to their
# applications. It also provides authentication for users as an
# implementation of the Google App Engine Users API. This module provides
# methods that abstract away its configuration and deployment.
module LoadBalancer


  SERVER_PORTS = [8000, 8001, 8002]


  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8060


  # The port which requests to this app will be served from
  LISTEN_PORT = 80


  LISTEN_SSL_PORT = 443


  RAILS_ROOT = File.expand_path("#{APPSCALE_HOME}/AppLoadBalancer")


  def self.start
    env_vars = { "RAILS_ENV" => "production", "APPSCALE_HOME" => APPSCALE_HOME }

    SERVER_PORTS.each { |port|
      start_cmd = "/usr/bin/mongrel_rails start -c #{RAILS_ROOT} -e production -p #{port} " +
        "-P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
      stop_cmd = "/usr/bin/mongrel_rails stop -P #{RAILS_ROOT}/log/mongrel.#{port}.pid"

      GodInterface.start(:loadbalancer, start_cmd, stop_cmd, port, env_vars)
    }

    #`service appscale-loadbalancer start`
  end

  def self.stop
    GodInterface.stop(:loadbalancer)
    #`service appscale-loadbalancer stop`
  end

  def self.restart
    self.stop
    self.start
  end

  def self.name
    "as_alb"
  end

  def self.public_directory
    "/root/appscale/AppLoadBalancer/public"
  end

  def self.listen_port
    LISTEN_PORT
  end

  def self.listen_ssl_port
    LISTEN_SSL_PORT
  end

  def self.server_ports
    SERVER_PORTS
  end

  def self.proxy_port
    PROXY_PORT
  end
end
