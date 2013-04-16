#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'app_dashboard'
require 'monitoring'


# As AppServers within AppScale are usually single-threaded, we run multiple
# copies of them and load balance traffic to them. Since nginx (our first
# load balancer) doesn't do health checks on the AppServer before it dispatches
# traffic to it, we employ haproxy, an open source load balancer that does
# provide this capability. This module abstracts away configuration and
# deployment for haproxy.
module HAProxy


  HAPROXY_PATH = File.join("/", "etc", "haproxy")


  SITES_ENABLED_PATH = File.join(HAPROXY_PATH, "sites-enabled")


  CONFIG_EXTENSION = "cfg"


  # The configuration file that haproxy reads from.
  MAIN_CONFIG_FILE = File.join(HAPROXY_PATH, "haproxy.#{CONFIG_EXTENSION}")


  # Provides a set of default configurations.
  BASE_CONFIG_FILE = File.join(HAPROXY_PATH, "base.#{CONFIG_EXTENSION}")


  # Options to used to configure servers.
  # For more information see http://haproxy.1wt.eu/download/1.3/doc/configuration.txt
  SERVER_OPTIONS = "maxconn 1 check inter 20000 fastinter 1000 fall 1"


  # The first port that haproxy will bind to for App Engine apps.
  START_PORT = 10000


  # The location of the script that god uses to see if haproxy is running,
  # restarting it if necessary.
  START_HAPROXY_SCRIPT = File.dirname(__FILE__) + "/../" + \
                          "/scripts/start_haproxy.sh"

  def self.start
    start_cmd = "bash #{START_HAPROXY_SCRIPT}"
    stop_cmd = "service haproxy stop"
    port = 9999
    GodInterface.start(:haproxy, start_cmd, stop_cmd, port)
  end

  def self.stop
    GodInterface.stop(:haproxy)
  end

  def self.restart
    `service haproxy restart`
  end

  def self.reload
    `service haproxy reload`
  end

  def self.is_running?
    processes = `ps ax | grep haproxy | grep -v grep | wc -l`.chomp
    if processes == "0"
      return false
    else
      return true
    end
  end

  # The port that the load balancer will be listening on for the given app number
  def self.app_listen_port(app_number)
    START_PORT + app_number
  end

  # Create the configuration file for the AppDashboard application
  def self.create_app_load_balancer_config(my_public_ip, my_private_ip, 
    listen_port)
    self.create_app_config(my_public_ip, my_private_ip, listen_port, 
      AppDashboard.server_ports, AppDashboard.name)
  end

  # Create the configuration file for the AppMonitoring Rails application
  def self.create_app_monitoring_config(my_public_ip, my_private_ip, listen_port)
    self.create_app_config(my_public_ip, my_private_ip, listen_port, 
      Monitoring.server_ports, Monitoring.name)
  end

  # Create the config file for Datastore Server applications
  def self.create_datastore_server_config(my_ip, listen_port, table)
    self.create_app_config(my_ip, my_ip, listen_port, 
      DatastoreServer.get_server_ports(table), DatastoreServer::NAME)
  end

  # A generic function for creating haproxy config files used by appscale services
  def self.create_app_config(my_public_ip, my_private_ip, listen_port, 
    server_ports, name)
    servers = []
    server_ports.each_with_index do |port, index|
      servers << HAProxy.server_config(name, index, my_private_ip, port)
    end

    config = "# Create a load balancer for the #{name} application \n"
    config << "listen #{name} #{my_private_ip}:#{listen_port} \n"
    config << servers.join("\n")

    config_path = File.join(SITES_ENABLED_PATH, "#{name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end

  # Generates a load balancer configuration file. Since haproxy doesn't provide
  # an file include option we emulate that functionality here.
  def self.regenerate_config
    conf = File.open(MAIN_CONFIG_FILE,"w+")
    
    # Start by writing in the base file
    File.open(BASE_CONFIG_FILE, "r") do |base|
      conf.write(base.read())
    end

    sites = Dir.entries(SITES_ENABLED_PATH)
    # Remove any files that are not configs
    sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }

    sites.sort!

    # Append each one of the configs into the main one
    sites.each do |site|
      conf.write("\n")
      File.open(File.join(SITES_ENABLED_PATH, site), "r") do |site_config|
        conf.write(site_config.read())
      end
      conf.write("\n")
    end

    conf.close()
    
    # Restart haproxy since we have changed the config
    HAProxy.restart
  end
  
  # Generate the server configuration line for the provided inputs
  def self.server_config app_name, index, ip, port
    "  server #{app_name}-#{index} #{ip}:#{port} #{SERVER_OPTIONS}"
  end

  def self.write_app_config(app_name, app_number, num_of_servers, ip)
    # Add a prefix to the app name to avoid possible conflicts
    full_app_name = "gae_#{app_name}"

    servers = []
    num_of_servers.times do |index|
      port = HelperFunctions.application_port(app_number, index, num_of_servers)
      server = HAProxy.server_config(full_app_name, index, ip, port)
      servers << server
    end

    listen_port = HAProxy.app_listen_port(app_number)
    config = "# Create a load balancer for the app #{app_name} \n"
    config << "listen #{full_app_name} #{ip}:#{listen_port} \n"
    config << servers.join("\n")

    config_path = File.join(SITES_ENABLED_PATH, 
      "#{full_app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end


  # Updates the HAProxy config file for this App Engine application to
  # point to all the ports currently the application. In contrast with
  # write_app_config, these ports can be non-contiguous.
  # TODO(cgb): Lots of copy/paste here with write_app_config - eliminate it.
  def self.update_app_config(app_name, app_number, ports, private_ip)
    # Add a prefix to the app name to avoid collisions with non-GAE apps
    full_app_name = "gae_#{app_name}"
    index = 0
    servers = []

    ports.each { |port|
      server = HAProxy.server_config(full_app_name, index, private_ip, port)
      index += 1
      servers << server
    }

    listen_port = HAProxy.app_listen_port(app_number)
    config = "# Create a load balancer for the app #{app_name} \n"
    config << "listen #{full_app_name} #{private_ip}:#{listen_port} \n"
    config << servers.join("\n")

    config_path = File.join(SITES_ENABLED_PATH, 
      "#{full_app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }
 
    HAProxy.regenerate_config()
  end


  def self.remove_app(app_name)
    config_name = "gae_#{app_name}.#{CONFIG_EXTENSION}"
    FileUtils.rm(File.join(SITES_ENABLED_PATH, config_name))
    HAProxy.regenerate_config
  end


  # Removes all the enabled sites
  def self.clear_sites_enabled
    if File.exists?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)
      # Remove any files that are not configs
      sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
      full_path_sites = sites.map { |site| File.join(SITES_ENABLED_PATH, site) }
      FileUtils.rm_f full_path_sites

      HAProxy.regenerate_config
    end
  end

  # Set up the folder structure and creates the configuration files necessary for haproxy
  def self.initialize_config
    base_config = <<CONFIG
global
  maxconn 64000
  ulimit-n 200000

  # log incoming requests - may need to tell syslog to accept these requests
  # http://kevin.vanzonneveld.net/techblog/article/haproxy_logging/
  log             127.0.0.1       local0
  log             127.0.0.1       local1 notice

  # Distribute the health checks with a bit of randomness
  spread-checks 5

  # Bind socket for haproxy stats
  stats socket /etc/haproxy/stats

# Settings in the defaults section apply to all services (unless overridden in a specific config)
defaults

  # apply log settings from the global section above to services
  log global

  # Proxy incoming traffic as HTTP requests
  mode http

  # Use round robin load balancing, however since we will use maxconn that will take precedence
  balance roundrobin

  maxconn 64000

  # Log details about HTTP requests
  #option httplog

  # Abort request if client closes its output channel while waiting for the 
  # request. HAProxy documentation has a long explanation for this option.
  option abortonclose

  # Check if a "Connection: close" header is already set in each direction,
  # and will add one if missing.
  option httpclose

  # If sending a request fails, try to send it to another, 3 times
  # before aborting the request
  retries 3

  # Do not enforce session affinity (i.e., an HTTP session can be served by 
  # any Mongrel, not just the one that started the session
  option redispatch

  # Timeout a request if the client did not read any data for 60 seconds
  timeout client 60000

  # Timeout a request if Mongrel does not accept a connection for 60 seconds
  timeout connect 60000

  # Timeout a request if Mongrel does not accept the data on the connection,
  # or does not send a response back in 60 seconds
  timeout server 60000
  
  # Enable the statistics page 
  stats enable
  stats uri     /haproxy?stats
  stats realm   Haproxy\ Statistics
  stats auth    haproxy:stats

  # Create a monitorable URI which returns a 200 if haproxy is up
  # monitor-uri /haproxy?monitor

  # Amount of time after which a health check is considered to have timed out
  timeout check 5000
CONFIG

    # Create the sites enabled folder
    unless File.exists? SITES_ENABLED_PATH
      FileUtils.mkdir_p SITES_ENABLED_PATH
    end
    
    # Write the base configuration file which sets default configuration parameters
    File.open(BASE_CONFIG_FILE, "w+") { |dest_file| dest_file.write(base_config) }
  end
end
