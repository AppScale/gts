#!/usr/bin/ruby -w


# Imports within Ruby's standard libraries
require 'soap/rpc/httpserver'
require 'webrick/https'
require 'logger'
require 'soap/rpc/driver'

APPSCALE_HOME = ENV['APPSCALE_HOME']
ENV['EC2_HOME'] = "/usr/local/ec2-api-tools"
ENV['JAVA_HOME'] = "/usr/lib/jvm/java-6-openjdk"

# Import for AppController
$:.unshift File.join(File.dirname(__FILE__))
require 'djinn'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'helperfunctions'
require 'cron_helper'
require 'haproxy'
require 'collectd'
require 'nginx'


# DjinnServer is a wrapper around Djinn that adds SOAP capabilities to it.
class DjinnServer < SOAP::RPC::HTTPServer


  # The Djinn that this SOAP server wraps around.
  attr_reader :djinn


  def job
    @djinn.job
  end
  
  def djinn_locations
    @djinn.djinn_locations
  end

  def on_init
    @djinn = Djinn.new

    # Expose AppController methods to the outside world
    add_method(@djinn, "is_done_initializing", "secret")
    add_method(@djinn, "is_done_loading", "secret")
    add_method(@djinn, "get_role_info", "secret")
    add_method(@djinn, "kill", "secret")    
    add_method(@djinn, "set_parameters", "djinn_locations", "database_credentials", "app_names", "secret")
    add_method(@djinn, "set_apps", "app_names", "secret")
    add_method(@djinn, "status", "secret")
    add_method(@djinn, "get_stats", "secret")
    add_method(@djinn, "stop_app", "app_name", "secret")
    add_method(@djinn, "update", "app_names", "secret")
    add_method(@djinn, "get_all_public_ips", "secret")
    add_method(@djinn, "get_online_users_list", "secret")
    add_method(@djinn, "done_uploading", "appname", "location", "secret")
    add_method(@djinn, "is_app_running", "appname", "secret")
    add_method(@djinn, "backup_appscale", "backup_in_info", "secret")
    add_method(@djinn, "add_role", "new_role", "secret")
    add_method(@djinn, "remove_role", "old_role", "secret")
  end
end

`rm -rf /tmp/h*`
`rm -f ~/.appscale_cookies`
`rm -f #{APPSCALE_HOME}/.appscale/status-*`
`rm -f #{APPSCALE_HOME}/.appscale/database_info`
`rm -f /tmp/mysql.sock`
Nginx.clear_sites_enabled
Collectd.clear_sites_enabled
HAProxy.clear_sites_enabled
`echo '' > /root/.ssh/known_hosts` # empty it out but leave the file there
CronHelper.clear_crontab

appscale_dir = "/etc/appscale/"

secret = nil
loop {
  secret = HelperFunctions.get_secret(appscale_dir + "secret.key")
  break unless secret.nil?
  Djinn.log_debug("Still waiting for that secret key...")
  sleep(5)
}

server_cert = nil
server_key = nil
loop {
  server_cert = HelperFunctions.get_cert(appscale_dir + "certs/mycert.pem")
  server_key = HelperFunctions.get_key(appscale_dir + "certs/mykey.pem")
  break if !server_cert.nil? && !server_key.nil?
  Djinn.log_debug("Waiting on certs")
  sleep(5)
}

server = DjinnServer.new(
  :BindAddress => "0.0.0.0",
  :Port => Djinn::SERVER_PORT,
  :AccessLog => [],
  :SSLEnable => true,
  :SSLCertificate => server_cert,
  :SSLPrivateKey => server_key,
  :SSLVerifyClient => nil,
  :SSLCertName => nil
)

trap('INT') {
  Djinn.log_debug("Received INT signal, shutting down server")
  server.djinn.kill_sig_received = true
  server.shutdown 
  server.djinn.kill(secret)
}

new_thread = Thread.new { server.start }
server.djinn.job_start(secret)
new_thread.join()
