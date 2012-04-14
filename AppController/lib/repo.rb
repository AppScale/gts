#!/usr/bin/ruby -w


require 'net/http'
require 'uri'
require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'


$:.unshift File.join(File.dirname(__FILE__), "..")
require 'djinn'


# Neptune jobs need to store and retrieve data within AppScale, so we have
# a special Google App Engine application that always runs that acts as
# a repository (here, shortened to "the Repo") for this data. This class
# provides methods that automatically start the Repo and configure it
# as needed.
class Repo


  # The port that nginx should provide access to the Repo app on, by default.
  SERVER_PORT = 8079


  def self.init(public_ip, private_ip, secret)
    @@ip = public_ip
    @@private_ip = private_ip
    @@secret = secret
  end


  # So since we can't expose reading class variables directly, this method
  # exposes just what we need - where the Repo app is hosted.
  def self.get_public_ip()
    return @@ip
  end

  # Starts the Repo application. Since it's a Google App Engine app, we throw
  # up all the usual services for it (nginx/haproxy/AppServers), and wait for
  # them to start up. We don't register the app with the UAServer right now
  # since we don't necessarily want users accessing it.
  # TODO(cgb): Let it register with the UAServer but change the Repo app to
  # prevent unauthorized access.
  def self.start(login_ip, uaserver_ip)
    # its just another app engine app - but since numbering starts
    # at zero, this app has to be app neg one

    # TODO: tell the tools to disallow uploading apps called 'therepo'
    # and start_appengine to do the same

    num_servers = 3
    app_number = -1
    app = "therepo"
    app_language = "python"
    app_version = "1"

    app_location = "/var/apps/#{app}/app"
    Djinn.log_run("mkdir -p #{app_location}")
    Djinn.log_run("cp -r #{APPSCALE_HOME}/AppServer/demos/therepo/* #{app_location}")
    HelperFunctions.setup_app(app, untar=false)

    repo_main_code = "#{app_location}/repo.py"
    file_w_o_secret = HelperFunctions.read_file(repo_main_code)
    file_w_secret = file_w_o_secret.gsub("PLACE SECRET HERE", @@secret)
    HelperFunctions.write_file(repo_main_code, file_w_secret)

    static_handlers = HelperFunctions.parse_static_data(app)
    proxy_port = HAProxy.app_listen_port(app_number)
    Nginx.write_app_config(app, app_number, @@ip, proxy_port, static_handlers, login_ip)
    HAProxy.write_app_config(app, app_number, num_servers, @@private_ip)
    Collectd.write_app_config(app)

    [19997, 19998, 19999].each { |port|
      Djinn.log_debug("Starting #{app_language} app #{app} on #{HelperFunctions.local_ip}:#{port}")
      pid = HelperFunctions.run_app(app, port, uaserver_ip, @@ip, @@private_ip, app_version, app_language, SERVER_PORT, login_ip)
      pid_file_name = "#{APPSCALE_HOME}/.appscale/#{app}-#{port}.pid"
      HelperFunctions.write_file(pid_file_name, pid)
    }

    Nginx.reload
    Collectd.restart
  end


  # Stops the Repo app.
  # TODO(cgb): This kills all AppServers, which definitely is not the correct
  # thing to do. Since the Repo is an App Engine app, we should be able to use
  # the other functions that stop App Engine apps here as well.
  def self.stop
    Djinn.log_debug(`pkill -f dev_appserver`)
    Djinn.log_debug(`pkill -f DevAppServerMain`)
  end


end

