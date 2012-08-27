#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'load_balancer'
require 'monitoring'
require 'pbserver'


# A module to wrap all the interactions with the nginx web server
# Google App Engine applications can request that certain files should be
# hosted statically, so we use the nginx web server for this. It is the
# first server that a user hits, and forwards non-static file requests to
# haproxy, which then load balances requests to AppServers. This module
# configures and deploys nginx within AppScale.
module Nginx


  NGINX_PATH = File.join("/", "etc", "nginx")


  SITES_ENABLED_PATH = File.join(NGINX_PATH, "sites-enabled")


  CONFIG_EXTENSION = "conf"


  MAIN_CONFIG_FILE = File.join(NGINX_PATH, "nginx.#{CONFIG_EXTENSION}")


  START_PORT = 8080

  # This is the start port of SSL connections to applications. Where an
  # app would have the set of ports (8080, 3700), (8081, 3701), and so on.
  SSL_PORT_OFFSET = 3700 

  BLOBSERVER_PORT = 6106

  CHANNELSERVER_PORT = 5280

  def self.start
    `/etc/init.d/nginx start`
  end

  def self.stop
    `/etc/init.d/nginx stop`
  end

  def self.restart
    self.stop
    self.start
  end

  def self.reload
    self.restart
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

  # Return true if the configuration is good, false o.w.
  def self.check_config
    HelperFunctions.shell("nginx -t -c #{MAIN_CONFIG_FILE}")
    return ($?.to_i == 0)
  end

  # Creates a Nginx config file for the provided app name
  def self.write_app_config(app_name, app_number, my_public_ip, proxy_port, static_handlers, login_ip)
    static_locations = static_handlers.map { |handler| HelperFunctions.generate_location_config(handler) }.join
    listen_port = Nginx.app_listen_port(app_number)
    config = <<CONFIG
# Any requests that arent static files get sent to haproxy
upstream gae_#{app_name} {
    server #{my_public_ip}:#{proxy_port};
}

server {
    listen #{listen_port};
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

    #{static_locations}

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
CONFIG

    config_path = File.join(SITES_ENABLED_PATH, "#{app_name}.#{CONFIG_EXTENSION}")
    File.open(config_path, "w+") { |dest_file| dest_file.write(config) }

    return reload_nginx(config_path, app_name)
  end

  # Creates a Nginx config file for the provided app name on the load balancer
  def self.write_fullproxy_app_config(app_name, app_number, my_public_ip, 
    my_private_ip, proxy_port, login_ip, appengine_server_ips)
    listen_port = Nginx.app_listen_port(app_number)
    ssl_listen_port = listen_port - SSL_PORT_OFFSET
    blob_servers = []
    servers = []
    appengine_server_ips.each do |ip|
      servers << "server #{ip}:#{listen_port};"
    end
    appengine_server_ips.each do |ip|
      blob_servers << "server #{ip}:#{BLOBSERVER_PORT};"
    end
    servers = servers.join("\n")
    config = <<CONFIG
# Any requests that arent static files get sent to haproxy
upstream gae_#{app_name} {
    #{servers}
}
upstream gae_#{app_name}_blobstore {
    #{blob_servers}
}
server {
    listen #{listen_port};
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

    location /reserved-channel-appscale-path {
      proxy_buffering off;
      tcp_nodelay on;
      keepalive_timeout 55;
      proxy_pass http://#{login_ip}:#{CHANNELSERVER_PORT}/http-bind;
    }

}
server {
    listen #{BLOBSERVER_PORT};
    server_name #{my_public_ip}-#{app_name}-blobstore;
    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}-blobstore.access.log upstream;
    error_log  /var/log/nginx/#{app_name}-blobstore.error.log;
    access_log off;
    #error_log /dev/null crit;

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
    listen #{ssl_listen_port};
    server_name #{my_public_ip}-#{app_name}-ssl;
    ssl on;
    ssl_certificate /etc/nginx/mycert.pem;
    ssl_certificate_key /etc/nginx/mykey.pem;

    #root /var/apps/#{app_name}/app;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/#{app_name}.access.log upstream;
    error_log  /var/log/nginx/#{app_name}.error.log;
    access_log off;
    #error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;
    set $cache_dir /var/apps/#{app_name}/cache;

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
      Djinn.log_debug("Unable to load Nginx config for #{app_name}") 
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

  # Create the configuration file for the AppLoadBalancer Rails application
  def self.create_app_load_balancer_config(my_public_ip, my_private_ip, 
    proxy_port)
    self.create_app_config(my_public_ip, my_private_ip, proxy_port, 
      LoadBalancer.listen_port, LoadBalancer.name, 
      LoadBalancer.public_directory, LoadBalancer.listen_ssl_port)
  end

  # Create the configuration file for the AppMonitoring Rails application
  def self.create_app_monitoring_config(my_public_ip, my_private_ip, proxy_port)
    self.create_app_config(my_public_ip, my_private_ip, proxy_port, 
      Monitoring.listen_port, Monitoring.name, Monitoring.public_directory)
  end

  # Create the configuration file for the pbserver
  def self.create_pbserver_config(my_ip, proxy_port)
    config = <<CONFIG
