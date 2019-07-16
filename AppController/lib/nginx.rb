#!/usr/bin/ruby -w

require 'erb'
require 'fileutils'

$:.unshift File.join(File.dirname(__FILE__))
require 'app_dashboard'
require 'blobstore'
require 'custom_exceptions'
require 'datastore_server'
require 'helperfunctions'
require 'monit_interface'
require 'user_app_client'

# A module to wrap all the interactions with the nginx web server
# Google App Engine applications can request that certain files should be
# hosted statically, so we use the nginx web server for this. It is the
# first server that a user hits, and forwards non-static file requests to
# haproxy, which then load balances requests to AppServers. This module
# configures and deploys nginx within AppScale.
module Nginx
  CHANNELSERVER_PORT = 5280

  CONFIG_EXTENSION = 'conf'.freeze

  # The path on the local filesystem where the nginx binary can be found.
  NGINX_BIN = '/usr/sbin/nginx'.freeze

  # Nginx AppScale log directory.
  NGINX_LOG_PATH = '/var/log/nginx'.freeze

  # Nginx top configuration directory.
  NGINX_PATH = '/etc/nginx'.freeze

  MAIN_CONFIG_FILE = File.join(NGINX_PATH, "nginx.#{CONFIG_EXTENSION}")

  # Nginx sites-enabled path.
  SITES_ENABLED_PATH = File.join(NGINX_PATH, 'sites-enabled')

  # Application capture regex.
  VERSION_KEY_REGEX = /appscale-(.*_.*_.*).conf/

  # These ports are the one visible from outside, ie the ones that we
  # attach to running applications. Default is to have a maximum of 21
  # applications (8080-8100).
  START_PORT = 8080
  END_PORT = 8100

  # This is the start port of SSL connections to applications. Where an
  # app would have the set of ports (8080, 3700), (8081, 3701), and so on.
  SSL_PORT_OFFSET = 3700

  def self.start
    # Nginx runs both a 'master process' and one or more 'worker process'es, so
    # when we have monit watch it, as long as one of those is running, nginx is
    # still running and shouldn't be restarted.
    service_bin = `which service`.chomp
    start_cmd = "#{service_bin} nginx start"
    stop_cmd = "#{service_bin} nginx stop"
    pidfile = '/var/run/nginx.pid'
    MonitInterface.start_daemon(:nginx, start_cmd, stop_cmd, pidfile)
  end

  def self.stop
    MonitInterface.stop(:nginx, false)
  end

  # Kills nginx if there was a failure when trying to start/reload.
  #
  def self.cleanup_failed_nginx
    Djinn.log_error('****Killing nginx because there was a FATAL error****')
    `ps aux | grep nginx | grep worker | awk {'print $2'} | xargs kill -9`
  end

  def self.reload
    Djinn.log_info('Reloading nginx service.')
    HelperFunctions.shell('service nginx reload')
    cleanup_failed_nginx if $?.to_i != 0
  end

  def self.is_running?
    output = MonitInterface.is_running?(:nginx)
    Djinn.log_debug("Checking if nginx is already monitored: #{output}")
    output
  end

  # The port that nginx will be listen on for the given app number
  def self.app_listen_port(app_number)
    START_PORT + app_number
  end

  def self.get_ssl_port_for_app(http_port)
    http_port - SSL_PORT_OFFSET
  end

  # Return true if the configuration is good, false o.w.
  def self.check_config
    HelperFunctions.shell("#{NGINX_BIN} -t -c #{MAIN_CONFIG_FILE}")
    ($?.to_i == 0)
  end

  # Creates a Nginx config file for the provided version on the load balancer.
  # Returns:
  #   boolean: indicates if the nginx configuration has been written.
  def self.write_fullproxy_version_config(version_key, http_port, https_port,
    server_name, my_private_ip, proxy_port, static_handlers, load_balancer_ip,
    language)

    # Get project id (needed to look for certificates).
    project_id, service_id, _ = version_key.split(Djinn::VERSION_PATH_SEPARATOR)

    parsing_log = "Writing proxy for #{version_key} with language " \
      "#{language}.\n"



    config_path = File.join(SITES_ENABLED_PATH,
                            "appscale-#{version_key}.#{CONFIG_EXTENSION}")
    blobstore_port = BlobServer::HAPROXY_PORT
    dispatch = []
    if service_id == Djinn::DEFAULT_SERVICE
      begin
        zk_dispatch = ZKInterface.get_dispatch_rules(project_id)
        dispatch = zk_dispatch if zk_dispatch
      rescue ConfigNotFound
        Djinn.log_debug("No dispatch rules found for #{project_id}")
      end
    end

    template = File.read('/root/appscale/AppController/lib/application_nginx.erb')
    config =  ERB.new(template).result( binding )

    # Let's reload and overwrite only if something changed, or new
    # certificates have been installed.
    current = File.exists?(config_path) ? File.read(config_path) : ''

    # Make sure we have the proper certificates in place and re-write
    # nginx config if needed.
    if ensure_certs_are_in_place(project_id) || current != config
      Djinn.log_debug(parsing_log)
      File.open(config_path, 'w+') { |dest_file| dest_file.write(config) }
      reload_nginx(config_path, version_key)
      return true
    end

    Djinn.log_debug('No need to restart nginx: configuration didn\'t change.')
    false
  end

  def self.reload_nginx(config_path, version_key)
    if Nginx.check_config
      Nginx.reload
      return true
    end

    Djinn.log_error("Unable to load Nginx config for #{version_key}")
    FileUtils.rm_f(config_path)
    false
  end

  def self.remove_version(version_key)
    config_name = "appscale-#{version_key}.#{CONFIG_EXTENSION}"
    FileUtils.rm_f(File.join(SITES_ENABLED_PATH, config_name))
    Nginx.reload
  end

  def self.list_sites_enabled
    dir_app_regex = "appscale-*_*_*.#{CONFIG_EXTENSION}"
    return Dir.glob(File.join(SITES_ENABLED_PATH, dir_app_regex))
  end

  # Removes all the enabled sites
  def self.clear_sites_enabled
    if File.directory?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)

      # Only remove AppScale-related config files.
      to_remove = []
      sites.each { |site|
        if site.end_with?(CONFIG_EXTENSION) && site.start_with?('appscale-')
          to_remove.push(site)
        end
      }

      full_path_sites = to_remove.map { |site|
        File.join(SITES_ENABLED_PATH, site)
      }
      FileUtils.rm_f full_path_sites
      Nginx.reload
    end
  end

  # Creates an Nginx configuration file for a service or just adds
  # new location block
  #
  # Args:
  #   service_name: A string specifying the service name.
  #   service_host: A string specifying the location of the service.
  #   service_port: An integer specifying the service port.
  #   nginx_port: An integer specifying the port for Nginx to listen on.
  #   location: A string specifying an Nginx location match.
  def self.add_service_location(service_name, service_host, service_port,
                                nginx_port, location = '/')
    proxy_pass = "#{service_host}:#{service_port}"
    config_path = File.join(SITES_ENABLED_PATH,
                            "#{service_name}.#{CONFIG_EXTENSION}")
    old_config = File.read(config_path) if File.file?(config_path)

    locations = {}

    if old_config
      # Check if there is no port conflict
      old_nginx_port = old_config.match(/listen (\d+)/m)[1]
      if old_nginx_port != nginx_port.to_s
        msg = "Can't update nginx configs for #{service_name} "\
              "(old nginx port: #{old_nginx_port}, new: #{nginx_port})"
        Djinn.log_error(msg)
        raise AppScaleException.new(msg)
      end

      # Find all specified locations and update it
      regex = /location ([\/\w]+) \{.+?proxy_pass +http?\:\/\/([\d.]+\:\d+)/m
      locations = Hash[old_config.scan(regex)]
    end

    # Ensure new location is associated with a right proxy_pass
    locations[location] = proxy_pass

    config = <<CONFIG
server {
    listen #{nginx_port};

    ssl on;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;  # don't use SSLv3 ref: POODLE
    ssl_certificate     #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;

    #access_log #{NGINX_LOG_PATH}/#{service_name}.access.log upstream;
    #error_log  #{NGINX_LOG_PATH}/#{service_name}.error.log;
    access_log  off;
    error_log   /dev/null crit;

    ignore_invalid_headers off;
    rewrite_log off;

    # If they come here using HTTP, bounce them to the correct scheme.
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;

    error_page 502 /502.html;

    # Locations:
CONFIG

    locations.each do |location_key, proxy_pass_value|
      location_conf = <<LOCATION
    location #{location_key} {
      proxy_pass            http://#{proxy_pass_value};
      proxy_read_timeout    600;
      client_max_body_size  2G;
    }

LOCATION
      config << location_conf
    end
    config << '}'

    File.write(config_path, config)
    Nginx.reload
  end

  def self.ensure_certs_are_in_place(project_id=nil)
    # If the project is nil, we'll set up the self-signed certs for the
    # internal communication.
    target_certs = ["#{NGINX_PATH}/mycert.pem", "#{NGINX_PATH}/mykey.pem"]
    src_certs = ["#{Djinn::APPSCALE_CONFIG_DIR}/certs/mycert.pem",
                 "#{Djinn::APPSCALE_CONFIG_DIR}/certs/mykey.pem"]
    certs_modified = false

    # Validate and use the project specified certs for the project.
    if !project_id.nil?
      target_certs = ["#{NGINX_PATH}/#{project_id}.pem",
                      "#{NGINX_PATH}/#{project_id}.key"]
      new_src_certs = ["#{Djinn::APPSCALE_CONFIG_DIR}/certs/#{project_id}.pem",
                       "#{Djinn::APPSCALE_CONFIG_DIR}/certs/#{project_id}.key"]
      if File.exist?(new_src_certs[0]) && File.exist?(new_src_certs[1])
        if system("openssl x509 -in #{new_src_certs[0]} -noout") &&
            system("openssl rsa -in #{new_src_certs[1]} -noout")
          src_certs = new_src_certs
        else
          Djinn.log_warn("Not using invalid certificate for #{project_id}.")
        end
      end
    end

    target_certs.each_with_index { |cert, index|
      next if File.exist?(cert) && FileUtils.cmp(cert, src_certs[index])

      FileUtils.cp(src_certs[index], cert)
      File.chmod(0400, cert)
      Djinn.log_info("Installed certificate/key in #{cert}.")
      certs_modified = true
    }
    return certs_modified
  end

  # Set up the folder structure and creates the configuration files
  # necessary for nginx.
  def self.initialize_config
    config = <<CONFIG
user www-data;
worker_processes 1;

error_log /var/log/nginx/error.log;
pid       /run/nginx.pid;

events {
    worker_connections 30000;
}

http {
    include       #{NGINX_PATH}/mime.types;
    default_type  application/octet-stream;
    access_log    /var/log/nginx/access.log;

    log_format upstream '$remote_addr - - [$time_local] "$request" status $status '
                        'upstream $upstream_response_time request $request_time '
                        '[for $host via $upstream_addr]';

    sendfile    on;
    #tcp_nopush on;

    keepalive_timeout  600;
    tcp_nodelay        on;
    server_names_hash_bucket_size 128;
    types_hash_max_size           2048;
    gzip on;

    include #{NGINX_PATH}/sites-enabled/*;
}
CONFIG

    HelperFunctions.shell('mkdir -p /var/log/nginx/')
    # Create the sites enabled folder
    FileUtils.mkdir_p SITES_ENABLED_PATH unless File.exists? SITES_ENABLED_PATH

    # Copy the internal certificate (default for internal communication).
    ensure_certs_are_in_place

    # Write the main configuration file which sets default configuration
    # parameters
    File.open(MAIN_CONFIG_FILE, 'w+') { |dest_file| dest_file.write(config) }

    # The pid file location was changed in the default nginx config for
    # Trusty. Because of this, the first reload after writing the new config
    # will fail on Precise.
    HelperFunctions.shell('service nginx restart')
  end
end

