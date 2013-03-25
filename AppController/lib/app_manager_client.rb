#!/usr/bin/ruby -w
# Programmer: Navraj Chohan <nlake44@gmail.com>

require 'base64'
require 'json'
require 'openssl'
require 'soap/rpc/driver'
require 'timeout'
require 'helperfunctions'

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

  # Connect to localhost for the AppManager. Outside connections are not 
  # allowed for security reasons.
  SERVER_IP = 'localhost'

  # The port that the AppManager binds to
  SERVER_PORT = 49934

  # Initialization function for AppManagerClient
  #
  def initialize()
    @conn = SOAP::RPC::Driver.new("http://#{SERVER_IP}:#{SERVER_PORT}")
    @conn.add_method("start_app", "config")
    @conn.add_method("stop_app", "app_name")
    @conn.add_method("stop_app_instance", "app_name", "port")
  end

  # Make a SOAP call out to the AppManager. 
  # 
  # Args: 
  #   timeout: The maximum time to wait on a remote call
  #   retry_on_except: Boolean if we should keep retrying the 
  #     the call
  # Returns:
  #   The result of the remote call.
  # TODO: 
  #   This code was copy/pasted from app_controller_client 
  #   and can be factored out to a library. Note this for 
  #   the transition to the python port.
  #
  def make_call(timeout, retry_on_except, callr)
    result = ""
    Djinn.log_debug("Calling the AppManager - #{callr}")
    begin
      Timeout::timeout(timeout) do
        begin
          yield if block_given?
        end
      end
    rescue OpenSSL::SSL::SSLError
      Djinn.log_debug("Saw a SSLError when calling #{callr}" +
        " - trying again momentarily.")
      retry
    rescue Errno::ECONNREFUSED => except
      if retry_on_except
        Djinn.log_debug("Saw a connection refused when calling #{callr}" +
          " - trying again momentarily.")
        sleep(1)
        retry
      else
        trace = except.backtrace.join("\n")
        abort("We saw an unexpected error of the type #{except.class} with the following message:\n#{except}, with trace: #{trace}")
      end 
   rescue Exception => except
      if except.class == Interrupt
        abort
      end

      Djinn.log_debug("An exception of type #{except.class} was thrown: #{except}.")
      retry if retry_on_except
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
                 load_balancer_port, 
                 language, 
                 xmpp_ip,
                 db_locations,
                 env_vars)
    config = {'app_name' => app_name,
              'app_port' => app_port,
              'load_balancer_ip' => load_balancer_ip,
              'load_balancer_port' => load_balancer_port,
              'language' => language,
              'xmpp_ip' => xmpp_ip,
              'dblocations' => db_locations,
              'env_vars' => env_vars}
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
      result = @conn.stop_app(app_name, port)
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
end
