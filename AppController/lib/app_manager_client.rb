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
  #   app_port: The port to run the application server
  #   login_ip: The public IP of this deployemnt
  #   load_balancer_port: The port of the load balancer
  #   language: The language the application is written in
  #   env_vars: A Hash of environemnt variables that should be passed to the
  #     application to start.
  #   max_memory: An Integer that names the maximum amount of memory (in
  #     megabytes) that should be used for this App Engine app.
  #   syslog_server: The IP address of the remote syslog server to use.
  #
  def start_app(app_name,
                app_port,
                login_ip,
                language,
                env_vars,
                max_memory=500,
                syslog_server="")
    config = {'app_port' => app_port,
              'login_ip' => login_ip,
              'language' => language,
              'env_vars' => env_vars,
              'max_memory' => max_memory,
              'syslog_server' => syslog_server}

    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{app_name}")
    headers = {'Content-Type' => 'application/json'}
    request = Net::HTTP::Post.new(uri.path, headers)
    request.body = JSON.dump(config)
    make_call(request, uri)
  end

  # Stops an AppServer instance with the AppManager.
  #
  # Args:
  #   app_name: The name of the application
  #   port: The port the process instance of the application is running
  #
  def stop_app_instance(app_name, port)
    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{app_name}/#{port}")
    request = Net::HTTP::Delete.new(uri.path)
    make_call(request, uri)
  end

  # Stops all AppServer instances for a project with the AppManager.
  #
  # Args:
  #   app_name: The name of the application
  #
  def stop_app(app_name)
    uri = URI("http://#{@ip}:#{SERVER_PORT}/projects/#{app_name}")
    request = Net::HTTP::Delete.new(uri.path)
    make_call(request, uri)
  end
end
