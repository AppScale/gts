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
  APP_NAME = 'appscaledashboard'.freeze

  # Language the AppDashboard is written in.
  APP_LANGUAGE = 'python27'.freeze

  # Prepares the dashboard's source archive.
  #
  # Args:
  #   public_ip: This machine's public IP address or FQDN.
  #   private_ip: This machine's private IP address or FQDN.
  #   persistent_storage: Where we store the application tarball.
  #   datastore_location: The location of a datastore load balancer.
  # Returns:
  #   A string specifying the location of the prepared archive.
  def self.prep(public_ip, private_ip, persistent_storage, datastore_location)
    # Write deployment-specific information that the dashboard needs.
    lib_dir = File.join(APPSCALE_HOME, 'AppDashboard', 'lib')
    lib_contents = {
      'local_host.py' => "MY_PUBLIC_IP = '#{public_ip}'",
      'uaserver_host.py' => "UA_SERVER_IP = '#{private_ip}'",
      'datastore_location.py' => "DATASTORE_LOCATION = '#{datastore_location}'"
    }
    lib_contents.each {|lib_file, contents|
      lib_file = File.join(lib_dir, lib_file)
      begin
        contents_differ = File.read(lib_file) != contents
      rescue Errno::ENOENT
        contents_differ = true
      end
      if contents_differ
        File.open(lib_file, 'w') { |file| file.write(contents) }
      end
    }

    # TODO: tell the tools to disallow uploading apps called
    # APP_NAME, and have start_appengine to do the same.
    app_location = "#{persistent_storage}/apps/#{APP_NAME}.tar.gz"
    Djinn.log_run(
      "GZIP=-n tar -czf #{app_location} -C #{APPSCALE_HOME}/AppDashboard .")

    # Tell the app what nginx port sits in front of it.
    version_key = [APP_NAME, Djinn::DEFAULT_SERVICE,
                   Djinn::DEFAULT_VERSION].join(Djinn::VERSION_PATH_SEPARATOR)
    port_file = "/etc/appscale/port-#{version_key}.txt"
    HelperFunctions.write_file(port_file, LISTEN_PORT.to_s)

    Djinn.log_debug('Done setting dashboard.')

    app_location
  end

  # Stops all AppServers running the AppDashboard on this machine.
  # Returns:
  #   true if the AppDashboard was stopped successfully, and false otherwise.
  def self.stop
    Djinn.log_info("Stopping app #{APP_NAME} on #{HelperFunctions.local_ip}")
    app_manager = AppManagerClient.new(HelperFunctions.local_ip)

    app_stopped = false
    begin
      app_manager.stop_app(APP_NAME)
      app_stopped = true
    rescue FailedNodeException
      app_stopped = false
    end

    unless app_stopped
      Djinn.log_error("Failed to stop app #{APP_NAME} on " \
        "#{HelperFunctions.local_ip}")
    end

    app_stopped
  end
end
