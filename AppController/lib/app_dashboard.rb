#!/usr/bin/ruby -w


# As we can't rely on DNS in AppScale, we have an app, called the
# AppDashboard, that provides a single place to route users to their
# applications. It also provides authentication for users as an
# implementation of the Google App Engine Users API. This module provides
# methods that abstract away its configuration and deployment.
module AppDashboard


  SERVER_PORTS = [8000, 8001, 8002]


  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8060


  # The port which requests to this app will be served from
  LISTEN_PORT = 80


  LISTEN_SSL_PORT = 443


  APPSCALE_HOME = ENV['APPSCALE_HOME']


  # The name that nginx uses when writing configuration files for the Dashboard.
  # TODO(cgb): Consolidate this with APP_NAME.
  NGINX_APP_NAME = "as_adb"


  # The Google App Engine appid for the Dashboard app.
  APP_NAME = "appscaledashboard"


  # Language the AppDashboard is written in.
  APP_LANGUAGE = "python27"


  # The path on the local filesystem where static files can be served from.
  PUBLIC_DIRECTORY = "#{APPSCALE_HOME}/AppDashboard/static"


  # Starts the AppDashboard on this machine. Does not configure or start nginx
  # or haproxy, which are needed to load balance traffic to the AppDashboard
  # instances we start here.
  #
  # Args:
  #   login_ip: The hostname where nginx runs, serving a full proxy to Google
  #     App Engine applications hosted in this AppScale deployment.
  #   uaserver_ip: The hostname where the UserAppServer runs, enabling new users
  #     to be created and new apps to be uploaded.
  #   public_ip: This machine's public IP address or FQDN.
  #   private_ip: This machine's private IP address or FQDN.
  #   secret: A String that is used to authenticate this application with
  #     other AppScale services.
  # Returns:
  #   true if the AppDashboard was started successfully, and false otherwise.
  def self.start(login_ip, uaserver_ip, public_ip, private_ip, secret)
    # TODO: tell the tools to disallow uploading apps called 'apichecker'
    # or APP_NAME, and have start_appengine to do the same.   
    app_manager = AppManagerClient.new()

    app_location = "/var/apps/#{APP_NAME}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppDashboard/* #{app_location}")
    Djinn.log_run("mkdir -p /var/apps/#{APP_NAME}/log")
    Djinn.log_run("touch /var/apps/#{APP_NAME}/log/server.log")

    # Pass the secret key and our public IP address (needed to connect to the
    # AppController) to the app.
    Djinn.log_run("echo \"GLOBAL_SECRET_KEY = '#{secret}'\" > #{app_location}/lib/secret_key.py")
    Djinn.log_run("echo \"MY_PUBLIC_IP = '#{public_ip}'\" > #{app_location}/lib/local_host.py")

    Djinn.log_info("Starting #{APP_LANGUAGE} app #{APP_NAME}")
    SERVER_PORTS.each { |port|
      Djinn.log_debug("Starting #{APP_LANGUAGE} app #{APP_NAME} on #{HelperFunctions.local_ip}:#{port}")
      pid = app_manager.start_app(APP_NAME, port, uaserver_ip,
                                  PROXY_PORT, APP_LANGUAGE, login_ip,
                                  [uaserver_ip], {})
      if pid == -1
        Djinn.log_error("Failed to start app #{APP_NAME} on #{HelperFunctions.local_ip}:#{port}")
        return false
      else
        pid_file_name = "/etc/appscale/#{APP_NAME}-#{port}.pid"
        HelperFunctions.write_file(pid_file_name, pid)
      end
    }

    begin
      Djinn.log_info("Priming AppDashboard's cache")
      start_time = Time.now
      url = URI.parse("http://#{HelperFunctions.local_ip}:#{SERVER_PORTS[0]}/status/refresh")
      http = Net::HTTP.new(url.host, url.port)
      response = http.get(url.path)
      end_time = Time.now
      Djinn.log_debug("It took #{end_time - start_time} seconds to prime the AppDashboard's cache")
    rescue Exception => e
      # Don't crash the AppController because we weren't able to refresh the
      # AppDashboard - just continue on.
      Djinn.log_debug("Couldn't prime the AppDashboard's cache because of " +
        "a #{e.class} exception.")
    end

    Nginx.reload
    return true
  end


  # Stops all AppServers running the AppDashboard on this machine.
  # Returns:
  #   true if the AppDashboard was stopped successfully, and false otherwise.
  def self.stop
    Djinn.log_info("Stopping app #{APP_NAME} on #{HelperFunctions.local_ip}")
    app_manager = AppManagerClient.new()
    if app_manager.stop_app(APP_NAME)
      Djinn.log_error("Failed to start app #{APP_NAME} on #{HelperFunctions.local_ip}")
      return false
    else
      return true
    end
  end


  # Kills all AppServers hosting the AppDashboard, and then starts new
  # AppServers to host it.
  # Returns:
  #   true if the AppDashboard started successfully, and false otherwise.
  def self.restart
    self.stop
    self.start
  end


end
