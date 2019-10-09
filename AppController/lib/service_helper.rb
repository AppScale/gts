$:.unshift File.join(File.dirname(__FILE__))
require 'helperfunctions'

# Serialize access.
SERVICE_LOCK = Monitor.new

# AppScale uses systemd to start processes, restart them if they die, or kill and
# restart them if they take up too much CPU or memory.
module ServiceHelper
  SYSTEMCTL = 'systemctl'.freeze

  def self.start(name, ports = nil)
    command_and_args = if name.start_with?('appscale-') then '--runtime --now enable' else 'start' end
    ports = [nil] if ports.nil?
    ports.each { |port|
      service_name = if port.nil? then name.to_s else "#{name.to_s}#{port}" end
      run_cmd("#{SYSTEMCTL} #{command_and_args} #{expand_name(service_name)}")
    }
  end

  def self.restart(name, start = true)
    restart_command = if start then "restart" else "try-restart" end
    service_name_match = if name.end_with?('@') then "#{name.to_s}*" else name.to_s end
    run_cmd("#{SYSTEMCTL} #{restart_command} #{expand_name(service_name_match)}")
  end

  def self.reload(name, start = false)
    reload_command = if start then "reload-or-restart" else "try-reload-or-restart" end
    service_name_match = if name.end_with?('@') then "#{name.to_s}*" else name.to_s end
    run_cmd("#{SYSTEMCTL} #{reload_command} #{expand_name(service_name_match)}")
  end

  def self.stop(name)
    command_and_args = if name.start_with?('appscale-') then '--runtime --now disable' else 'stop' end
    service_name_match = if name.end_with?('@') then "#{name.to_s}*" else name.to_s end
    run_cmd("#{SYSTEMCTL} #{command_and_args} #{expand_name(service_name_match)}")
  end

  def self.is_running?(name, port = nil)
    service_name_match = if name.end_with?('@') then if port.nil? then "#{name.to_s}*" else "#{name.to_s}#{port}" end else name.to_s end
    output = run_cmd("#{SYSTEMCTL} is-active #{expand_name(service_name_match)}")
    not (output =~ /^active$/).nil?
  end

  # This function returns a list of running services
  #
  # If name is a "template" (e.g. appscale-myservice@) then multiple
  # services could be matched.
  #
  # If name is a regular service there will be at most one running service.
  def self.running(name)
    services = []
    service_name_match = if name.end_with?('@') then "#{name.to_s}*" else name.to_s end
    output = run_cmd("#{SYSTEMCTL} --state=active --plain --no-pager --no-legend list-units #{service_name_match}")
    services_raw = output.gsub! /(.*)\.service .*/, '\1'
    if services_raw
      services = services_raw.split("\n")
    end
    services
  end

  def self.write_environment(name, environment = nil)
    env_contents = ''
    unless environment.nil?
      env_contents = environment.map{|k,v| "#{k}=#{v}\n"}.join('')
    end
    HelperFunctions.write_file(
      "#{HelperFunctions::APPSCALE_RUN_DIR}/#{name}.env",
      env_contents)
  end

  private

  def self.expand_name(name)
    expanded = name
    expanded = "#{name}.service" unless name.include?('.')
    expanded
  end

  def self.run_cmd(cmd, sleep = false)
    output = ''
    SERVICE_LOCK.synchronize {
      output = Djinn.log_run(cmd)
    }
    output
  end
end

