#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'load_balancer'
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

  
  # FIXME(cgb): make sense of this
  TIME_PERIOD = 10
  SRV_NAME = 1
  QUEUE_CURR = 2
  REQ_RATE = 46
  CURR_RATE = 33
  @@initialized = {}
  @@req_rate = {}   # Request rate coming in over last 20 seconds
  @@queue_curr = {} # currently Queued requests      
  @@threshold_req_rate = {}
  @@threshold_queue_curr = {}
  @@scale_down_req_rate = {}
  # END


  # FIXME(cgb): make sense of this method
  def self.initialize(app_name)
    if @@initialized[app_name].nil?
      index = 0
      # To maintain req rate for last TIME_PERIOD seconds for each app in the system
      @@req_rate[app_name] = []
      # To maintain queued requests number for last TIME_PERIOD seconds for each app in the system
      @@queue_curr[app_name] = []
      # Assigning values of thresholds such as use of resources is maximized
      # Thresholds are same for each app as assigned . but these can be changed to match with App's chracterstics
      # Threshold for incoming request rate . Condition for scaling up will test will see if request rate is more than this threshold
      @@threshold_req_rate[app_name] = 5
      # Condition for scaling down will test will see if request rate is less than or equal to this threshold
      @@scale_down_req_rate[app_name] = 2
      # Threshold for currently queued requests number . Condition for scaling up will test will see if queued requests at haproxy are  more than this threshold
      @@threshold_queue_curr[app_name] = 5 
      # Initializing the request rates and number of queued requests to 0 for the whole TIME_PERIOD seconds
      while index < TIME_PERIOD
        @@req_rate[app_name][index] = 0
        @@queue_curr[app_name][index] = 0
        index += 1
      end
      # To make sure the variables are intialized only once for an app
      @@initialized[app_name] = 1 
    end
  end


  def self.stop
    `service haproxy stop`
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

  # Create the configuration file for the AppLoadBalancer Rails application
  def self.create_app_load_balancer_config(my_ip, listen_port)
    self.create_app_config(my_ip, listen_port, LoadBalancer.server_ports, LoadBalancer.name)
  end

  # Create the configuration file for the AppMonitoring Rails application
  def self.create_app_monitoring_config(my_ip, listen_port)
    self.create_app_config(my_ip, listen_port, Monitoring.server_ports, Monitoring.name)
  end

  # Create the config file for PBServer applications
  def self.create_pbserver_config(my_ip, listen_port, table)
    self.create_app_config(my_ip, listen_port, PbServer.get_server_ports(table), PbServer::NAME)
  end

  # A generic function for creating haproxy config files used by appscale services
  def self.create_app_config(my_ip, listen_port, server_ports, name)
    servers = []
    server_ports.each_with_index do |port, index|
      servers << HAProxy.server_config(name, index, my_ip, port)
    end

    config = "# Create a load balancer for the #{name} application \n"
    config << "listen #{name} #{my_ip}:#{listen_port} \n"
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

    config_path = File.join(SITES_ENABLED_PATH, "#{full_app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end


  # FIXME(cgb): make sense of this method
  def self.add_app_config(app_name, app_number, port_apps,ip)
    # Add a prefix to the app name to avoid possible conflicts
    full_app_name = "gae_#{app_name}"
    index = 0
    servers = []

    port_apps[app_name].each { |port|
      server = HAProxy.server_config(full_app_name, index, ip, port)
      index+=1
      servers << server
    }

    listen_port = HAProxy.app_listen_port(app_number)
    config = "# Create a load balancer for the app #{app_name} \n"
    config << "listen #{full_app_name} #{ip}:#{listen_port} \n"
    config << servers.join("\n")

    config_path = File.join(SITES_ENABLED_PATH, "#{full_app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }
 
    HAProxy.regenerate_config
  end


  def self.remove_app(app_name)
    config_name = "gae_#{app_name}.#{CONFIG_EXTENSION}"
    FileUtils.rm(File.join(SITES_ENABLED_PATH, config_name))
    HAProxy.regenerate_config
  end


  # FIXME(cgb): make sense of this method
  # Based on the queued requests and request rate statistics from haproxy , the function decides whether to scale up or down or 
  # whether to not have any change in number of appservers . 
  def self.auto_scale(app_name, autoscale_log)
    # Average Request rates and queued requests set to 0
    avg_req_rate = 0
    avg_queue_curr = 0

    # Get the current request rate and the currently queued requests  
    # And store the req rate for last TIME_PERIOD seconds 
    # Now calculate the average and maintain the request rate and queued requests over those last TIME_PERIOD seconds

    index = 0
    while index < ( TIME_PERIOD - 1 )
      @@req_rate[app_name][index] = @@req_rate[app_name][index+1]
      @@queue_curr[app_name][index] = @@queue_curr[app_name][index+1]
      avg_req_rate += @@req_rate[app_name][index+1].to_i
      avg_queue_curr += @@queue_curr[app_name][index+1].to_i
      index += 1
    end

    # Run this command for each app and get the queued request and request rate of requests coming in 
    monitor_cmd = `echo \"show info;show stat\" | socat stdio unix-connect:/etc/haproxy/stats | grep #{app_name} `

    monitor_cmd.each{ |line_output|
      array = line_output.split(',')
      if array.length < REQ_RATE
        next
      end
      service_name = array[SRV_NAME]
      queue_curr_present = array[QUEUE_CURR]
      req_rate_present = array[REQ_RATE]
      # Not using curr rate  as of now 
      rate_last_sec = array[CURR_RATE]

      if service_name == "FRONTEND"
        autoscale_log.puts("#{service_name} - Request Rate #{req_rate_present}")
        req_rate_present = array[REQ_RATE]
        avg_req_rate += req_rate_present.to_i
        @@req_rate[app_name][index] = req_rate_present
      end

      if service_name == "BACKEND"
        autoscale_log.puts("#{service_name} - Queued Currently #{queue_curr_present}")
        queue_curr_present = array[QUEUE_CURR]
        avg_queue_curr += queue_curr_present.to_i
        @@queue_curr[app_name][index] = queue_curr_present
      end
    }

    # Average Request rates and queued requests currently contain the aggregated sum over last TIME_PERIOD till this time
    # So we will make a decsion here based on their values , whether to scale or not
    total_queue_curr = avg_queue_curr 

    avg_req_rate /= TIME_PERIOD
    avg_queue_curr /= TIME_PERIOD

    autoscale_log.puts("Average Request rate & Avg Queued requests:#{avg_req_rate} #{avg_queue_curr}")

    # Testing the condition to check whether we should scale down number of Appservers 
    # by Checking the  queued requests at HaProxy and incoming request rate
    if avg_req_rate <= @@scale_down_req_rate[app_name] && total_queue_curr == 0 
      return :scale_down
    end

    # Condition to check whether we should scale up number of Appservers by checking the queued requests at HaProxy
    # and incoming request rate and comparing it to the threshold values of request rate and queue rate for each app
    if avg_req_rate > @@threshold_req_rate[app_name] && avg_queue_curr > @@threshold_queue_curr[app_name] 
      return :scale_up
    end
   
    # Returns :no_change as both the conditions for scaling up or scaling down number of appservers hasn't been meet
    return :no_change   
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
