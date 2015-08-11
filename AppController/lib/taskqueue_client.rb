#!/usr/bin/ruby -w

require 'base64'
require 'helperfunctions'
require 'json'
require 'net/http'
require 'timeout'

# Number of seconds to wait before timing out when doing a remote call.
# This number should be higher than the maximum time required for remote calls
# to properly execute (i.e., starting a process may take more than 2 minutes).
MAX_TIME_OUT = 180

# This is transitional glue code as we shift from ruby to python. The 
# Taskqueue server is written in python and hence we use a REST client 
# to communicate between the two services.
class TaskQueueClient

  # The connection to use and IP to connect to.
  attr_reader :conn, :ip

  # The port that the TaskQueue Server binds to.
  SERVER_PORT = 64839

  # Location of where the nearest taskqueue server is.
  NEAREST_TQ_LOCATION = '/etc/appscale/rabbitmq_ip'

  # Initialization function for TaskQueueClient
  def initialize()
    @host = HelperFunctions.read_file(NEAREST_TQ_LOCATION)
  end


  # Provides automatic retry logic for transient SOAP errors. This code is
  # used in few others client (it should be made in a library):
  #   lib/infrastructure_manager_client.rb
  #   lib/user_app_client.rb
  #   lib/taskqueue_client.rb
  #   lib/app_manager_client.rb
  #   lib/app_controller_client.rb
  # Modification in this function should be reflected on the others too.
  #
  # Args:
  #   time: A Fixnum that indicates how long the timeout should be set to when
  #     executing the caller's block.
  #   retry_on_except: A boolean that indicates if non-transient Exceptions
  #     should result in the caller's block being retried or not.
  #   callr: A String that names the caller's method, used for debugging
  #     purposes.
  #
  # Raises:
  #   FailedNodeException: if the given block contacted a machine that
  #     is either not running or is rejecting connections.
  #   SystemExit: If a non-transient Exception was thrown when executing the
  #     given block.
  # Returns:
  #   The result of the block that was executed, or nil if the timeout was
  #   exceeded.
  def make_call(time, retry_on_except, callr)
    refused_count = 0
    max = 5

    # Do we need to retry at all?
    if not retry_on_except
      refused_count = max + 1
    end

    begin
      Timeout::timeout(time) {
        yield if block_given?
      }
    rescue Timeout::Error
      Djinn.log_warn("[#{callr}] SOAP call to #{@ip} timed out")
      raise FailedNodeException.new("Time out: is the AppController running?")
    rescue Errno::ECONNREFUSED, Errno::EHOSTUNREACH,
      OpenSSL::SSL::SSLError, NotImplementedError, Errno::EPIPE,
      Errno::ECONNRESET, SOAP::EmptyResponseError, Exception => e
      trace = e.backtrace.join("\n")
      Djinn.log_warn("[#{callr}] exception in make_call to #{@ip}: #{e.class}\n#{trace}")
      if refused_count > max
        raise FailedNodeException.new("[#{callr}] failed to interact with #{@ip}.")
      else
        refused_count += 1
        Kernel.sleep(3)
        retry
      end
    end
  end


  # Wrapper for REST calls to the TaskQueue Server to start a
  # taskqueue worker on a taskqueue node.
  #
  # Args:
  #   app_name: Name of the application.
  # Returns:
  #   JSON response.
  def start_worker(app_name)
    config = {'app_id' => app_name, 'command' => 'update'}
    json_config = JSON.dump(config)
    response = nil
     
    make_call(MAX_TIME_OUT, false, "start_worker"){
      url = URI.parse('http://' + @host + ":#{SERVER_PORT}/startworker")
      http = Net::HTTP.new(url.host, url.port)
      response = http.post(url.path, json_config, {'Content-Type'=>'application/json'})
    }
    if response.nil?
      return {"error" => true, "reason" => "Unable to get a response"}
    end

    return JSON.load(response.body)
  end

  # Wrapper for REST calls to the TaskQueue Server to reload a
  # taskqueue worker on a taskqueue node.
  #
  # Args:
  #   app_name: Name of the application.
  # Returns:
  #   JSON response.
  def reload_worker(app_name)
    config = {'app_id' => app_name, 'command' => 'update'}
    json_config = JSON.dump(config)
    response = nil
     
    make_call(MAX_TIME_OUT, false, "reload_worker"){
      url = URI.parse('http://' + @host + ":#{SERVER_PORT}/reloadworker")
      http = Net::HTTP.new(url.host, url.port)
      response = http.post(url.path, json_config, {'Content-Type'=>'application/json'})
    }
    if response.nil?
      return {"error" => true, "reason" => "Unable to get a response"}
    end

    return JSON.load(response.body)
  end


  # Wrapper for REST calls to the TaskQueue Server to stop a
  # taskqueue worker on a taskqueue node.
  #
  # Args:
  #   app_name: Name of the application.
  # Returns:
  #   JSON response.
  def stop_worker(app_name)
    config = {'app_id' => app_name, 
              'command' => 'update'}
    json_config = JSON.dump(config)
    response = nil
    make_call(MAX_TIME_OUT, false, "stop_worker"){
      url = URI.parse('http://' + @host + ":#{SERVER_PORT}/stopworker")
      http = Net::HTTP.new(url.host, url.port)
      response = http.post(url.path, json_config, {'Content-Type'=>'application/json'})
    }
    if response.nil?
      return {"error" => true, "reason" => "Unable to get a response"}
    end

    return JSON.load(response.body)
  end

end
