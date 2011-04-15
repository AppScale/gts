#!/usr/bin/ruby -w

# A class to wrap all the interactions with the AppLoadBalancer rails app
class LoadBalancer
  SERVER_PORTS = [8000, 8001, 8002]
  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8060
  # The port which requests to this app will be served from
  LISTEN_PORT = 80
  LISTEN_SSL_PORT = 443

  def self.start
    `service appscale-loadbalancer start`
  end

  def self.stop
    `service appscale-loadbalancer stop`
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
