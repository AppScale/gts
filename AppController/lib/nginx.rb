#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'app_dashboard'
require 'datastore_server'
require 'monit_interface'
require 'user_app_client'


# A module to wrap all the interactions with the nginx web server
# Google App Engine applications can request that certain files should be
# hosted statically, so we use the nginx web server for this. It is the
# first server that a user hits, and forwards non-static file requests to
# haproxy, which then load balances requests to AppServers. This module
# configures and deploys nginx within AppScale.
module Nginx


  # The path on the local filesystem where the nginx binary can be found.
  NGINX_BIN = "/usr/sbin/nginx"


  NGINX_PATH = "/etc/nginx/"


  SITES_ENABLED_PATH = File.join(NGINX_PATH, "sites-enabled")


  CONFIG_EXTENSION = "conf"


  MAIN_CONFIG_FILE = File.join(NGINX_PATH, "nginx.#{CONFIG_EXTENSION}")


  # These ports are the one visible from outside, ie the ones that we
  # attach to running applications. Default is to have a maximum of 21
  # applications (8080-8100).
  START_PORT = 8080
  END_PORT = 8100


  # This is the start port of SSL connections to applications. Where an
  # app would have the set of ports (8080, 3700), (8081, 3701), and so on.
  SSL_PORT_OFFSET = 3700 


  BLOBSERVER_LISTEN_PORT = 6106


  BLOBSERVER_PORT = 6107


  CHANNELSERVER_PORT = 5280


  def self.start()
    # Nginx runs both a 'master process' and one or more 'worker process'es, so
    # when we have monit watch it, as long as one of those is running, nginx is
    # still running and shouldn't be restarted.
    start_cmd = '/usr/bin/service nginx start'
    stop_cmd = '/usr/bin/service nginx stop'
    match_cmd = "nginx: (.*) process"
    MonitInterface.start(:nginx, start_cmd, stop_cmd, ports=9999, env_vars=nil,
      remote_ip=nil, remote_key=nil, match_cmd=match_cmd)
  end

  def self.stop()
    MonitInterface.stop(:nginx)
  end

  # Kills nginx if there was a failure when trying to start/reload.
  #
  def self.cleanup_failed_nginx()
    Djinn.log_error("****Killing nginx because there was a FATAL error****")
    `ps aux | grep nginx | grep worker | awk {'print $2'} | xargs kill -9`
  end

  def self.reload()
    Djinn.log_info("Reloading nginx service.")
    HelperFunctions.shell('service nginx reload')
    if $?.to_i != 0
      cleanup_failed_nginx()
    end
  end

  def self.is_running?()
    output = MonitInterface.is_running?(:nginx)
    Djinn.log_debug("Checking if nginx is already monitored: #{output}")
    return output
  end

  # The port that nginx will be listen on for the given app number
  def self.app_listen_port(app_number)
    START_PORT + app_number
  end

  def self.get_ssl_port_for_app(http_port)
    http_port - SSL_PORT_OFFSET
  end

  # Return true if the configuration is good, false o.w.
  def self.check_config()
    HelperFunctions.shell("#{NGINX_BIN} -t -c #{MAIN_CONFIG_FILE}")
    return ($?.to_i == 0)
  end

  # Creates a Nginx config file for the provided app name on the load balancer
  def self.write_fullproxy_app_config(app_name, http_port, https_port,
    my_public_ip, my_private_ip, proxy_port, static_handlers, login_ip,
    language)

    Djinn.log_debug("Writing proxy for app #{app_name} with language #{language}")

    secure_handlers = HelperFunctions.get_secure_handlers(app_name)
    Djinn.log_debug("Secure handlers: " + secure_handlers.inspect.to_s)
    always_secure_locations = secure_handlers[:always].map { |handler|
      HelperFunctions.generate_secure_location_config(handler, https_port)
    }.join
    never_secure_locations = secure_handlers[:never].map { |handler|
      HelperFunctions.generate_secure_location_config(handler, http_port)
    }.join

    secure_static_handlers = []
    non_secure_static_handlers = []
    static_handlers.map { |handler|
      if handler["secure"] == "always"
        secure_static_handlers << handler
      elsif handler["secure"] == "never"
        non_secure_static_handlers << handler
      else
        secure_static_handlers << handler
        non_secure_static_handlers << handler
      end
    }

    secure_static_locations = secure_static_handlers.map { |handler|
      HelperFunctions.generate_location_config(handler)
    }.join
    non_secure_static_locations = non_secure_static_handlers.map { |handler|
      HelperFunctions.generate_location_config(handler)
    }.join

    # Java application needs a redirection for the blobstore.
    java_blobstore_redirection = ""
    if language == "java"
      java_blobstore_redirection = <<JAVA_BLOBSTORE_REDIRECTION
location ~ /_ah/upload/.* {
      proxy_pass http://gae_#{app_name}_blobstore;
      client_max_body_size 2G;
      proxy_connect_timeout 600;
      client_body_timeout 600;
      proxy_read_timeout 600;
    }
