#!/usr/bin/ruby -w


require 'net/http'
require 'uri'
require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'app_manager_client'
require 'helperfunctions'

$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'


# Google App Engine application that always runs, checking the API
# stats.
class ApiChecker


  # The port that nginx should provide access to the API checker 
  # app on, by default.
  SERVER_PORT = 8079

  # AppScale home path.
  APPSCALE_HOME = ENV['APPSCALE_HOME']


  def self.init(public_ip, private_ip, secret)
    @@ip = public_ip
    @@private_ip = private_ip
    @@secret = secret
  end


  # So since we can't expose reading class variables directly, this method
  # exposes just what we need - where the API checker app is hosted.
  def self.get_public_ip()
    return @@ip
  end

  # Starts the API checker application. Since it's a Google App Engine 
  # app, we throw up all the usual services for it 
  # (nginx/haproxy/AppServers), and wait for
  # them to start up. We don't register the app with the UAServer right now
  # since we don't necessarily want users accessing it.
  # TODO(cgb): Let it register with the UAServer but change the apichecker 
  # app to prevent unauthorized access.
  # 
  # Args: 
  #   login_ip: The IP of the load balancer
  #   uaserver_ip: The IP of a UserAppServer
  # Returns:
  #   return true on success, false otherwise
  def self.start(login_ip, uaserver_ip)
    # its just another app engine app - but since numbering starts
    # at zero, this app has to be app neg one

    # TODO: tell the tools to disallow uploading apps called 'apichecker'
    # and start_appengine to do the same

    num_servers = 1
    app_number = -1
    app = "apichecker"
    app_language = "python27"

    # Tell the app what nginx port sits in front of it.
    port_file = "/etc/appscale/port-#{app}.txt"
    HelperFunctions.write_file(port_file, "#{SERVER_PORT}")

    app_manager = AppManagerClient.new(HelperFunctions.local_ip())

    app_location = "/var/apps/#{app}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppServer/demos/apichecker/* #{app_location}")
    HelperFunctions.setup_app(app, untar=false)

    apichecker_main_code = "#{app_location}/apichecker.py"
    file_w_o_secret = HelperFunctions.read_file(apichecker_main_code)
    file_w_secret = file_w_o_secret.gsub("PLACE SECRET HERE", @@secret)
    HelperFunctions.write_file(apichecker_main_code, file_w_secret)

    static_handlers = HelperFunctions.parse_static_data(app)
    proxy_port = HAProxy.app_listen_port(app_number)
    http_port = SERVER_PORT
    https_port = Nginx.get_ssl_port_for_app(http_port)
    Nginx.write_app_config(app, http_port, https_port, @@ip, @@private_ip,
      proxy_port, static_handlers, login_ip)
    HAProxy.write_app_config(app, app_number, num_servers, @@private_ip)

    Djinn.log_info("Starting #{app_language} app #{app}")
    [19999].each { |port|
      Djinn.log_debug("Starting #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{port}")
      pid = app_manager.start_app(app, port, uaserver_ip, app_language,
        login_ip, [uaserver_ip], {})
      if pid == -1
        Djinn.log_error("Failed to start app #{app} on #{HelperFunctions.local_ip}:#{port}")
        return false
      else
        pid_file_name = "#{APPSCALE_HOME}/.appscale/#{app}-#{port}.pid"
        HelperFunctions.write_file(pid_file_name, pid)
      end
    }

    Nginx.reload
    return true
  end


  # Stops the API checker app.
  #
  def self.stop
    Djinn.log_info("Stopping apichecker on #{HelperFunctions.local_ip}")
    app_manager = AppManagerClient.new(HelperFunctions.local_ip())
    if app_manager.stop_app("apichecker")
      Djinn.log_error("Failed to stop apichecker on #{HelperFunctions.local_ip}")
    end
  end

end
