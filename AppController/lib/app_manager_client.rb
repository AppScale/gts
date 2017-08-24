#!/usr/bin/ruby -w

require 'json'
require 'net/http'
require 'helperfunctions'

# Number of seconds to wait before timing out when making a call to the
# AppManager. Starting a process may take more than 2 minutes.
MAX_TIME_OUT = 180

class AppManagerClient

  # The port that the AppManager binds to, by default.
  SERVER_PORT = 17445

  # Initialization function for AppManagerClient
  def initialize(ip)
    @ip = ip
  end

  def make_call(request, uri)
    begin
      response = Net::HTTP.start(uri.hostname, uri.port,
                                 :read_timeout => MAX_TIME_OUT) do |http|
        http.request(request)
      end
      if response.code != '200'
        raise FailedNodeException.new("AppManager error: #{response.body}")
      end
    rescue Errno::ECONNREFUSED, Errno::ETIMEDOUT
      raise FailedNodeException.new("Call to AppManager timed out")
    end
  end

  # Starts an AppServer instance with the AppManager.
  #
  # Args:
  #   app_name: Name of the application
  #   service_id: The AppServer's service ID.
  #   version_id: The AppServer's version ID.
  #   app_port: The port to run the application server
  #   env_vars: A Hash of environemnt variables that should be passed to the
  #     application to start.
  #
  def start_app(app_name,
                service_id,
                version_id,
                app_port)
    config = {'app_port' => app_port,
              'service_id' => service_id,
              'version_id' => version_id}

    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{app_name}")
    headers = {'Content-Type' => 'application/json'}
    request = Net::HTTP::Post.new(uri.path, headers)
    request.body = JSON.dump(config)
    make_call(request, uri)
  end

  # Stops an AppServer instance with the AppManager.
  #
  # Args:
  #   version_key: The name of the version
  #   port: The port the process instance of the application is running
  #
  def stop_app_instance(version_key, port)
    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{version_key}/#{port}")
    request = Net::HTTP::Delete.new(uri.path)
    make_call(request, uri)
  end

  # Stops all AppServer instances for a version with the AppManager.
  #
  # Args:
  #   version_key: The name of the version
  #
  def stop_app(version_key)
    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{version_key}")
    request = Net::HTTP::Delete.new(uri.path)
    make_call(request, uri)
  end
end
