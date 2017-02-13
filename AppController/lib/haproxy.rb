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


  # The position in the haproxy profiling information where the name of
  # of the application is (ie the GAE app, or datastore etc..).
  APP_NAME_INDEX = 0


  # The position in the haproxy profiling information where the name of
  # the service (e.g., the frontend or backend) is specified.
  SERVICE_NAME_INDEX = 1


  # The position in the haproxy profiling information where the number of
  # enqueued requests is specified.
  REQ_IN_QUEUE_INDEX = 2


  # The position in the haproxy profiling information where the number of
  # current sessions is specified.
  CURRENT_SESSIONS_INDEX = 4


  # The position in the haproxy profiling information where the status of
  # the specific server is specified.
  SERVER_STATUS_INDEX = 17


  # The position in the haproxy profiling information where the total
  # number of requests seen for a given app is specified.
  TOTAL_REQUEST_RATE_INDEX = 48


  # The String haproxy returns when we try to set a parameter on a
  # non defined server or backend.
  HAPROXY_ERROR_PREFIX = "No such"


  def self.start()
    start_cmd = "/usr/sbin/service haproxy start"
    stop_cmd = "/usr/sbin/service haproxy stop"
    match_cmd = "/usr/sbin/haproxy"
    MonitInterface.start(:haproxy, start_cmd, stop_cmd, [9999], nil, match_cmd,
                         nil, nil, nil)
  end

  def self.stop()
    MonitInterface.stop(:haproxy, false)
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

  # Create the config file for UserAppServer.
  def self.create_ua_server_config(server_ips, my_ip, listen_port)
    # We reach out to UserAppServers on the DB nodes.
    # The port is fixed.
    servers = []
    server_ips.each{ |server|
      servers << {'ip' => server, 'port' => UserAppClient::SERVER_PORT }
    }
    self.create_app_config(servers, my_ip, listen_port, UserAppClient::NAME)
  end

  # Create the config file for TaskQueue REST API endpoints.
  def self.create_tq_endpoint_config(server_ips, my_ip, listen_port)
    servers = []
    server_ips.each{ |server|
      servers << {'ip' => server,
                  'port' => TaskQueue::HAPROXY_PORT}
    }
    self.create_app_config(servers, my_ip, listen_port, TaskQueue::REST_NAME)
  end

  # Create the config file for Datastore Server.
  def self.create_datastore_server_config(my_ip, listen_port, table)
    # For the Datastore servers we have a list of local ports the servers
    # are listening to, and we need to create the list of local IPs.
    servers = []
    DatastoreServer.get_server_ports().each { |port|
      servers << {'ip' => my_ip, 'port' => port}
    }
    self.create_app_config(servers, my_ip, listen_port, DatastoreServer::NAME)
  end

  # Create the config file for TaskQueue servers.
  def self.create_tq_server_config(my_ip, listen_port)
    servers = []
    TaskQueue.get_server_ports().each { |port|
      servers << {'ip' => my_ip, 'port' => port}
    }
    self.create_app_config(servers, my_ip, listen_port, TaskQueue::NAME)
  end

  # A generic function for creating HAProxy config files used by AppScale services.
  #
  # Arguments:
  #   servers     : list of hashes containing server IPs and respective ports
  #   listen_ip   : the IP HAProxy should listen for
  #   listen_port : the port to listen to
  #   name        : the name of the server
  def self.create_app_config(servers, my_private_ip, listen_port, name)
    config = "# Create a load balancer for the #{name} application\n"
    config << "listen #{name} #{my_private_ip}:#{listen_port}\n"
    servers.each do |server|
      config << HAProxy.server_config(name, "#{server['ip']}:#{server['port']}") + "\n"
    end

    # If it is the dashboard app, increase the server timeout because uploading apps
    # can take some time.
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
    # Remove any files that are not configs
    sites = Dir.entries(SITES_ENABLED_PATH)
    sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
    sites.sort!

    # Build the configuration in memory first.
    config = File.read(BASE_CONFIG_FILE)
    sites.each do |site|
      config << File.read(File.join(SITES_ENABLED_PATH, site))
      config << "\n"
    end

    # We overwrite only if something changed.
    current = ""
    current = File.read(MAIN_CONFIG_FILE)  if File.exists?(MAIN_CONFIG_FILE)
    if current == config
      Djinn.log_debug("No need to restart haproxy: configuration didn't change.")
      return
    end

    # Update config file and restart haproxy.
    File.open(MAIN_CONFIG_FILE, "w+") { |dest_file| dest_file.write(config) }
    HAProxy.reload
  end


  # Generate the server configuration line for the provided inputs. GAE applications
  # that are thread safe will have a higher connection limit.
  def self.server_config(app_name, location)
    if HelperFunctions.get_app_thread_safe(app_name)
      return "  server #{app_name}-#{location} #{location} #{THREADED_SERVER_OPTIONS}"
    else
      return "  server #{app_name}-#{location} #{location} #{SERVER_OPTIONS}"
    end
  end


  # Updates the HAProxy config file for this App Engine application to
  # point to all the ports currently used by the application.
  def self.update_app_config(private_ip, app_name, listen_port, appservers)
    # Add a prefix to the app name to avoid collisions with non-GAE apps
    full_app_name = "gae_#{app_name}"

    servers = []
    appservers.each { |location|
      # Ignore not-yet started appservers.
      host, port = location.split(":")
      next if Integer(port) < 0
      servers << HAProxy.server_config(full_app_name, location)
    }
    if servers.length <= 0
      Djinn.log_warn("update_app_config called but no servers found.")
      return
    end

    config = "# Create a load balancer for the app #{app_name} \n"
    config << "listen #{full_app_name} #{private_ip}:#{listen_port} \n"
    config << servers.join("\n")

    config_path = File.join(SITES_ENABLED_PATH,
      "#{full_app_name}.#{CONFIG_EXTENSION}")

    # Let's reload and overwrite only if something changed.
    current = ""
    current = File.read(config_path) if File.exists?(config_path)
    if current != config
      File.open(config_path, "w+") { |dest_file| dest_file.write(config) }
      HAProxy.regenerate_config()
    else
      Djinn.log_debug("No need to restart haproxy: configuration didn't change.")
    end

    return true
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
  stats socket #{HAPROXY_PATH}/stats level admin

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


  # Retrieves HAProxy stats for the given app.
  #
  # Args:
  #   app_name: The name of the app to get HAProxy stats for.
  # Returns:
  #   The total requests for the app, the requests enqueued and the
  #   timestamp of stat collection.
  def self.get_haproxy_stats(app_name)
    full_app_name = "gae_#{app_name}"
    Djinn.log_debug("Getting scaling info for application #{full_app_name}")

    total_requests_seen = 0
    total_req_in_queue = 0
    time_requests_were_seen = 0

    # Retrieve total and enqueued requests for the given app.
    monitoring_info = Djinn.log_run("echo \"show stat\" | " +
      "socat stdio unix-connect:#{HAPROXY_PATH}/stats | grep #{full_app_name}")

    if monitoring_info.empty?
      Djinn.log_warn("Didn't see any monitoring info - #{full_app_name} may not " +
        "be running.")
      return :no_change, :no_change, :no_backend
    end

    monitoring_info.each_line { |line|
      parsed_info = line.split(',')
      # If we get short lines, are not part of the statistics returned by
      # haproxy, so we skip them.
      next if parsed_info.length < TOTAL_REQUEST_RATE_INDEX

      # Make sure the application name is correct (application name can be
      # prefix of others application names).
      next if parsed_info[APP_NAME_INDEX] != full_app_name

      service_name = parsed_info[SERVICE_NAME_INDEX]

      if service_name == "FRONTEND"
        total_requests_seen = parsed_info[TOTAL_REQUEST_RATE_INDEX].to_i
        time_requests_were_seen = Time.now.to_i
        Djinn.log_debug("#{full_app_name} #{service_name} Requests Seen " +
          "#{total_requests_seen}")
      end

      if service_name == "BACKEND"
        total_req_in_queue = parsed_info[REQ_IN_QUEUE_INDEX].to_i
        Djinn.log_debug("#{full_app_name} #{service_name} Queued Currently " +
          "#{total_req_in_queue}")
      end
    }

    return total_requests_seen, total_req_in_queue, time_requests_were_seen
  end


  # This method returns the list of running and failed AppServers
  # associated with a specific application.
  #
  # Args:
  #   app: A String containing the application ID.
  # Returns:
  #   An Array of running AppServers (ip:port).
  #   An Array of failed (marked as DOWN) AppServers (ip:port).
  def self.list_servers(app, down=false)
    full_app_name = "gae_#{app}"
    running = []
    failed = []
    servers = Djinn.log_run("echo \"show stat\" | socat stdio " +
      "unix-connect:#{HAPROXY_PATH}/stats | grep \"#{full_app_name}\"")
    servers.each_line{ |line|
      parsed_info = line.split(',')
      # Make sure the application name is correct (application name can be
      # prefix of others application names), and ignore the service
      # summary lines.
      next if parsed_info[APP_NAME_INDEX] != full_app_name
      next if parsed_info[SERVICE_NAME_INDEX] == "FRONTEND"
      next if parsed_info[SERVICE_NAME_INDEX] == "BACKEND"

      if parsed_info[SERVER_STATUS_INDEX] == "DOWN"
        failed << parsed_info[SERVICE_NAME_INDEX].sub(/^#{full_app_name}-/,'')
      else
        running << parsed_info[SERVICE_NAME_INDEX].sub(/^#{full_app_name}-/,'')
      end
    }
    if running.length > HelperFunctions::NUM_ENTRIES_TO_PRINT
      Djinn.log_debug("Haproxy: found #{running.length} running AppServers for #{app}.")
    else
      Djinn.log_debug("Haproxy: found these running AppServer for #{app}: #{running}.")
    end
    if failed.length > HelperFunctions::NUM_ENTRIES_TO_PRINT
      Djinn.log_debug("Haproxy: found #{failed.length} failed AppServers for #{app}.")
    else
      Djinn.log_debug("Haproxy: found these failed AppServer for #{app}: #{failed}.")
    end
    return running, failed
  end

  # This method sets the weight of the specified server (which needs to be
  # in haproxy) to 0 (that is no more new requests will be sent to the
  # server) and returns the number of current sessions handled by such
  # server.
  #
  # Args:
  #   app: A String containing the application ID.
  #   location: A String with the host:port of the running appserver.
  # Returns:
  #   An Integer containing the number of current sessions, or -1 if the
  #     server is not known by haproxy.
  def self.ensure_no_pending_request(app, location)
    full_app_name = "gae_#{app}"
    appserver = "#{full_app_name}-#{location}"
    Djinn.log_debug("We will put 0% weight to #{appserver}.")

    # Let's set the weight to 0, and check if the server is actually known by haproxy.
    result = Djinn.log_run("echo \"set weight #{full_app_name}/#{appserver} 0%\" |" +
      " socat stdio unix-connect:#{HAPROXY_PATH}/stats")
    if result.include?(HAPROXY_ERROR_PREFIX)
      Djinn.log_warn("Server #{full_app_name}/#{appserver} does not exists.")
      return -1
    end

    # Retrieve the current sessions for this server.
    server_stat = Djinn.log_run("echo \"show stat\" | socat stdio " +
      "unix-connect:#{HAPROXY_PATH}/stats | grep \"#{full_app_name},#{appserver}\"")
    if server_stat.empty? or server_stat.length > 1
      # We shouldn't be here, since we set the weight before.
      Djinn.log_warn("Something wrong retrieving stat for #{full_app_name}/#{appserver}!")
      return -1
    end

    parsed_info = server_stat.split(',')
    current_sessions = parsed_info[CURRENT_SESSIONS_INDEX]
    Djinn.log_debug("Current sessions for #{full_app_name}/#{appserver} " +
      "is #{current_sessions}.")
    return current_sessions
  end
end
