#!/usr/bin/ruby -w

require 'base64'
require 'openssl'
require 'soap/rpc/driver'
require 'timeout'
require 'helperfunctions'

require 'rubygems'
require 'json'

# Number of seconds to wait before timing out when doing a SOAP call.
# This number should be higher than the maximum time required for remote calls
# to properly execute (i.e., starting a process may take more than 2 minutes).
MAX_TIME_OUT = 180

# This is transitional glue code as we shift from ruby to python. The 
# AppManager is written in python and hence we use a SOAP client to communicate
# between the two services.
class AppManagerClient

  # The connection to use and IP to connect to
  attr_reader :conn, :ip

  # The port that the AppManager binds to, by default.
  SERVER_PORT = 49934

  # Initialization function for AppManagerClient
  def initialize(ip)
    @ip = ip

    @conn = SOAP::RPC::Driver.new("http://#{@ip}:#{SERVER_PORT}")
    @conn.add_method("start_app", "config")
    @conn.add_method("stop_app", "app_name")
    @conn.add_method("stop_app_instance", "app_name", "port")
    @conn.add_method("restart_app_instances_for_app", "app_name", "language")
  end

  # Check the comments in AppController/lib/app_controller_client.rb.
  def make_call(time, retry_on_except, callr)
    begin
      Timeout::timeout(time) {
        begin
          yield if block_given?
        rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH,
          OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE,
          Errno::ECONNRESET, SOAP::EmptyResponseError, Exception => e
          trace = e.backtrace.join("\n")
          Djinn.log_warn("[#{callr}] exception in make_call to #{@ip}: #{e.class}\n#{trace}")
          if retry_on_except
            Kernel.sleep(1)
            retry
          else
            raise FailedNodeException.new('Exception encountered while '\
              "talking to #{@ip}:#{SERVER_PORT}.")
          end
        end
      }
    rescue Timeout::Error
      Djinn.log_warn("[#{callr}] SOAP call to #{@ip} timed out")
      raise FailedNodeException.new("Time out talking to #{@ip}:#{SERVER_PORT}")
    end
  end

  # Wrapper for SOAP call to the AppManager to start an process instance of
  # an application server.
  #
  # Args:
  #   app_name: Name of the application
  #   app_port: The port to run the application server
  #   load_balancer_ip: The public IP of the load balancer
  #   load_balancer_port: The port of the load balancer
  #   language: The language the application is written in
  #   xmpp_ip: The IP for XMPP
  #   db_locations: An Array of datastore server IPs
  #   env_vars: A Hash of environemnt variables that should be passed to the
  #     application to start.
  #   max_memory: An Integer that names the maximum amount of memory (in
  #     megabytes) that should be used for this App Engine app.
  # Returns:
  #   The PID of the process started
  # Note:
  #   We currently send hashes over in SOAP using json because
  #   of incompatibilities between SOAP mappings from ruby to python.
  #   As we convert over to python we should use native dictionaries.
  #
  def start_app(app_name,
                app_port,
                load_balancer_ip,
                language,
                xmpp_ip,
                db_locations,
                env_vars,
                max_memory=500)
    config = {'app_name' => app_name,
              'app_port' => app_port,
              'load_balancer_ip' => load_balancer_ip,
              'language' => language,
              'xmpp_ip' => xmpp_ip,
              'dblocations' => db_locations,
              'env_vars' => env_vars,
              'max_memory' => max_memory}
    json_config = JSON.dump(config)
    result = ""
    make_call(MAX_TIME_OUT, false, "start_app") {
      result = @conn.start_app(json_config)
    }
    return result
  end

  # Wrapper for SOAP call to the AppManager to stop an application
  # process instance from the current host.
  #
  # Args:
  #   app_name: The name of the application
  #   port: The port the process instance of the application is running
  # Returns:
  #   True on success, False otherwise
  #
  def stop_app_instance(app_name, port)
    result = ""
    make_call(MAX_TIME_OUT, false, "stop_app_instance") {
      result = @conn.stop_app_instance(app_name, port)
    }
    return result
  end

  # Wrapper for SOAP call to the AppManager to remove an application
  # from the current host.
  # 
  # Args:
  #   app_name: The name of the application
  # Returns:
  #   True on success, False otherwise
  #
  def stop_app(app_name)
    result = ""
    make_call(MAX_TIME_OUT, false, "stop_app") {
      result = @conn.stop_app(app_name)
    }
    return result
  end

  # Wrapper for SOAP call to the AppManager to kill all the processes running
  # the named application.
  #
  # Args:
  #   app_name: A String representing the name of the application.
  #   language: A String, the language the app is written in.
  # Returns:
  #   An Array of process IDs that were killed, that had been hosting the app.
  def restart_app_instances_for_app(app_name, language)
    result = ""
    make_call(MAX_TIME_OUT, false, "restart_app_instances_for_app") {
      result = @conn.restart_app_instances_for_app(app_name, language)
    }
    return result
  end
end
