#!/usr/bin/ruby -w

require 'fileutils'
require 'posixpsutil'

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'app_dashboard'
require 'monit_interface'
require 'user_app_client'
require 'datastore_server'
require 'taskqueue'
require 'blobstore'
require 'search'

# As AppServers within AppScale are usually single-threaded, we run multiple
# copies of them and load balance traffic to them. Since nginx (our first
# load balancer) doesn't do health checks on the AppServer before it dispatches
# traffic to it, we employ haproxy, an open source load balancer that does
# provide this capability. This module abstracts away configuration and
# deployment for haproxy.
module HAProxy
  # We do have 2 haproxy, one that is used for AppServers, and the other
  # for internal AppScale services (Datastore, TaskQueue etc...). We keep
  # them separate to be able to control when reload is necessary.
  HAPROXY_PATH = File.join('/', 'etc', 'haproxy')
  CONFIG_EXTENSION = 'cfg'.freeze
  HAPROXY_BIN = `which haproxy`.chomp
  BASH_BIN = `which bash`.chomp

  # These are for the AppScale internal services haproxy.
  SERVICE_SITES_PATH = File.join(HAPROXY_PATH, 'service-sites-enabled')
  SERVICE_MAIN_FILE = File.join(HAPROXY_PATH, "service-haproxy.#{CONFIG_EXTENSION}")
  SERVICE_BASE_FILE = File.join(HAPROXY_PATH, "service-base.#{CONFIG_EXTENSION}")
  SERVICE_PIDFILE = '/var/run/appscale/service-haproxy.pid'.freeze

  # Maximum AppServer threaded connections
  MAX_APPSERVER_CONN = 7

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
  HAPROXY_ERROR_PREFIX = 'No such'.freeze

  # The number of seconds HAProxy should wait for a server response.
  HAPROXY_SERVER_TIMEOUT = 600

  # The version key regex.
  VERSION_KEY_REGEX = /#{HelperFunctions::GAE_PREFIX}(.*_.*_.*).#{CONFIG_EXTENSION}/

  # Start HAProxy for API services.
  def self.services_start
    if !valid_config?(SERVICE_MAIN_FILE)
      Djinn.log_warn('Invalid configuration for HAProxy services.')
      return
    end
    return if MonitInterface.is_running?(:service_haproxy)

    start_cmd = "#{HAPROXY_BIN} -f #{SERVICE_MAIN_FILE} -D " \
      "-p #{SERVICE_PIDFILE}"
    stop_cmd = "#{BASH_BIN} -c 'kill $(cat #{SERVICE_PIDFILE})'"
    MonitInterface.start_daemon(
      :service_haproxy, start_cmd, stop_cmd, SERVICE_PIDFILE)
  end

  # Create the config file for UserAppServer.
  def self.create_ua_server_config(server_ips, my_ip, listen_port)
    # We reach out to UserAppServers on the DB nodes.
    # The port is fixed.
    servers = []
    server_ips.each { |server|
      servers << { 'ip' => server, 'port' => UserAppClient::SERVER_PORT }
    }
    create_app_config(servers, my_ip, listen_port, UserAppClient::NAME)
  end

  # Remove the configuration for TaskQueue REST API endpoints.
  def self.remove_tq_endpoints
    FileUtils.rm_f(File.join(SERVICE_SITES_PATH, TaskQueue::NAME))
    HAProxy.regenerate_config
  end

  # Create the config file for TaskQueue servers.
  def self.create_tq_server_config(server_ips, my_ip, listen_port)
    servers = []
    server_ips.each { |server|
      TaskQueue.get_server_ports.each { |port|
        servers << { 'ip' => server, 'port' => port }
      }
    }
    create_app_config(servers, my_ip, listen_port, TaskQueue::NAME)
  end

  # A generic function for creating HAProxy config files used by AppScale services.
  #
  # Arguments:
  #   servers     : list of hashes containing server IPs and respective ports
  #   listen_ip   : the IP HAProxy should listen for
  #   listen_port : the port to listen to
  #   name        : the name of the server
  # Returns:
  #   Boolean     : true if config was good, false if parameters were
  #                 incorrect
  def self.create_app_config(servers, my_private_ip, listen_port, name)
    if servers.empty?
      Djinn.log_warn('create_app_config called with no running servers.')
      return false
    end

    # We only serve internal services here.
    unless [TaskQueue::NAME, DatastoreServer::NAME, Search2::NAME,
        UserAppClient::NAME, BlobServer::NAME].include?(name)
      Djinn.log_warn("create_app_config called for unknown service: #{name}.")
      return false
    end

    full_version_name = "#{name}"
    config_path = File.join(SERVICE_SITES_PATH,
                            "#{full_version_name}.#{CONFIG_EXTENSION}")
    config = "# Create a load balancer for #{name}.\n"
    config << "listen #{full_version_name}\n"
    config << "  bind #{my_private_ip}:#{listen_port}\n"
    servers.each do |server|
      config << HAProxy.server_config(full_version_name,
                                      "#{server['ip']}:#{server['port']}") +
                                      "\n"
    end

    # If it is the dashboard app, increase the server timeout because
    # uploading apps can take some time.
    if name.split(Djinn::VERSION_PATH_SEPARATOR)[0] == AppDashboard::APP_NAME
      config << "\n  timeout server #{ALB_SERVER_TIMEOUT}\n"
    end

    # Let's overwrite configuration for 'name' only if anything changed.
    current = ''
    current = File.read(config_path) if File.exists?(config_path)
    File.open(config_path, 'w+') { |f| f.write(config) } if current != config

    # This will reload haproxy if anything changed.
    HAProxy.regenerate_config
    true
  end

  # Generates a load balancer configuration file. Since HAProxy doesn't provide
  # a `file include` option we emulate that functionality here.
  def self.regenerate_config_file(config_dir, base_config_file, config_file)
    # Remove any files that are not configs
    sites = Dir.entries(config_dir)
    sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
    sites.sort!

    # Build the configuration in memory first.
    config = File.read(base_config_file)
    sites.each do |site|
      config << File.read(File.join(config_dir, site))
      config << "\n"
    end

    # We overwrite only if something changed.
    current = ''
    current = File.read(config_file)  if File.exists?(config_file)
    if current == config
      Djinn.log_debug("No need to restart haproxy for #{config_file}:" \
                      " configuration didn't change.")
      return false
    end

    # Update config file.
    File.open(config_file, 'w+') { |dest_file| dest_file.write(config) }
    unless valid_config?(config_file)
      Djinn.log_warn("Invalid haproxy configuration at #{config_file}.")
      return false
    end

    Djinn.log_info("Updated haproxy configuration at #{config_file}.")
    true
  end

  # Checks if a given HAProxy config file is valid.
  def self.valid_config?(config_file)
    return false unless File.file?(config_file)
    system("#{HAPROXY_BIN} -c -f #{config_file}")
  end

  # Regenerate the configuration file for HAProxy (if anything changed)
  # then starts or reload haproxy as needed.
  def self.regenerate_config
    # Regenerate configuration for the AppScale serices haproxy.
    if regenerate_config_file(SERVICE_SITES_PATH,
                              SERVICE_BASE_FILE,
                              SERVICE_MAIN_FILE)
      # Ensure the service is monitored and running.
      services_start
      Djinn::RETRIES.downto(0) {
        break if MonitInterface.is_running?(:service_haproxy)
        sleep(Djinn::SMALL_WAIT)
      }

      # Reload with the new configuration file.
      Djinn.log_run("#{HAPROXY_BIN} -f #{SERVICE_MAIN_FILE} -p #{SERVICE_PIDFILE}" \
                    " -D -sf `cat #{SERVICE_PIDFILE}`")
    end
  end

  # Generate the server configuration line for the provided inputs. GAE
  # applications that are thread safe will have a higher connection limit.
  def self.server_config(server_name, location)
    if server_name.start_with?(HelperFunctions::GAE_PREFIX)
      version_key = server_name[HelperFunctions::GAE_PREFIX.length..-1]
      threadsafe = HelperFunctions.get_version_thread_safe(version_key)
      maxconn = threadsafe ? MAX_APPSERVER_CONN : 1
    elsif server_name == DatastoreServer::NAME
      # Allow custom number of connections at a time for datastore.
      maxconn = DatastoreServer::MAXCONN
    elsif server_name == Search2::NAME
      # Allow custom number of connections at a time for search2.
      maxconn = Search2::MAXCONN
    else
      # Allow only one connection at a time for other services.
      maxconn = 1
    end

    "  server #{server_name}-#{location} #{location} maxconn #{maxconn} check"
  end

  # Set up the folder structure and creates the configuration files necessary for haproxy
  #
  # Args:
  #   connect_timeout: Number of milliseconds for a request to wait before
  #     a backend server will accept connection.
  def self.initialize_config(connect_timeout)
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

  # If sending a request fails, try to send it to another, 3 times
  # before aborting the request
  retries 3

  # Do not enforce session affinity (i.e., an HTTP session can be served by
  # any Mongrel, not just the one that started the session
  option redispatch

  # Time to wait for a connection attempt to a server.
  timeout connect #{connect_timeout}ms

  # The maximum inactivity time allowed for a client.
  timeout client 50000ms

  # The maximum inactivity time allowed for a server.
  timeout server #{HAPROXY_SERVER_TIMEOUT}s

  # Amount of time after which a health check is considered to have timed out
  timeout check 5000

CONFIG

    # Create the sites enabled folder
    unless File.exists? SERVICE_SITES_PATH
      FileUtils.mkdir_p SERVICE_SITES_PATH
    end

    # Write the base configuration file which sets default configuration
    # parameters for the service haproxy process.
    File.open(SERVICE_BASE_FILE, 'w+') { |dest_file|
      dest_file.write(base_config.sub('/stats', '/service-stats'))
    }
  end
end

