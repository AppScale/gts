#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'app_dashboard'
require 'datastore_server'
require 'monit_interface'


# A module to wrap all the interactions with the nginx web server
# Google App Engine applications can request that certain files should be
# hosted statically, so we use the nginx web server for this. It is the
# first server that a user hits, and forwards non-static file requests to
# haproxy, which then load balances requests to AppServers. This module
# configures and deploys nginx within AppScale.
module Nginx


  # The path on the local filesystem where the nginx binary can be found.
  NGINX_BIN = "/usr/local/nginx/sbin/nginx"


  NGINX_PATH = "/usr/local/nginx/conf"


  SITES_ENABLED_PATH = File.join(NGINX_PATH, "sites-enabled")


  CONFIG_EXTENSION = "conf"


  MAIN_CONFIG_FILE = File.join(NGINX_PATH, "nginx.#{CONFIG_EXTENSION}")


  START_PORT = 8080


  # This is the start port of SSL connections to applications. Where an
  # app would have the set of ports (8080, 3700), (8081, 3701), and so on.
  SSL_PORT_OFFSET = 3700 


  BLOBSERVER_LISTEN_PORT = 6106


  BLOBSERVER_PORT = 6107


  CHANNELSERVER_PORT = 5280


  def self.start
    # Nginx runs both a 'master process' and one or more 'worker process'es, so
    # when we have monit watch it, as long as one of those is running, nginx is
    # still running and shouldn't be restarted.
    start_cmd = "#{NGINX_BIN} -c #{MAIN_CONFIG_FILE}"
    stop_cmd = "#{NGINX_BIN} -s stop"
    match_cmd = "nginx: (.*) process"
    MonitInterface.start(:nginx, start_cmd, stop_cmd, ports=9999, env_vars=nil,
      remote_ip=nil, remote_key=nil, match_cmd=match_cmd)
  end

  def self.stop
    MonitInterface.stop(:nginx)
  end

  def self.restart
    MonitInterface.restart(:nginx)
  end

  # Reload nginx if it is already running. If nginx is not running, start it.
  def self.reload
    if Nginx.is_running?
      HelperFunctions.shell("#{NGINX_BIN} -s reload")
    else
      Nginx.start 
    end
  end

  def self.is_running?
    processes = `ps ax | grep nginx | grep -v grep | wc -l`.chomp
    if processes == "0"
      return false
    else
      return true
    end
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
    return ($?.to_i == 0)
  end

  # Creates a Nginx config file for the provided app name
  def self.write_app_config(app_name, http_port, https_port, my_public_ip,
    my_private_ip, proxy_port, static_handlers, login_ip)
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

    default_location = <<DEFAULT_CONFIG
    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_#{app_name};
      client_max_body_size 2G;
      proxy_connect_timeout 60;
      client_body_timeout 60;
      proxy_read_timeout 60;
    }
DEFAULT_CONFIG
    secure_default_location = default_location
    non_secure_default_location = default_location
    if never_secure_locations.include?('location / {')
      secure_default_location = ''
    end
    if always_secure_locations.include?('location / {')
      non_secure_default_location = ''
    end

    config = <<CONFIG
# Any requests that aren't static files get sent to haproxy
upstream gae_#{app_name} {
    server #{my_private_ip}:#{proxy_port};
}

