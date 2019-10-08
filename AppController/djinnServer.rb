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

  def on_init
    @djinn = Djinn.new

    # Expose AppController methods to the outside world
    add_method(@djinn, "is_done_initializing", "secret")
    add_method(@djinn, "receive_server_message", "timeout", "secret")
    add_method(@djinn, "is_appscale_terminated", "secret")
    add_method(@djinn, "run_terminate", "clean", "secret")
    add_method(@djinn, "get_role_info", "secret")
    add_method(@djinn, "get_app_info_map", "secret")
    add_method(@djinn, "relocate_version", "version_key", "http_port",
               "https_port", "secret")
    add_method(@djinn, "set_parameters", "layout", "options", "secret")
    add_method(@djinn, "get_cluster_stats_json", "secret")
    add_method(@djinn, "get_application_cron_info", "app_name", "secret")
    add_method(@djinn, "upload_app", "archived_file", "file_suffix", "secret")
    add_method(@djinn, "get_app_upload_status", "reservation_id", "secret")
    add_method(@djinn, "get_database_information", "secret")
    add_method(@djinn, "get_instance_info", "app_id", "secret")
    add_method(@djinn, "get_request_info", "version_key", "secret")
    add_method(@djinn, "get_all_public_ips", "secret")
    add_method(@djinn, "get_all_private_ips", "secret")
    add_method(@djinn, "get_online_users_list", "secret")
    add_method(@djinn, "start_roles_on_nodes", "ips_hash", "secret")
    add_method(@djinn, "gather_logs", "secret")
    add_method(@djinn, "run_groomer", "secret")
    add_method(@djinn, "get_property", "property_regex", "secret")
    add_method(@djinn, "set_property", "property_name", "property_value",
      "secret")
    add_method(@djinn, "deployment_id_exists", "secret")
    add_method(@djinn, "get_deployment_id", "secret")
    add_method(@djinn, "set_deployment_id", "secret")
    add_method(@djinn, "set_node_read_only", "read_only", "secret")
    add_method(@djinn, "set_read_only", "read_only", "secret")
    add_method(@djinn, "get_node_stats_json", "secret")
    add_method(@djinn, "reset_password", "username", "password", "secret")
    add_method(@djinn, "does_user_exist", "username", "secret")
    add_method(@djinn, "create_user", "username", "password", "account_type" ,"secret")
    add_method(@djinn, "set_admin_role", "username", "is_cloud_admin", "capabilities" ,"secret")
    add_method(@djinn, "primary_db_is_up", "secret")
    add_method(@djinn, "update_cron", "project_id", "secret")
  end
end

def run_server(server)
  begin
    server.start
  rescue => server_error
    Djinn.log_error(server_error.message)
    run_server(server)
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
unless ac_list.empty?
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

trap('EXIT') {
  Djinn.log_debug("Received TERM signal: stopping AppController.")
  server.shutdown
}

new_thread = Thread.new { run_server(server) }
server.djinn.job_start(secret)
new_thread.join()