JAVA_BLOBSTORE_REDIRECTION
    end

    if never_secure_locations.include?('location / {')
      secure_default_location = ''
    else
      secure_default_location = <<DEFAULT_CONFIG
location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header  X-Forwarded-Proto $scheme;
      proxy_set_header  X-Forwarded-Ssl $ssl;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_ssl_#{app_name};
      client_max_body_size 2G;
      proxy_connect_timeout 600;
      client_body_timeout 600;
      proxy_read_timeout 600;
    }
DEFAULT_CONFIG
    end

    if always_secure_locations.include?('location / {')
      non_secure_default_location = ''
    else
      non_secure_default_location = <<DEFAULT_CONFIG
location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header  X-Forwarded-Proto $scheme;
      proxy_set_header  X-Forwarded-Ssl $ssl;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_#{app_name};
      client_max_body_size 2G;
      proxy_connect_timeout 600;
      client_body_timeout 600;
      proxy_read_timeout 600;
    }
DEFAULT_CONFIG
    end

    config = <<CONFIG
# Any requests that aren't static files get sent to haproxy
upstream gae_#{app_name} {
    server #{my_private_ip}:#{proxy_port};
}

upstream gae_ssl_#{app_name} {
    server #{my_private_ip}:#{proxy_port};
}

upstream gae_#{app_name}_blobstore {
    server #{my_private_ip}:#{BLOBSERVER_PORT};
}

map $scheme $ssl {
    default off;
    https on;
}

server {
    listen #{http_port};
    server_name #{my_public_ip}-#{app_name};
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;
    ignore_invalid_headers off;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    # If they come here using HTTPS, bounce them to the correct scheme.
    error_page 400 http://$host:$server_port$request_uri;

    #{always_secure_locations}
    #{non_secure_static_locations}
    #{non_secure_default_location}

    #{java_blobstore_redirection}

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 600;
      proxy_read_timeout 120;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }

}
server {
    listen #{BLOBSERVER_LISTEN_PORT};
    server_name #{my_public_ip}-#{app_name}-blobstore;
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}-blobstore.access.log upstream;
    error_log  /var/log/nginx/#{app_name}-blobstore.error.log;
    access_log off;
    #error_log /dev/null crit;
    ignore_invalid_headers off;

    # If they come here using HTTPS, bounce them to the correct scheme.
    error_page 400 http://$host:$server_port$request_uri;

    rewrite_log off;
    error_page 404 = /404.html;

    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_#{app_name}_blobstore;
      client_max_body_size 2G;
      proxy_connect_timeout 600;
      client_body_timeout 600;
      proxy_read_timeout 600;
    }
}    

server {
    listen #{https_port};
    server_name #{my_public_ip}-#{app_name}-ssl;
    ssl on;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;  # don't use SSLv3 ref: POODLE
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;

    # If they come here using HTTP, bounce them to the correct scheme.
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;

    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;
    ignore_invalid_headers off;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    #{never_secure_locations}
    #{secure_static_locations}
    #{secure_default_location}

    #{java_blobstore_redirection}

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 600;
      proxy_read_timeout 120;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }


}
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    return reload_nginx(config_path, app_name)
  end

  # This function checks if Nginx has already configured the specified
  # application.
  #
  # Args:
  #  app_name: The application to check for.
  #
  # Returns:
  #  bool: true/false depending if the application is already configured.
  def self.is_app_already_configured(app_name)
    if app_name != nil
      return File.exists?(File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}"))
    end

    return false
  end

  def self.reload_nginx(config_path, app_name)
    if Nginx.check_config()
      Nginx.reload()
      return true
    else
      Djinn.log_error("Unable to load Nginx config for #{app_name}")
      FileUtils.rm_f(config_path)
      return false
    end
  end 

  def self.remove_app(app_name)
    config_name = "#{app_name}.#{CONFIG_EXTENSION}"
    FileUtils.rm_f(File.join(SITES_ENABLED_PATH, config_name))
    Nginx.reload()
  end

  # Removes all the enabled sites
  def self.clear_sites_enabled()
    if File.directory?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)
      # Remove any files that are not configs
      sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
      full_path_sites = sites.map { |site| File.join(SITES_ENABLED_PATH, site) }
      FileUtils.rm_f full_path_sites
      Nginx.reload()
    end
  end

  # Create the configuration file for the datastore_server
  def self.create_datastore_server_config(all_private_ips, proxy_port)
    config = <<CONFIG
upstream #{DatastoreServer::NAME} {
CONFIG
    all_private_ips.each { |ip|
      config += <<CONFIG 
    server #{ip}:#{proxy_port};
CONFIG
    }
    config += <<CONFIG
}
    
