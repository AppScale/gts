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
    @ip = HelperFunctions.read_file(NEAREST_TQ_LOCATION)
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
          end
        end
      }
    rescue Timeout::Error
      Djinn.log_warn("[#{callr}] SOAP call to #{@ip} timed out")
      raise FailedNodeException.new("Time out talking to #{@ip}:#{SERVER_PORT}")
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
      url = URI.parse('http://' + @ip + ":#{SERVER_PORT}/startworker")
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
      url = URI.parse('http://' + @ip + ":#{SERVER_PORT}/reloadworker")
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
      url = URI.parse('http://' + @ip + ":#{SERVER_PORT}/stopworker")
      http = Net::HTTP.new(url.host, url.port)
      response = http.post(url.path, json_config, {'Content-Type'=>'application/json'})
    }
    if response.nil?
      return {"error" => true, "reason" => "Unable to get a response"}
    end

    return JSON.load(response.body)
  end

end
