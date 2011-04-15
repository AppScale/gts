#!/usr/bin/ruby -w

require 'soap/rpc/httpserver'
require 'webrick/https'
require 'logger'
require 'soap/rpc/driver'

$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'
require 'cron_helper'
require 'djinn'
require 'haproxy'
require 'collectd'
require 'nginx'

$VERBOSE = nil # to supress excessive SSL cert warnings

NEPTUNE_JOBS = ["appscale", "compile", "erlang", "mpi", "mapreduce", "dfsp", "cewssa", "output", "acl", "input"]

class DjinnServer < SOAP::RPC::HTTPServer
  attr_reader :djinn
  
  def job
    @djinn.job
  end
  
  def djinn_locations
    @djinn.djinn_locations
  end

  def on_init
    @djinn = Djinn.new
    add_method(@djinn, "done", "secret")
    add_method(@djinn, "kill", "secret")    
    add_method(@djinn, "set_parameters", "djinn_locations", "database_credentials", "app_names", "secret")
    add_method(@djinn, "set_apps", "app_names", "secret")
    add_method(@djinn, "status", "secret")
    add_method(@djinn, "stop_app", "app_name", "secret")
    add_method(@djinn, "update", "app_names", "secret")
    add_method(@djinn, "get_all_public_ips", "secret")
    add_method(@djinn, "get_online_users_list", "secret")
    add_method(@djinn, "done_uploading", "appname", "location", "secret")
    add_method(@djinn, "is_app_running", "appname", "secret")
    add_method(@djinn, "backup_appscale", "backup_in_info", "secret")
    add_method(@djinn, "backup_database_state", "backup_info", "secret")
    add_method(@djinn, "add_role", "new_role", "secret")
    add_method(@djinn, "remove_role", "old_role", "secret")

    add_method(@djinn, "neptune_start_job", 'job_data', 'secret')
    add_method(@djinn, "neptune_is_job_running", "job_data", "secret")
    add_method(@djinn, "neptune_put_input", "job_data", "secret")
    add_method(@djinn, "neptune_get_output", "job_data", "secret")
    add_method(@djinn, "neptune_get_acl", "job_data", "secret")
    add_method(@djinn, "neptune_set_acl", "job_data", "secret")
    add_method(@djinn, "neptune_compile_code", "job_data", "secret")

    NEPTUNE_JOBS.each { |name|
      add_method(@djinn, "neptune_#{name}_run_job", "nodes", "job_data", "secret")
    }
  end
end

`cp #{APPSCALE_HOME}/AppDB/logs/pb_server.log /tmp/pb_backup.log`
`service appscale-loadbalancer stop`
`pkill -9 java; pkill -9 python; rm -rf /tmp/h*`
`pkill -9 python2.6; pkill -9 python2.5; pkill -9 memcached`
`rm -f ~/.appscale_cookies`
`rm -f #{APPSCALE_HOME}/.appscale/status-*`
`rm -f #{APPSCALE_HOME}/.appscale/database_info`
`rm -f /tmp/mysql.sock`
Nginx.clear_sites_enabled
Collectd.clear_sites_enabled
HAProxy.clear_sites_enabled
`pkill -9 mongod; pkill -9 mongo`
`echo '' > /root/.ssh/known_hosts` # empty it out but leave the file there
CronHelper.clear_crontab

appscale_dir = File.expand_path("#{APPSCALE_HOME}/.appscale") + File::Separator

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

# can't have the djinn pid file end in .pid since a user could upload an
# app called djinn, whose pid would then be stored in djinn.pid by 
# helperfunctions and mess things up

pid_file = appscale_dir + "djinn.id"
if File.exists?(pid_file)
  pid = (File.open(pid_file) { |f| f.read }).chomp
  `kill -9 #{pid}`
end
sleep(2)

new_pid = `ps ax | grep [d]jinnServer | mawk '{ print $1 } '`
File.open(pid_file, "w+") { |file| file.write(new_pid) }

server = DjinnServer.new(
  :BindAddress => "0.0.0.0",
  :Port => 17443,
  :AccessLog => [],
  :SSLEnable => true,
  :SSLCertificate => server_cert,
  :SSLPrivateKey => server_key,
  :SSLVerifyClient => nil,
  :SSLCertName => nil
)
#rescue Errno::EADDRINUSE
#  pid = `ps ax | grep djinnServer | grep -v grep | awk '{ print $1 } '`
#  Djinn.log_debug("Killing process with pid [#{pid}]")
#  `kill -9 #{pid}`
#  sleep(5)
#  retry
#end

shutdown_yet = false

trap('INT') {
  Djinn.log_debug("Received INT signal, shutting down server")
  server.djinn.kill_sig_received = true
  server.shutdown 
  server.djinn.kill(secret)
}

new_thread = Thread.new { server.start }
server.djinn.job_start(secret)
new_thread.join

