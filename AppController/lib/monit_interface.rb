#!/usr/bin/ruby -w


require 'helperfunctions'


# AppScale uses monit to start processes, restart them if they die, or kill and
# restart them if they take up too much CPU or memory. This module abstracts
# away interfacing with monit directly.
module MonitInterface

  def self.start_monit(remote_ip, remote_key)
    # TODO(cgb): Write startup=1 in /etc/default/monit
    # TODO(cgb): Write monit config with webserver on
    self.run_god_command("monit", remote_ip, remote_key)
  end
  
  def self.start(watch, process_name, start_cmd, stop_cmd, ports, env_vars=nil,
    remote_ip=nil, remote_key=nil)

    ports = [ports] unless ports.class == Array
    ports.each { |port|
      self.write_monit_config(watch, process_name, start_cmd, stop_cmd, port,
        env_vars, remote_ip, remote_key)
    }

    self.run_god_command("monit start #{watch}", remote_ip, remote_key)
  end

  def self.write_monit_config(watch, process_name, start_cmd, stop_cmd, port,
    env_vars, remote_ip, remote_key)

    contents = <<BOO
check process #{process_name} with pidfile /var/appscale/#{watch}-#{port}.pid
  group #{watch}
  start program = "#{start_cmd}"
  stop program = "#{stop_cmd}"
  if cpu is greater than 50% for 5 cycles then restart
  if memory is greater than 50% for 5 cycles then restart
BOO
=begin
    prologue = <<BOO
watch_name = "#{watch}"
BOO
  w.log = "/var/log/appscale/#{watch_name}-#{port}.log"

    if !env_vars.nil? and !env_vars.empty?
      env_vars_str = ""

      env_vars.each { |k, v|
        env_vars_str += "     \"#{k}\" => \"#{v}\",\n"
      }

      body += <<BOO

  w.env = {
    #{env_vars_str}
  }
BOO
    end

    epilogue = <<BAZ
end
end
BAZ
=end

    monit_file = "/etc/monit/conf.d/#{watch}-#{port}.cfg"
    if remote_ip
      tempfile = "/tmp/monit-#{watch}-#{port}.cfg"
      HelperFunctions.write_file(tempfile, contents)
      HelperFunctions.scp_file(tempfile, monit_file, remote_ip, remote_key)
      Djinn.log_run("rm -rf #{tempfile}")
    else
      HelperFunctions.write_file(monit_file, contents)
    end

    self.run_god_command("monit reload", remote_ip, remote_key)

    Djinn.log_info("Starting #{watch} on ip #{ip}, port #{port}" +
      " with start command [#{start_cmd}] and stop command [#{stop_cmd}]")
  end

  def self.stop(watch, remote_ip=nil, remote_key=nil)
    self.run_god_command("monit stop #{watch}", remote_ip, remote_key)
  end

  def self.remove(watch, remote_ip=nil, remote_key=nil)
    self.run_god_command("monit stop #{watch}", remote_ip, remote_key)
    self.run_god_command("monit unmonitor #{watch}", remote_ip, remote_key)
  end

  def self.shutdown(remote_ip=nil, remote_key=nil)
    self.run_god_command("monit stop all", remote_ip, remote_key)
    self.run_god_command("monit unmonitor all", remote_ip, remote_key)
    self.run_god_command("monit quit", remote_ip, remote_key)
  end

  private
  def self.run_god_command(cmd, ip, ssh_key)
    raise Exception.new("asfka")
    #local = ip.nil?
    
    #if local
    #  Djinn.log_run(cmd)
    #else
    #  output = HelperFunctions.run_remote_command(ip, cmd, ssh_key, WANT_OUTPUT)
    #  Djinn.log_debug("running command #{cmd} on ip #{ip} returned #{output}")
    #end
  end
end
