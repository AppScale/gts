#!/usr/bin/ruby -w

require 'fileutils'

$:.unshift File.join(File.dirname(__FILE__))
require 'node_info'
require 'helperfunctions'
require 'monit_interface'

# Our implementation of the Google App Engine XMPP and Channel APIs uses the
# open source ejabberd server. This module provides convenience methods to
# start and stop ejabberd, and write its configuration files.
module Ejabberd
  # Indicates an error when determining the version of ejabberd.
  class UnknownVersion < StandardError; end

  EJABBERD_PATH = File.join('/', 'etc', 'ejabberd')

  CONFIG_FILE = File.join(EJABBERD_PATH, 'ejabberdctl.cfg')

  AUTH_SCRIPT_LOCATION = "#{EJABBERD_PATH}/ejabberd_auth.py".freeze

  ONLINE_USERS_FILE = '/etc/appscale/online_xmpp_users'.freeze

  def self.start
    service = `which service`.chomp
    start_cmd = "#{service} ejabberd start"
    stop_cmd = "#{service} ejabberd stop"
    pidfile = '/var/run/ejabberd/ejabberd.pid'

    self.ensure_correct_epmd
    MonitInterface.start_daemon(:ejabberd, start_cmd, stop_cmd, pidfile)
  end

  def self.stop
    MonitInterface.stop(:ejabberd) if MonitInterface.is_running?(:ejabberd)
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

  def self.ensure_correct_epmd()
    # On Xenial, an older epmd daemon can get started that doesn't play well
    # with ejabberd. This makes sure that the compatible service is running.
    begin
      services = `systemctl list-unit-files`
      if services.include?('epmd.service')
        PosixPsutil::Process.processes.each { |process|
          begin
            next unless process.name == 'epmd'
            process.terminate if process.cmdline.include?('-daemon')
          rescue PosixPsutil::NoSuchProcess
            next
          end
        }
        `systemctl start epmd`
      end
    rescue Errno::ENOENT
      # Distros without systemd don't have systemctl, and they do not exhibit
      # the issue.
    end
  end

  def self.write_online_users_list(nodes)
    online_users = `ejabberdctl connected-users`
    HelperFunctions.write_file(ONLINE_USERS_FILE, online_users)

    return if nodes.nil?
    nodes.each { |node|
      next if node.is_shadow? # don't copy the file to itself
      ip = node.private_ip
      ssh_key = node.ssh_key
      HelperFunctions.scp_file(ONLINE_USERS_FILE, ONLINE_USERS_FILE,
                               ip, ssh_key)
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

    major_version
  end

  def self.update_ctl_config
    # Make sure ejabberd writes a pidfile.
    begin
      config = File.read(CONFIG_FILE)
      config.gsub!('#EJABBERD_PID_PATH=', 'EJABBERD_PID_PATH=')
      File.open(CONFIG_FILE, 'w') { |file| file.write(config) }
    rescue Errno::ENOENT
      Djinn.log_debug("#{CONFIG_FILE} does not exist")
    end
  end

  def self.write_config_file(domain, my_private_ip)
    config_file = 'ejabberd.yml'
    begin
      ejabberd_version = get_ejabberd_version
      config_file = 'ejabberd.cfg' if ejabberd_version < 14
    rescue Ejabberd::UnknownVersion => error
      Djinn.log_warn("Error while getting ejabberd version: #{error.message}")
    end

    template = "#{APPSCALE_HOME}/AppController/templates/#{config_file}"
    config = File.read(template)

    config.gsub!('APPSCALE-HOST', domain)
    if config_file == 'ejabberd.yml'
      config.gsub!('APPSCALE-PRIVATE-IP', my_private_ip)
    else
      # Convert IP address to Erlang tuple.
      ip_tuple = "{#{my_private_ip.gsub('.', ',')}}"
      config.gsub!('APPSCALE-PRIVATE-IP', ip_tuple)
    end
    config.gsub!('APPSCALE-CERTFILE',
                 "#{Djinn::APPSCALE_CONFIG_DIR}/ejabberd.pem")
    config.gsub!('APPSCALE-AUTH-SCRIPT', AUTH_SCRIPT_LOCATION)

    # Not all packages include mod_client_state.
    disable_mod_client_state = true
    arch = `uname -m`
    arch_dir = "/usr/lib/#{arch}-linux-gnu"
    if File.directory?(arch_dir)
      Dir.entries(arch_dir).each { |entry|
        full_path = File.join(arch_dir, entry)
        next unless entry.start_with?('ejabberd')
        next unless File.directory?(full_path)
        module_file = File.join(full_path, 'mod_client_state.beam')
        disable_mod_client_state = false if File.file?(module_file)
      }
    end
    if disable_mod_client_state
      config.gsub!(' mod_client_state: {}', ' ## mod_client_state: {}')
    end

    config_path = "/etc/ejabberd/#{config_file}"
    HelperFunctions.write_file(config_path, config)
    Djinn.log_run("chown ejabberd #{config_path}")
  end
end
