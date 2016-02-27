#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'app_dashboard'
require 'monit_interface'
require 'user_app_client'


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
  SERVER_OPTIONS = "maxconn 1 check"


  # HAProxy Configuration to use for a thread safe gae app.
  THREADED_SERVER_OPTIONS = "maxconn 7 check"


  # The first port that haproxy will bind to for App Engine apps.
  START_PORT = 10000


  # The default server timeout for the dashboard (apploadbalancer)
  ALB_SERVER_TIMEOUT = 300000


  def self.start()
    start_cmd = "/usr/sbin/service haproxy start"
    stop_cmd = "/usr/sbin/service haproxy stop"
    match_cmd = "/usr/sbin/haproxy"
    MonitInterface.start(:haproxy, start_cmd, stop_cmd, ports=9999,
      env_vars=nil, remote_ip=nil, remote_key=nil, match_cmd=match_cmd)
  end

  def self.stop()
    MonitInterface.stop(:haproxy)
  end

  def self.restart()
    MonitInterface.restart(:haproxy)
  end

  def self.reload()
    Djinn.log_run("service haproxy reload")
  end

  def self.is_running?
   output = MonitInterface.is_running?(:haproxy)
   Djinn.log_debug("Checking if haproxy is already monitored: #{output}")
   return output
  end

  # The port that the load balancer will be listening on for the given app number
  def self.app_listen_port(app_number)
    START_PORT + app_number
  end

  # Create the config file for UserAppServer.
  def self.create_ua_server_config(servers, my_ip, listen_port)
    # We reach out to UserAppServers on the DB nodes.
    # The port is fixed.
    ports = []
    servers.each{ |server|
      ports << UserAppClient::SERVER_PORT
    }
    self.create_app_config(servers, my_ip, listen_port, ports,
      UserAppClient::NAME)
  end

  # Create the config file for Datastore Server.
  def self.create_datastore_server_config(my_ip, listen_port, table)
    # For the Datastore servers we have a list of local ports the servers
    # are listening to, and we need to create the list of local IPs.
    ips = []
    DatastoreServer.get_server_ports(table).each { |port|
      ips << my_ip
    }
    self.create_app_config(ips, my_ip, listen_port,
      DatastoreServer.get_server_ports(table), DatastoreServer::NAME)
  end

  # A generic function for creating HAProxy config files used by AppScale services.
  #
  # Arguments:
  #   server_ips  : list of server IPs
  #   listen_ip   : the IP HAProxy should listen for
  #   listen_port : the port to listen to
  #   server_ports: list of server ports, corresponding to server_ips
  #   name        : the name of the server
  def self.create_app_config(server_ips, my_private_ip, listen_port,
    server_ports, name)
    servers = []
    server_ports.each_with_index do |port, index|
      servers << HAProxy.server_config(name, index, "#{server_ips[index]}:#{port}")
    end

    config = "# Create a load balancer for the #{name} application \n"
    config << "listen #{name} #{my_private_ip}:#{listen_port} \n"
    config << servers.join("\n")
    # If it is the dashboard app, increase the server timeout because uploading apps
    # can take some time
    if name == AppDashboard::APP_NAME
      config << "\n  timeout server #{ALB_SERVER_TIMEOUT}\n"
    end

    config_path = File.join(SITES_ENABLED_PATH, "#{name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end

  # Generates a load balancer configuration file. Since HAProxy doesn't provide
  # a `file include` option we emulate that functionality here.
  def self.regenerate_config()
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
    # Reload haproxy since we changed the config, restarting causes connections
    # to be cut which shows users a nginx 404
    HAProxy.reload()
  end

  # Generate the server configuration line for the provided inputs. GAE applications
  # that are thread safe will have a higher connection limit.
  def self.server_config(app_name, index, location)
    if HelperFunctions.get_app_thread_safe(app_name)
      Djinn.log_debug("[#{app_name}] Writing Threadsafe HAProxy config")
      return "  server #{app_name}-#{index} #{location} #{THREADED_SERVER_OPTIONS}"
    else
      Djinn.log_debug("[#{app_name}] Writing Non-Threadsafe HAProxy config")
      return "  server #{app_name}-#{index} #{location} #{SERVER_OPTIONS}"
    end
  end

  # Updates the HAProxy config file for this App Engine application to
  # point to all the ports currently used by the application.
  def self.update_app_config(private_ip, app_name, app_info)
    listen_port = app_info['haproxy']

    # Add a prefix to the app name to avoid collisions with non-GAE apps
    full_app_name = "gae_#{app_name}"

    servers = []
    app_info['appengine'].each_with_index { |location, index|
      servers << HAProxy.server_config(full_app_name, index, location)
    }

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
    FileUtils.rm_f(File.join(SITES_ENABLED_PATH, config_name))
    HAProxy.regenerate_config
  end


  # Removes all the enabled sites
  def self.clear_sites_enabled()
    if File.directory?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)
      # Remove any files that are not configs
      sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
      full_path_sites = sites.map { |site| File.join(SITES_ENABLED_PATH, site) }
      FileUtils.rm_f full_path_sites
      HAProxy.regenerate_config
    end
  end

  # Set up the folder structure and creates the configuration files necessary for haproxy
  def self.initialize_config()
    base_config = <<CONFIG
global
  maxconn 64000
  ulimit-n 200000

  # log incoming requests - may need to tell syslog to accept these requests
  # http://kevin.vanzonneveld.net/techblog/article/haproxy_logging/
  log             127.0.0.1       local1 warning

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

  # Timeout a request if the client did not read any data for 600 seconds
  timeout client 600000

  # Timeout a request if Mongrel does not accept a connection for 600 seconds
  timeout connect 600000

  # Timeout a request if Mongrel does not accept the data on the connection,
  # or does not send a response back in 10 minutes.
  timeout server 600000

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
