#!/usr/bin/ruby -w


require 'fileutils'


$:.unshift File.join(File.dirname(__FILE__))
require 'djinn_job_data'
require 'helperfunctions'
require 'monit_interface'


# Our implementation of the Google App Engine XMPP and Channel APIs uses the
# open source ejabberd server. This module provides convenience methods to
# start and stop ejabberd, and write its configuration files.
module Ejabberd

  # Indicates an error when determining the version of ejabberd.
  class UnknownVersion < StandardError; end


  EJABBERD_PATH = File.join("/", "etc", "ejabberd")
  
  
  AUTH_SCRIPT_LOCATION = "#{EJABBERD_PATH}/ejabberd_auth.py"
  
  
  ONLINE_USERS_FILE = "/etc/appscale/online_xmpp_users"


  def self.start
    service = `which service`.chomp
    start_cmd = "#{service} ejabberd start"
    stop_cmd = "#{service} ejabberd stop"
    pidfile = '/var/run/ejabberd/ejabberd.pid'
    MonitInterface.start_daemon(:ejabberd, start_cmd, stop_cmd, pidfile)
  end

  def self.stop
    MonitInterface.stop(:ejabberd)
  end

  def self.clear_online_users
    Djinn.log_run("rm #{ONLINE_USERS_FILE}")
  end

  def self.does_app_need_receive?(app)
    begin
      version_details = ZKInterface.get_version_details(
        app, Djinn::DEFAULT_SERVICE, Djinn::DEFAULT_VERSION)
    rescue VersionNotFound
      return false
    end

    inbound_services = version_details.fetch('inboundServices', [])
    return true if inbound_services.include?('INBOUND_SERVICE_XMPP_MESSAGE')
    return inbound_services.include?('INBOUND_SERVICE_XMPP_PRESENCE')
  end

  def self.write_online_users_list(nodes)
    online_users = `ejabberdctl connected-users`
    HelperFunctions.write_file(ONLINE_USERS_FILE, online_users)

    return if nodes.nil?
    nodes.each { |node|
      next if node.is_shadow? # don't copy the file to itself
      ip = node.private_ip
      ssh_key = node.ssh_key
      HelperFunctions.scp_file(ONLINE_USERS_FILE, ONLINE_USERS_FILE, ip, ssh_key)
    }
  end


  def self.get_ejabberd_version
    version_re = /Version: (\d+)\./

    begin
      ejabberd_info = `dpkg -s ejabberd`
    rescue Errno::ENOENT
      raise Ejabberd::UnknownVersion.new('The dpkg command was not found')
    end

    match = version_re.match(ejabberd_info)
    raise Ejabberd::UnknownVersion.new('Unable to find version') if match.nil?

    begin
      major_version = Integer(match[1])
    rescue ArgumentError, TypeError
      raise Ejabberd::UnknownVersion.new('Invalid ejabberd version')
    end

    return major_version
  end

  def self.write_config_file(my_private_ip)
    config_file = 'ejabberd.yml'
    begin
      ejabberd_version = self.get_ejabberd_version
      config_file = 'ejabberd.cfg' if ejabberd_version < 14
    rescue Ejabberd::UnknownVersion => error
      Djinn.log_warn("Error while getting ejabberd version: #{error.message}")
    end

    template = "#{APPSCALE_HOME}/AppController/templates/#{config_file}"
    config = File.read(template)

    config.gsub!('APPSCALE-HOST', my_private_ip)
    config.gsub!('APPSCALE-CERTFILE',
                 "#{Djinn::APPSCALE_CONFIG_DIR}/ejabberd.pem")
    config.gsub!('APPSCALE-AUTH-SCRIPT', AUTH_SCRIPT_LOCATION)

    config_path = "/etc/ejabberd/#{config_file}"
    HelperFunctions.write_file(config_path, config)
    Djinn.log_run("chown ejabberd #{config_path}")
  end
end