upstream #{PbServer::NAME} {
    server #{my_ip}:#{proxy_port};
}
    
server {
    listen #{PbServer::LISTEN_PORT_NO_SSL};
    server_name #{my_ip};
    root /root/appscale/AppDB/;
    # Uncomment these lines to enable logging, and comment out the following two
    #access_log  /var/log/nginx/pbserver.access.log upstream;
    #error_log  /var/log/nginx/pbserver.error.log;
    access_log off;
    error_log /dev/null crit;

    rewrite_log off;
    error_page 404 = /404.html;



    location / {
      proxy_set_header  X-Real-IP  $remote_addr;
      proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Host $http_host;
      proxy_redirect off;
      proxy_pass http://#{PbServer::NAME};
      client_max_body_size 30M;
      proxy_connect_timeout 60;
      client_body_timeout 60;
      proxy_read_timeout 60;
    }

}

server {
    listen #{PbServer::LISTEN_PORT_WITH_SSL};
    ssl on;
    ssl_certificate /etc/nginx/mycert.pem;
    ssl_certificate_key /etc/nginx/mykey.pem;
    root /root/appscale/AppDB/public;
    #access_log  /var/log/nginx/pbencrypt.access.log upstream;
    #error_log  /var/log/nginx/pbencrypt.error.log;
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
      proxy_pass http://#{PbServer::NAME};
    }
}
CONFIG
    config_path = File.join(SITES_ENABLED_PATH, "#{PbServer::NAME}.#{CONFIG_EXTENSION}")
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
    listen #{listen_port};
    rewrite ^(.*) https://#{my_public_ip}:#{ssl_port}$1 permanent;
}

server {
    listen #{ssl_port};
    ssl on;
    ssl_certificate #{NGINX_PATH}/mycert.pem;
    ssl_certificate_key #{NGINX_PATH}/mykey.pem;
CONFIG
    else
      config += <<CONFIG
server {
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

      #Increase file size so larger applications can be uploaded
      client_max_body_size 30M;


      # go to proxy
      if (!-f $request_filename) {
        proxy_pass http://#{name};
        break;
      }
    }

    location /502.html {
      root #{APPSCALE_HOME}/AppLoadBalancer/public;
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
    include       /etc/nginx/mime.types;
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

    `mkdir -p /var/log/nginx/`
    # Create the sites enabled folder
    unless File.exists? SITES_ENABLED_PATH
      FileUtils.mkdir_p SITES_ENABLED_PATH
    end

    # copy over certs for ssl
    # just copy files once to keep certificate as static.
    #`test ! -e #{NGINX_PATH}/mycert.pem && cp /etc/appscale/certs/mycert.pem #{NGINX_PATH}`
    #`test ! -e #{NGINX_PATH}/mykey.pem && cp /etc/appscale/certs/mykey.pem #{NGINX_PATH}`
    `cp /etc/appscale/certs/mykey.pem #{NGINX_PATH}`
    `cp /etc/appscale/certs/mycert.pem #{NGINX_PATH}`
    # Write the main configuration file which sets default configuration parameters
    File.open(MAIN_CONFIG_FILE, "w+") { |dest_file| dest_file.write(config) }
  end
end