server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{http_port};
    server_name #{my_public_ip};
    root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    #If they come here using HTTPS, bounce them to the correct scheme
    error_page 400 http://$host:$server_port$request_uri;

    #{always_secure_locations}
    #{non_secure_static_locations}

    #{non_secure_default_location}

    location /404.html {
      root /var/apps/#{app_name};
    }

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 55;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }

}
server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
        chunkin_resume;
    }
    listen #{https_port};
    server_name #{my_public_ip}-#{app_name}-ssl;
    ssl on;
    ssl_certificate /usr/local/nginx/conf/mycert.pem;
    ssl_certificate_key /usr/local/nginx/conf/mykey.pem;

    #If they come here using HTTP, bounce them to the correct scheme
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;
 
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    #{never_secure_locations}
    #{secure_static_locations}

    #{secure_default_location}

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 55;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }


}
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    return reload_nginx(config_path, app_name)
  end

  # Creates a Nginx config file for the provided app name on the load balancer
  def self.write_fullproxy_app_config(app_name, http_port, https_port,
    my_public_ip, my_private_ip, proxy_port, static_handlers, login_ip)

    Djinn.log_debug("Writing full proxy app config for app #{app_name}")

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

    if never_secure_locations.include?('location / {')
      secure_default_location = ''
    else
      secure_default_location = <<DEFAULT_CONFIG
    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_ssl_#{app_name};
      client_max_body_size 2G;
      proxy_connect_timeout 60;
      client_body_timeout 60;
      proxy_read_timeout 60;
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
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://gae_#{app_name};
      client_max_body_size 2G;
      proxy_connect_timeout 60;
      client_body_timeout 60;
      proxy_read_timeout 60;
    }
DEFAULT_CONFIG
    end

    config = <<CONFIG
# Any requests that aren't static files get sent to haproxy
upstream gae_#{app_name} {
    #{my_private_ip}:#{proxy_port}
}

upstream gae_ssl_#{app_name} {
    #{my_private_ip}:#{proxy_port}
}

upstream gae_#{app_name}_blobstore {
    #{my_private_ip}:#{BLOBSERVER_PORT}
}

server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{http_port};
    server_name #{my_public_ip}-#{app_name};
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    #If they come here using HTTPS, bounce them to the correct scheme
    error_page 400 http://$host:$server_port$request_uri;

    #{always_secure_locations}
    #{non_secure_static_locations}
    #{non_secure_default_location}

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 55;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }

}
server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{BLOBSERVER_LISTEN_PORT};
    server_name #{my_public_ip}-#{app_name}-blobstore;
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}-blobstore.access.log upstream;
    error_log  /var/log/nginx/#{app_name}-blobstore.error.log;
    access_log off;
    #error_log /dev/null crit;

    #If they come here using HTTPS, bounce them to the correct scheme
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
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{https_port};
    server_name #{my_public_ip}-#{app_name}-ssl;
    ssl on;
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;

    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

    #{never_secure_locations}
    #{secure_static_locations}
    #{secure_default_location}

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 55;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }


}
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    return reload_nginx(config_path, app_name)
  end

  def self.reload_nginx(config_path, app_name)
    if Nginx.check_config
      Nginx.reload
      return true
    else
      Djinn.log_error("Unable to load Nginx config for #{app_name}")
      FileUtils.rm(config_path)
      return false
    end
  end 

  def self.remove_app(app_name)
    config_name = "#{app_name}.#{CONFIG_EXTENSION}"
    FileUtils.rm(File.join(SITES_ENABLED_PATH, config_name))
    Nginx.reload
  end

  # Removes all the enabled sites
  def self.clear_sites_enabled
    if File.exists?(SITES_ENABLED_PATH)
      sites = Dir.entries(SITES_ENABLED_PATH)
      # Remove any files that are not configs
      sites.delete_if { |site| !site.end_with?(CONFIG_EXTENSION) }
      full_path_sites = sites.map { |site| File.join(SITES_ENABLED_PATH, site) }
      FileUtils.rm_f full_path_sites

      Nginx.reload
    end
  end

  # Create the configuration file for the AppDashboard application
  def self.create_app_load_balancer_config(my_public_ip, my_private_ip, 
    proxy_port)
    self.create_app_config(my_public_ip, my_private_ip, proxy_port, 
      AppDashboard::LISTEN_PORT, AppDashboard::APP_NAME,
      AppDashboard::PUBLIC_DIRECTORY, AppDashboard::LISTEN_SSL_PORT)
  end

  # Create the configuration file for the datastore_server
  def self.create_datastore_server_config(my_ip, proxy_port)
    config = <<CONFIG
upstream #{DatastoreServer::NAME} {
    server #{my_ip}:#{proxy_port};
}
    
