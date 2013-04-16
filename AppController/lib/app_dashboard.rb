#!/usr/bin/ruby -w


# As we can't rely on DNS in AppScale, we have a app, called the
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

  # Name for the AppDashboard app.
  APP_NAME = "appscaledashboard"

  # Language the AppDashboard is written in.
  APP_LANGUAGE = "python27"
  
  def self.start(login_ip, uaserver_ip, public_ip, private_ip, secret)
    # It's just another app engine app - but since numbering starts
    # at zero, this app has to be app neg one

    # TODO: tell the tools to disallow uploading apps called 'apichecker'
    # and start_appengine to do the same


    app_manager = AppManagerClient.new()

    app_location = "/var/apps/#{APP_NAME}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppDashboard/* #{app_location}")
    Djinn.log_run("mkdir -p /var/apps/#{APP_NAME}/log")
    Djinn.log_run("touch /var/apps/#{APP_NAME}/log/server.log")

    #pass the secret key to the app
    Djinn.log_run("echo \"GLOBAL_SECRET_KEY = '#{secret}'\" > #{app_location}/lib/secret_key.py")
    Collectd.write_app_config(APP_NAME)

    SERVER_PORTS.each { |port|
      Djinn.log_debug("Starting #{APP_LANGUAGE} app #{APP_NAME} on #{HelperFunctions.local_ip}:#{port}")
      pid = app_manager.start_app(app, port, uaserver_ip,
                                  PROXY_PORT, APP_LANGUAGE, login_ip,
                                  [uaserver_ip], {})
      if pid == -1
        Djinn.log_debug("Failed to start app #{APP_NAME} on #{HelperFunctions.local_ip}:#{port}")
        return false
      else
        pid_file_name = "#{APPSCALE_HOME}/.appscale/#{APP_NAME}-#{port}.pid"
        HelperFunctions.write_file(pid_file_name, pid)
      end
    }

    Nginx.reload
    Collectd.restart
    return true
  end

  def self.stop
    Djinn.log_debug("Stopping app #{APP_NAME} on #{HelperFunctions.local_ip}")
    app_manager = AppManagerClient.new()
    if app_manager.stop_app(APP_NAME)
      Djinn.log_debug("Failed to start app #{APP_NAME} on #{HelperFunctions.local_ip}")
    end
  end


  def self.restart
    self.stop
    self.start
  end

  def self.name
    "as_alb"
  end

  def self.public_directory
    "/root/appscale/AppDashboard/static"
  end

  def self.listen_port
    LISTEN_PORT
  end

  def self.listen_ssl_port
    LISTEN_SSL_PORT
  end

  def self.server_ports
    SERVER_PORTS
  end

  def self.proxy_port
    PROXY_PORT
  end
end
