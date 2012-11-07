#!/usr/bin/ruby -w
# Programmer: Navraj Chohan


# Imports within Ruby's standard libraries
require 'base64'
require 'openssl'
require 'soap/rpc/driver'
require 'timeout'

# Number of seconds to wait before timing out when doing a SOAP call
MAX_TIMEOUT = 30

# This is transitional glue code as we shift from ruby to python. The 
# AppManager is written in python and hence we use a SOAP client to communicate
# between the two services
class AppManager
  attr_reader :conn, :ip

  # The port that the AppManager binds to, by default.
  SERVER_PORT = 49934

  def initialize(ip)
    @ip = ip
    
    @conn = SOAP::RPC::Driver.new("https://#{@ip}:#{SERVER_PORT}")
    @conn.add_method("start_app", "configuration")
    @conn.add_method("stop_app", "app_name")
    @conn.add_method("get_app_listing")
  end

  def make_call(timeout, retry_on_except)
    result = ""
    begin
      Timeout::timeout(timeout) do
        begin
          yield if block_given?
        end
      end
    rescue OpenSSL::SSL::SSLError
      retry
    rescue Errno::ECONNREFUSED
      if retry_on_except
        sleep(1)
        retry
      else
        abort("We were unable to establish a connection with the AppManager at the designated location. Is AppScale currently running?")
      end 
   rescue Exception => except
      if except.class == Interrupt
        abort
      end

      puts "An exception of type #{except.class} was thrown."
      retry if retry_on_except
    end
  end
  
  def start_app(app_name, 
                app_port,
                load_balancer_ip,
                load_balancer_port, 
                language, 
                xmpp_ip)
    # Wrapper for SOAP call to the AppManager to start an instance of 
    #    an application server.
    #
    # Args:
    #   app_name: Name of the application
    #   app_port: The port to run the application server
    #   load_balancer_ip: The public IP of the load balancer
    #   load_balancer_port: The port of the load balancer
    #   language: The language the application is written in
    #   xmpp_ip: The IP for XMPP
    # Returns:
    #   The PID of the process started
    
    configuration = {'app_name' => app_name,
                     'app_port' => app_port,
                     'load_balancer_ip' => load_balancer_ip,
                     'load_balancer_port' => load_balancer_port,
                     'language' => language,
                     'xmpp_ip' => xmpp_ip}
    
    result = ""
    make_call(MAX_TIME_OUT, retry_on_except) { 
      result = @conn.start_app(configuration)
    }
    return result
  end
 end