server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{DatastoreServer::LISTEN_PORT_NO_SSL};
    server_name #{my_ip};
    root /root/appscale/AppDB/;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/datastore_server.access.log upstream;
    #error_log  /var/log/nginx/datastore_server.error.log;
    access_log off;
    error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;



    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://#{DatastoreServer::NAME};
      client_max_body_size 30M;
      proxy_connect_timeout 60;
      client_body_timeout 60;
      proxy_read_timeout 60;
    }

}

server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{DatastoreServer::LISTEN_PORT_WITH_SSL};
    ssl on;
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;
    root /root/appscale/AppDB/public;
    #access_log  /var/log/nginx/datastore_server_encrypt.access.log upstream;
    #error_log  /var/log/nginx/datastore_server_encrypt.error.log;
    access_log off;
    error_log  /dev/null crit;

    rewrite_log off;
    error_page 502 /502.html;

    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;

      client_body_timeout 60;
      proxy_read_timeout 60;
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


  # A generic function for creating nginx config files used by appscale services
  def self.create_app_config(my_public_ip, my_private_ip, proxy_port, 
    listen_port, name, public_dir, ssl_port=nil)

    config = <<CONFIG
upstream #{name} {
   server #{my_private_ip}:#{proxy_port};
}
CONFIG

    if ssl_port
      # redirect all request to ssl port.
      config += <<CONFIG
server {
  chunkin on;
 
    #If they come here using HTTPS, bounce them to the correct scheme
    error_page 400 http://$host:$server_port$request_uri;

  error_page 411 = @my_411_error;
  location @my_411_error {
      chunkin_resume;
  }

    listen #{listen_port};
    rewrite ^(.*) https://#{my_public_ip}:#{ssl_port}$1 permanent;
}

server {
    chunkin on;
 
    #If they come here using HTTP, bounce them to the correct scheme
    error_page 400 https://$host:$server_port$request_uri;
    error_page 497 https://$host:$server_port$request_uri;

    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{ssl_port};
    ssl on;
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;
CONFIG
    else
      config += <<CONFIG
server {
    chunkin on;
 
    error_page 411 = @my_411_error;
    location @my_411_error {
      chunkin_resume;
    }
    listen #{listen_port};
CONFIG
    end

    config += <<CONFIG
    root #{public_dir};
    access_log  /var/log/nginx/load-balancer.access.log upstream;
    error_log  /var/log/nginx/load-balancer.error.log;
    rewrite_log off;
    error_page 502 /502.html;

    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header  REMOTE_ADDR  $remote_addr;
      proxy_set_header  HTTP_X_FORWARDED_FOR $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;

      client_body_timeout 360;
      proxy_read_timeout 360;
CONFIG
    if name == AppDashboard::APP_NAME
      config += <<CONFIG
 
      # Increase file size for alb so larger applications can be uploaded
      client_max_body_size 1G;
CONFIG
    else
      config += <<CONFIG
      client_max_body_size 30M;
CONFIG
    end
    config += <<CONFIG
      # go to proxy
      if (!-f $request_filename) {
        proxy_pass http://#{name};
        break;
      }
    }

    location /502.html {
      root #{APPSCALE_HOME}/AppDashboard/static;
    }
}
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    HAProxy.regenerate_config
  end


  # Set up the folder structure and creates the configuration files necessary for nginx
  def self.initialize_config
    config = <<CONFIG
user www-data;
worker_processes  1;

error_log  /var/log/nginx/error.log;
pid        /var/run/nginx.pid;

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
    keepalive_timeout  60;
    tcp_nodelay        on;
    server_names_hash_bucket_size 128;

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
    HelperFunctions.shell("cp /etc/appscale/certs/mykey.pem #{NGINX_PATH}")
    HelperFunctions.shell("cp /etc/appscale/certs/mycert.pem #{NGINX_PATH}")
    # Write the main configuration file which sets default configuration parameters
    File.open(MAIN_CONFIG_FILE, "w+") { |dest_file| dest_file.write(config) }
  end
end
