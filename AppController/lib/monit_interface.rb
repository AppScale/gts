#!/usr/bin/ruby -w


require 'helperfunctions'


# A constant that we use to indicate that we want the output produced
# by remotely executed SSH commands.
WANT_OUTPUT = true


# A constant that we use to indicate that we do not want the output
# produced by remotely executed SSH commands.
NO_OUTPUT = false


# AppScale uses monit to start processes, restart them if they die, or kill and
# restart them if they take up too much CPU or memory. This module abstracts
# away interfacing with monit directly.
module MonitInterface

  
  # The location on the local filesystem of the monit executable.
  MONIT = "/usr/bin/monit"

  def self.start_monit(remote_ip, remote_key)
    self.execute_remote_command("service monit start", remote_ip, remote_key)
  end
  
  def self.start(watch, start_cmd, stop_cmd, ports, env_vars=nil,
    remote_ip=nil, remote_key=nil, match_cmd=start_cmd)

    ports = [ports] unless ports.class == Array
    ports.each { |port|
      self.write_monit_config(watch, start_cmd, stop_cmd, port,
        env_vars, remote_ip, remote_key, match_cmd)
    }

    self.execute_remote_command("#{MONIT} start -g #{watch}", remote_ip, remote_key)
  end

  def self.restart(watch, remote_ip=nil, remote_key=nil)
    self.execute_remote_command("#{MONIT} restart -g #{watch}", remote_ip, remote_key)
  end

  def self.write_monit_config(watch, start_cmd, stop_cmd, port,
    env_vars, remote_ip, remote_key, match_cmd)

    # Monit doesn't support environment variables in its DSL, so if the caller
    # wants environment variables passed to the app, we have to collect them and
    # prepend it to the executable string.
    env_vars_str = ""
    if !env_vars.nil? and env_vars.length > 0
      env_vars.each { |key, value|
        env_vars_str += "#{key}=#{value} "
      }
    end

    logfile = "/var/log/appscale/#{watch}-#{port}.log"
    
    # To get monit to capture standard out and standard err from processes it
    # monitors, we have to have bash exec it, and pipe stdout/stderr to a file.
    # Note that we can't just do 2>&1 - monit won't capture stdout or stderr if
    # we do this.
    full_start_command = "/bin/bash -c '#{env_vars_str} #{start_cmd} " +
      "1>>#{logfile} 2>>#{logfile}'"

    contents = <<BOO
check process #{watch}-#{port} matching "#{match_cmd}"
  group #{watch}
  start program = "#{full_start_command}"
  stop program = "#{stop_cmd}"
BOO

    monit_file = "/etc/monit/conf.d/#{watch}-#{port}.cfg"
    if remote_ip
      tempfile = "/tmp/monit-#{watch}-#{port}.cfg"
      HelperFunctions.write_file(tempfile, contents)
      begin
        HelperFunctions.scp_file(tempfile, monit_file, remote_ip, remote_key)
      rescue AppScaleSCPException
        Djinn.log_error("Failed to write monit file at #{remote_ip}")
        Djinn.log_run("rm -rf #{tempfile}")
        raise AppScaleSCPException.new("Failed to write monit file at #{remote_ip}")
      end
      Djinn.log_run("rm -rf #{tempfile}")
    else
      HelperFunctions.write_file(monit_file, contents)
    end

    self.execute_remote_command("service monit reload", remote_ip, remote_key)

    ip = remote_ip || HelperFunctions.local_ip
    Djinn.log_info("Starting #{watch} on ip #{ip}, port #{port}" +
      " with start command [#{start_cmd}] and stop command [#{stop_cmd}]")
  end

  def self.stop(watch, remote_ip=nil, remote_key=nil)
    self.execute_remote_command("#{MONIT} stop -g #{watch}", remote_ip, remote_key)
  end

  def self.remove(watch, remote_ip=nil, remote_key=nil)
    self.execute_remote_command("#{MONIT} stop -g #{watch}", remote_ip, remote_key)
    self.execute_remote_command("#{MONIT} unmonitor -g #{watch}", remote_ip, remote_key)
  end

  def self.shutdown(remote_ip=nil, remote_key=nil)
    self.execute_remote_command("#{MONIT} stop all", remote_ip, remote_key)
    self.execute_remote_command("#{MONIT} unmonitor all", remote_ip, remote_key)
    self.execute_remote_command("#{MONIT} quit", remote_ip, remote_key)
  end

  def self.is_running(watch, remote_ip=nil, remote_key=nil)
    output = self.execute_remote_command("#{MONIT} summary | grep '#{watch} " +
      "| grep Running'", remote_ip, remote_key)
    return not output == ""
  end

  private
  def self.execute_remote_command(cmd, ip, ssh_key)
    local = ip.nil?
    
    if local
      output = Djinn.log_run(cmd)
    else
      output = HelperFunctions.run_remote_command(ip, cmd, ssh_key, WANT_OUTPUT)
      Djinn.log_debug("running command #{cmd} on ip #{ip} returned #{output}")
    end

    return output
  end
end
