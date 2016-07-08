#!/usr/bin/ruby -w

# As we can't rely on DNS in AppScale, we have an app, called the
# AppDashboard, that provides a single place to route users to their
# applications. It also provides authentication for users as an
# implementation of the Google App Engine Users API. This module provides
# methods that abstract away its configuration and deployment.
module AppDashboard

  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8060


  # The port which requests to this app will be served from
  LISTEN_PORT = 1080


  LISTEN_SSL_PORT = 1443


  APPSCALE_HOME = ENV['APPSCALE_HOME']


  # The Google App Engine appid for the Dashboard app.
  APP_NAME = "appscaledashboard"


  # Language the AppDashboard is written in.
  APP_LANGUAGE = "python27"


  # Starts the AppDashboard on this machine. Does not configure or start nginx
  # or haproxy, which are needed to load balance traffic to the AppDashboard
  # instances we start here.
  #
  # Args:
  #   public_ip: This machine's public IP address or FQDN.
  #   private_ip: This machine's private IP address or FQDN.
  #   persistent_storage: Where we store the application tarball.
  #   secret: A String that is used to authenticate this application with
  #     other AppScale services.
  # Returns:
  #   true if the AppDashboard was started successfully, and false otherwise.
  def self.start(public_ip, private_ip, persistent_storage, secret)

    # Pass the secret key and our public IP address (needed to connect to the
    # AppController) to the app.
    Djinn.log_run("echo \"GLOBAL_SECRET_KEY = '#{secret}'\" > #{APPSCALE_HOME}/AppDashboard/lib/secret_key.py")
    Djinn.log_run("echo \"MY_PUBLIC_IP = '#{public_ip}'\" > #{APPSCALE_HOME}/AppDashboard/lib/local_host.py")
    Djinn.log_run("echo \"UA_SERVER_IP = '#{private_ip}'\" > #{APPSCALE_HOME}/AppDashboard/lib/uaserver_host.py")

    # TODO: tell the tools to disallow uploading apps called 
    # APP_NAME, and have start_appengine to do the same.   
    app_location = "#{persistent_storage}/apps/#{APP_NAME}.tar.gz"
    Djinn.log_run("tar -czf #{app_location} -C #{APPSCALE_HOME}/AppDashboard .")

    # Tell the app what nginx port sits in front of it.
    port_file = "/etc/appscale/port-#{APP_NAME}.txt"
    HelperFunctions.write_file(port_file, "#{LISTEN_PORT}")

    # Restore repo template values.
    Djinn.log_run("echo \"GLOBAL_SECRET_KEY = 'THIS VALUE WILL BE OVERWRITTEN ON STARTUP'\" > #{APPSCALE_HOME}/AppDashboard/lib/secret_key.py")
    Djinn.log_run("echo \"MY_PUBLIC_IP = 'THIS VALUE WILL BE OVERWRITTEN ON STARTUP'\" > #{APPSCALE_HOME}/AppDashboard/lib/local_host.py")
    Djinn.log_run("echo \"UA_SERVER_IP = 'THIS VALUE WILL BE OVERWRITTEN ON STARTUP'\" > #{APPSCALE_HOME}/AppDashboard/lib/uaserver_host.py")

    Djinn.log_debug("Done setting dashboard.")

    return true
  end


  # Stops all AppServers running the AppDashboard on this machine.
  # Returns:
  #   true if the AppDashboard was stopped successfully, and false otherwise.
  def self.stop()
    Djinn.log_info("Stopping app #{APP_NAME} on #{HelperFunctions.local_ip()}")
    app_manager = AppManagerClient.new(HelperFunctions.local_ip())

    app_stopped = false
    begin
      app_stopped = app_manager.stop_app(APP_NAME)
    rescue FailedNodeException
      app_stopped = false
    end

    unless app_stopped
      Djinn.log_error("Failed to stop app #{APP_NAME} on #{HelperFunctions.local_ip()}")
    end

    return app_stopped
  end

end