server {
    listen #{DatastoreServer::LISTEN_PORT_NO_SSL};
    root /root/appscale/AppDB/;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/datastore_server.access.log upstream;
    #error_log  /var/log/nginx/datastore_server.error.log;
    access_log off;
    error_log /dev/null crit;
    ignore_invalid_headers off;

    rewrite_log off;
    error_page 404 = /404.html;



    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_next_upstream     error timeout invalid_header http_500;
      proxy_pass http://#{DatastoreServer::NAME};
      client_max_body_size 30M;
      proxy_connect_timeout 5;
      client_body_timeout 600;
      proxy_read_timeout 600;
    }

}

server {
    listen #{DatastoreServer::LISTEN_PORT_WITH_SSL};
    ssl on;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;  # don't use SSLv3 ref: POODLE
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;

    # If they come here using HTTP, bounce them to the correct scheme.
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;

    root /root/appscale/AppDB/public;
    #access_log  /var/log/nginx/datastore_server_encrypt.access.log upstream;
    #error_log  /var/log/nginx/datastore_server_encrypt.error.log;
    access_log off;
    error_log  /dev/null crit;
    ignore_invalid_headers off;

    rewrite_log off;
    error_page 502 /502.html;

    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;

      client_body_timeout 600;
      proxy_read_timeout 600;
      proxy_next_upstream     error timeout invalid_header http_500;
      proxy_connect_timeout 5;
      #Increase file size so larger applications can be uploaded
      client_max_body_size 30M;
      # go to proxy
      proxy_pass http://#{DatastoreServer::NAME};
    }
}
CONFIG
    config_path = File.join(SITES_ENABLED_PATH, "#{DatastoreServer::NAME}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end

  # Creates an Nginx configuration file for the Users/Apps soap server.
  # 
  # Args:
  #   all_private_ips: A list of strings, the IPs on which the datastore is running. 
  def self.create_uaserver_config()
    config = <<CONFIG
upstream uaserver {
CONFIG
      config += <<CONFIG
    server 127.0.0.1:#{UserAppClient::HAPROXY_SERVER_PORT};
CONFIG
    config += <<CONFIG
}
 
server {
    listen #{SSL_SERVER_PORT};
    ssl on;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;  # don't use SSLv3 ref: POODLE
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;

    # If they come here using HTTP, bounce them to the correct scheme.
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;

    root /root/appscale/AppDB/public;
    #access_log  /var/log/nginx/datastore_server_encrypt.access.log upstream;
    #error_log  /var/log/nginx/datastore_server_encrypt.error.log;
    access_log off;
    error_log  /dev/null crit;
    ignore_invalid_headers off;

    rewrite_log off;
    error_page 502 /502.html;

    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;

      client_body_timeout 600;
      proxy_read_timeout 600;
      proxy_next_upstream     error timeout invalid_header http_500;
      proxy_connect_timeout 5;
      #Increase file size so larger applications can be uploaded
      client_max_body_size 30M;
      # go to proxy
      proxy_pass http://uaserver;
    }
}
CONFIG
    config_path = File.join(SITES_ENABLED_PATH, "as_uaserver.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end

  # Set up the folder structure and creates the configuration files necessary for nginx
  def self.initialize_config
    config = <<CONFIG
user www-data;
worker_processes  1;

error_log  /var/log/nginx/error.log;
pid        /run/nginx.pid;

events {
    worker_connections  30000;
}

http {
    include       #{NGINX_PATH}/mime.types;
    default_type  application/octet-stream;

    access_log  /var/log/nginx/access.log;

    log_format upstream '$remote_addr - - [$time_local] "$request" status $status '
                        'upstream $upstream_response_time request $request_time '
                        '[for $host via $upstream_addr]';

    sendfile        on;
    #tcp_nopush     on;

    #keepalive_timeout  0;
    keepalive_timeout  600;
    tcp_nodelay        on;
    server_names_hash_bucket_size 128;
    types_hash_max_size 2048;
    gzip  on;

    include #{NGINX_PATH}/sites-enabled/*;
}
CONFIG

    HelperFunctions.shell("mkdir -p /var/log/nginx/")
    # Create the sites enabled folder
    unless File.exists? SITES_ENABLED_PATH
      FileUtils.mkdir_p SITES_ENABLED_PATH
    end

    # copy over certs for ssl
    # just copy files once to keep certificate as static.
    if !File.exists?("#{NGINX_PATH}/mykey.pem")
      HelperFunctions.shell("cp /etc/appscale/certs/mykey.pem #{NGINX_PATH}")
    end
    if !File.exists?("#{NGINX_PATH}/mycert.pem")
      HelperFunctions.shell("cp /etc/appscale/certs/mycert.pem #{NGINX_PATH}")
    end
    # Write the main configuration file which sets default configuration parameters
    File.open(MAIN_CONFIG_FILE, "w+") { |dest_file| dest_file.write(config) }

    # The pid file location was changed in the default nginx config for
    # Trusty. Because of this, the first reload after writing the new config
    # will fail on Precise.
    HelperFunctions.shell('service nginx restart')
  end
end
