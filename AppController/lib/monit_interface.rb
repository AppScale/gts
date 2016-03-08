#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries.
require 'tmpdir'

# Imports AppScale's libraries.
require 'helperfunctions'


# A constant that we use to indicate that we want the output produced
# by remotely executed SSH commands.
WANT_OUTPUT = true


# AppScale uses monit to start processes, restart them if they die, or kill and
# restart them if they take up too much CPU or memory. This module abstracts
# away interfacing with monit directly.
module MonitInterface

  
  # The location on the local filesystem of the monit executable.
  MONIT = "/usr/bin/monit"

  def self.start_monit()
    self.execute_command("service monit start")
  end
  
  def self.start(watch, start_cmd, stop_cmd, ports, env_vars=nil,
    match_cmd=start_cmd, mem=nil)

    ports = [ports] unless ports.class == Array
    ports.each { |port|
      self.write_monit_config(watch, start_cmd, stop_cmd, port,
        env_vars, match_cmd, mem)
    }

    self.execute_command("#{MONIT} start -g #{watch}")
  end

  def self.start_file(watch, path, action, hours=12)
    contents = <<BOO
check file #{watch} path "#{path}" every 2 cycles
  group #{watch}
  if timestamp > 12 hours then exec "#{action}"
BOO
    monit_file = "/etc/monit/conf.d/appscale-#{watch}.cfg"
    HelperFunctions.write_file(monit_file, contents)

    self.execute_command("service monit reload")

    Djinn.log_info("Watching file #{path} for #{watch}" +
      " with exec action [#{action}]")


    self.execute_command("#{MONIT} start -g #{watch}")
  end

  def self.restart(watch)
    self.execute_command("#{MONIT} restart -g #{watch}")
  end

  def self.write_monit_config(watch, start_cmd, stop_cmd, port,
    env_vars, match_cmd, mem)

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
    # If we have a valid 'mem' option, set the max memory for this
    # process.
    begin
      max_mem = Integer(mem)
      contents += "\n  if totalmem > #{max_mem} MB for 10 cycles then restart"
    rescue
      # It was not an integer, ignoring it.
    end

    monit_file = "/etc/monit/conf.d/appscale-#{watch}-#{port}.cfg"
    changing_config = true
    if File.file?(monit_file)
      current_contents = File.open(monit_file).read()
      changing_config = false if contents == current_contents
    end

    if changing_config
      HelperFunctions.write_file(monit_file, contents)
      Djinn.log_run('service monit reload')
    end

    Djinn.log_info("Starting #{watch} on port #{port}" +
      " with start command [#{start_cmd}] and stop command [#{stop_cmd}]")
  end

  def self.stop(watch)
    self.execute_command("#{MONIT} stop -g #{watch}")
  end

  def self.remove(watch)
    self.execute_command("#{MONIT} stop -g #{watch}")
    self.execute_command("#{MONIT} unmonitor -g #{watch}")
  end

  def self.is_running?(watch)
    output = self.execute_command("#{MONIT} summary | grep #{watch} | grep Running")
    return (not output == "")
  end

  private
  def self.execute_command(cmd)
    output = Djinn.log_run(cmd)
    Djinn.log_debug("running command #{cmd} returned #{output}.")

    return output
  end
end
