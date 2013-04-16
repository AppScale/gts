#!/usr/bin/ruby -w


# As we can't rely on DNS in AppScale, we have a Rails app, called the
# AppDashboard, that provides a single place to route users to their
# applications. It also provides authentication for users as an
# implementation of the Google App Engine Users API. This module provides
# methods that abstract away its configuration and deployment.
module LoadBalancer


  SERVER_PORTS = [8000, 8001, 8002]


  # The port which nginx will use to send requests to haproxy
  PROXY_PORT = 8060


  # The port which requests to this app will be served from
  LISTEN_PORT = 80


  LISTEN_SSL_PORT = 443


  APPSCALE_HOME = ENV['APPSCALE_HOME']

  
#  def self.start
#    env_vars = { "APPSCALE_HOME" => APPSCALE_HOME }
#
#    SERVER_PORTS.each { |port|
#      start_cmd = "/usr/bin/mongrel_rails start -c #{RAILS_ROOT} -e production -p #{port} " +
#        "-P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
#      stop_cmd = "/usr/bin/mongrel_rails stop -P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
#
#      GodInterface.start(:loadbalancer, start_cmd, stop_cmd, port, env_vars)
#    }
#
#    #`service appscale-loadbalancer start`
#  end
  def self.start(login_ip, uaserver_ip, public_ip, private_ip, secret)
    # its just another app engine app - but since numbering starts
    # at zero, this app has to be app neg one

    # TODO: tell the tools to disallow uploading apps called 'apichecker'
    # and start_appengine to do the same

    num_servers = 3
    app = "dashboard"
    app_language = "python27"

    app_manager = AppManagerClient.new()

    app_location = "/var/apps/#{app}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppDashboard/* #{app_location}")
    Djinn.log_run("mkdir -p /var/apps/#{app}/log")
    Djinn.log_run("touch /var/apps/#{app}/log/server.log")

    # Pass the secret key to the app.
    Djinn.log_run("echo \"GLOBAL_SECRET_KEY = '#{secret}'\" > #{app_location}/lib/secret_key.py")

    Collectd.write_app_config(app)

    SERVER_PORTS.each { |port|
      Djinn.log_debug("Starting #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{port}")
      pid = app_manager.start_app(app, port, uaserver_ip,
                                  PROXY_PORT, app_language, login_ip,
                                  [uaserver_ip], {})
      if pid == -1
        Djinn.log_debug("Failed to start app #{app} on #{HelperFunctions.local_ip}:#{port}")
        return false
      else
        pid_file_name = "#{APPSCALE_HOME}/.appscale/#{app}-#{port}.pid"
        HelperFunctions.write_file(pid_file_name, pid)
      end
    }

    Nginx.reload
    Collectd.restart
    return true
  end

  def self.stop
    app = "dashboard"
    Djinn.log_debug("Stopping app #{app} on #{HelperFunctions.local_ip}")
    app_manager = AppManagerClient.new()
    if app_manager.stop_app(app)
      Djinn.log_debug("Failed to start app #{app} on #{HelperFunctions.local_ip}")
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
