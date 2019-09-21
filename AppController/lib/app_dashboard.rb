#!/usr/bin/ruby -w

# As we can't rely on DNS in AppScale, we have an app, called the
# AppDashboard, that provides a single place to route users to their
# applications. It also provides authentication for users as an
# implementation of the Google App Engine Users API. This module provides
# methods that abstract away its configuration and deployment.
module AppDashboard
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
  #   private_ip: This machine's private IP address or FQDN.
  #   persistent_storage: Where we store the application tarball.
  #   datastore_location: The location of a datastore load balancer.
  #   taskqueue_location: The location of a taskqueue load balancer.
  # Returns:
  #   A string specifying the location of the prepared archive.
  def self.prep(private_ip, persistent_storage, datastore_location,
                taskqueue_location, ua_server_location)
    # Write deployment-specific information that the dashboard needs.
    lib_dir = File.join(APPSCALE_HOME, 'AppDashboard', 'lib')
    lib_contents = {
      'admin_server_location.py' => "ADMIN_SERVER_LOCATION = '#{private_ip}'",
      'controller_location.py' => "CONTROLLER_LOCATION = '#{private_ip}'",
      'uaserver_location.py' => "UA_SERVER_LOCATION = '#{ua_server_location}'",
      'datastore_location.py' => "DATASTORE_LOCATION = '#{datastore_location}'",
      'taskqueue_location.py' => "TASKQUEUE_LOCATION = '#{taskqueue_location}'"
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
    FileUtils.mkdir_p "#{persistent_storage}/apps"
    Djinn.log_info("Creating #{app_location}")
    system({'GZIP' => '-n'},
           "tar -czf #{app_location} -C #{APPSCALE_HOME}/AppDashboard .")

    # Tell the app what nginx port sits in front of it.
    version_key = [APP_NAME, Djinn::DEFAULT_SERVICE,
                   Djinn::DEFAULT_VERSION].join(Djinn::VERSION_PATH_SEPARATOR)
    port_file = "/etc/appscale/port-#{version_key}.txt"
    HelperFunctions.write_file(port_file, LISTEN_PORT.to_s)

    Djinn.log_debug('Done setting dashboard.')

    app_location
  end
end
