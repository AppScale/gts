#!/usr/bin/ruby -w

$VERBOSE = nil
# Imports within Ruby's standard libraries
require 'soap/rpc/httpserver'
require 'webrick/https'
require 'logger'
require 'soap/rpc/driver'
require 'yaml'

require 'net/http'
require 'openssl'

class Net::HTTP
  alias_method :old_initialize, :initialize
  def initialize(*args)
    old_initialize(*args)
    @ssl_context = OpenSSL::SSL::SSLContext.new
    @ssl_context.verify_mode = OpenSSL::SSL::VERIFY_NONE
  end
end


environment = YAML.load_file('/etc/appscale/environment.yaml')
environment.each { |k,v| ENV[k] = v }

APPSCALE_HOME = ENV['APPSCALE_HOME']

# Import for AppController
$:.unshift File.join(File.dirname(__FILE__))
require 'djinn'


# Imports for AppController libraries
$:.unshift File.join(File.dirname(__FILE__), "lib")
require 'helperfunctions'
require 'cron_helper'
require 'haproxy'
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
    add_method(@djinn, "get_app_info_map", "secret")
    add_method(@djinn, "relocate_app", "appid", "http_port", "https_port",
      "secret")
    add_method(@djinn, "kill", "stop_deployment", "secret")
    add_method(@djinn, "set_parameters", "djinn_locations",
      "database_credentials", "app_names", "secret")
    add_method(@djinn, "set_apps", "app_names", "secret")
    add_method(@djinn, "status", "secret")
    add_method(@djinn, "get_stats", "secret")
    add_method(@djinn, "get_stats_json", "secret")
    add_method(@djinn, "upload_app", "archived_file", "file_suffix", "email",
      "secret")
    add_method(@djinn, "get_app_upload_status", "reservation_id", "secret")
    add_method(@djinn, "get_database_information", "secret")
    add_method(@djinn, "get_api_status", "secret")
    add_method(@djinn, "stop_app", "app_name", "secret")
    add_method(@djinn, "update", "app_names", "secret")
    add_method(@djinn, "set_apps_to_restart", "apps_to_restart", "secret")
    add_method(@djinn, "get_all_public_ips", "secret")
    add_method(@djinn, "get_online_users_list", "secret")
    add_method(@djinn, "done_uploading", "appname", "location", "secret")
    add_method(@djinn, "is_app_running", "appname", "secret")
    add_method(@djinn, "backup_appscale", "backup_in_info", "secret")
    add_method(@djinn, "add_role", "new_role", "secret")
    add_method(@djinn, "remove_role", "old_role", "secret")
    add_method(@djinn, "start_roles_on_nodes", "ips_hash", "secret")
    add_method(@djinn, "gather_logs", "secret")
    add_method(@djinn, "add_routing_for_appserver", "app_id", "ip", "port",
      "secret")
    add_method(@djinn, "remove_appserver_from_haproxy", "app_id", "ip", "port",
      "secret")
    add_method(@djinn, "add_appserver_process", "app_id", "secret")
    add_method(@djinn, "remove_appserver_process", "app_id", "port", "secret")
    add_method(@djinn, "run_groomer", "secret")
    add_method(@djinn, "get_property", "property_regex", "secret")
    add_method(@djinn, "set_property", "property_name", "property_value",
      "secret")
    add_method(@djinn, "deployment_id_exists", "secret")
    add_method(@djinn, "get_deployment_id", "secret")
    add_method(@djinn, "set_deployment_id", "secret")
  end
end

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

# Before we try to bind, make sure that another AppController hasn't already
# started another AppController here, and if so, kill it.
ac_list = `ps ax | grep djinnServer.rb | grep ruby | grep -v #{Process.pid} | awk '{print $1}'`
if not ac_list.empty?
  `kill -9 #{ac_list}`
  # Give it few seconds to free the socket/port.
  sleep(3)
end

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

trap('TERM') {
  Djinn.log_debug("Received TERM signal: stopping node servies.")
  server.djinn.kill_sig_received = true
  server.shutdown
  server.djinn.kill(false, secret)
}

new_thread = Thread.new { server.start }
server.djinn.job_start(secret)
new_thread.join()
