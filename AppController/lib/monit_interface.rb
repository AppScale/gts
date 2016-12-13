#!/usr/bin/ruby -w

# Imports within Ruby's standard libraries.
require 'monitor'
require 'tmpdir'

# Imports AppScale's libraries.
require 'helperfunctions'


# Where we save the configuration file.
MONIT_CONFIG = "/etc/monit/conf.d"


# Monit is finicky when it comes to multiple commands at the same time.
# Let's make sure we serialize access.
MONIT_LOCK = Monitor.new()


# Monit requires a bit of time after doing a reload to ensure no request
# is lost.
SMALL_WAIT = 2


# AppScale uses monit to start processes, restart them if they die, or kill and
# restart them if they take up too much CPU or memory. This module abstracts
# away interfacing with monit directly.
module MonitInterface

  
  # The location on the local filesystem of the monit executable.
  MONIT = "/usr/bin/monit"

  def self.start_monit()
    ret = system("service --status-all 2> /dev/null | grep monit | grep + > /dev/null")
    self.run_cmd("service monit start") unless ret
    return ret
  end
  
  def self.start(watch, start_cmd, stop_cmd, ports, env_vars, match_cmd, mem,
    pidfile, timeout)

    ports.each { |port|
      self.write_monit_config(watch, start_cmd, stop_cmd, port,
        env_vars, match_cmd, mem, pidfile, timeout)
    }

    self.run_cmd("#{MONIT} start -g #{watch}")
  end

  def self.start_file(watch, path, action, hours=12)
    contents = <<BOO
check file #{watch} path "#{path}" every 2 cycles
  group #{watch}
  if timestamp > 12 hours then exec "#{action}"
BOO
    monit_file = "#{MONIT_CONFIG}/appscale-#{watch}.cfg"
    HelperFunctions.write_file(monit_file, contents)
    Djinn.log_run("service monit reload")

    Djinn.log_info("Watching file #{path} for #{watch}" +
      " with exec action [#{action}]")

    Djinn.log_run("#{MONIT} start -g #{watch}")
  end

  def self.restart(watch)
    self.run_cmd("#{MONIT} restart -g #{watch}")
  end

  # This function unmonitors and optionally stops the service, and removes
  # the monit configuration file.
  def self.stop(watch, stop=true)
    # To make sure the service is stopped, we query monit till the service
    # is not any longer running.
    running = true
    while running
      if stop
        Djinn.log_info("stop_monitoring: stopping service #{watch}.")
        self.run_cmd("#{MONIT} stop -g #{watch}")
      else
        Djinn.log_info("stop_monitoring: unmonitor service #{watch}.")
        self.run_cmd("#{MONIT} unmonitor -g #{watch}")
      end

      10.downto(0) {
        if not self.is_running?(watch)
          running = false
          break
        end
        Djinn.log_debug("Waiting for monit to stop #{watch}.")
        Kernel.sleep(SMALL_WAIT)
      }
    end

    # Now let's find the corresponding configuration file and remove it.
    config = Dir::glob("#{MONIT_CONFIG}/appscale-#{watch}*")
    if config.length > 1
      Djinn.log_info("Found multiple monit config matches for #{watch}: #{config}.")
    end
    FileUtils.rm_rf(config)
    self.run_cmd('service monit reload', true)
  end


  def self.write_monit_config(watch, start_cmd, stop_cmd, port,
    env_vars, match_cmd, mem, pidfile, timeout)

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

    match_str = %Q[MATCHING "#{match_cmd}"]
    match_str = "PIDFILE #{pidfile}" unless pidfile.nil?

    start_line = %Q[start program = "#{full_start_command}"]
    start_line += " with timeout #{timeout} seconds" unless timeout.nil?

    contents = <<BOO
CHECK PROCESS #{watch}-#{port} #{match_str}
  group #{watch}
  #{start_line}
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

    monit_file = "#{MONIT_CONFIG}/appscale-#{watch}-#{port}.cfg"
    changing_config = true
    if File.file?(monit_file)
      current_contents = File.open(monit_file).read()
      changing_config = false if contents == current_contents
    end

    if changing_config
      HelperFunctions.write_file(monit_file, contents)
      self.run_cmd('service monit reload', true)
    end

    Djinn.log_info("Starting #{watch} on port #{port}" +
      " with start command [#{start_cmd}] and stop command [#{stop_cmd}]")
  end

  def self.is_running?(watch)
    output = self.run_cmd("#{MONIT} summary | grep #{watch} | grep -E '(Running|Initializing)'")
    return (not output == "")
  end

  # This function returns a list of running applications: the
  # dev_appservers needs to still be monitored by monit.
  # Returns:
  #   A list of application:port records.
  def self.running_appengines()
    appengines = []
    output = self.run_cmd("#{MONIT} summary | grep -E 'app___.*(Running|Initializing)'")
    appengines_raw = output.gsub! /Process 'app___(.*)-([0-9]*).*/, '\1:\2'
    if appengines_raw
      appengines_raw.split("\n").each{ |appengine|
        appengines << appengine if !appengine.split(":")[1].nil?
      }
    end

    Djinn.log_debug("Found these appservers processes running: #{appengines}.")
    return appengines
  end

  private
  def self.run_cmd(cmd, sleep=false)
    output = ""
    MONIT_LOCK.synchronize {
      output = Djinn.log_run(cmd)
      # Some command (ie reload) requires some extra time to ensure monit
      # is ready for the subsequent command.
      Kernel.sleep(SMALL_WAIT) if sleep
    }
    return output
  end
end
