#!/usr/bin/ruby -w


# A constant that we use to indicate that we want the output produced
# by remotely executed SSH commands.
WANT_OUTPUT = true


# A constant that we use to indicate that we do not want the output 
# produced by remotely executed SSH commands.
NO_OUTPUT = false


# Most daemons within AppScale aren't fault-tolerant, so to make them
# fault-tolerant, we use the open source process monitor god. This
# module hides away having to write god config files, deploying it, and
# sending config files to it.
module GodInterface

  def self.start_god(remote_ip, remote_key)
    self.run_god_command("nohup god --log /var/log/appscale/god.log -D &",
      remote_ip, remote_key)
  end
  
  # Lock prevents a race condition where services do not get started correctly
  # if done concurrently.
  def self.start(watch, start_cmd, stop_cmd, ports, env_vars=nil, remote_ip=nil,
    remote_key=nil)
    if !defined?(@@lock)
      @@lock = Monitor.new
    end

    @@lock.synchronize {
      ports = [ports] unless ports.class == Array

      prologue = <<BOO
watch_name = "#{watch}"
start_command = "#{start_cmd}"
stop_command = "#{stop_cmd}"
ports = [#{ports.join(', ')}]

BOO

    body = <<'BAZ'
ports.each do |port|
  God.watch do |w|
    w.name = "#{watch_name}-#{port}"
    w.group = watch_name
    w.start = start_command
    w.log = "/var/log/appscale/#{watch_name}-#{port}.log"
    w.keepalive(:memory_max => 150.megabytes)
BAZ

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

      config_file = prologue + body + epilogue
      tempfile = "/tmp/god-#{rand(10000)}.god"

      HelperFunctions.write_file(tempfile, config_file)

      if remote_ip
        HelperFunctions.scp_file(tempfile, tempfile, remote_ip, remote_key)
      end

      self.run_god_command("god load #{tempfile}", remote_ip, remote_key)
      Kernel.sleep(5)
      FileUtils.rm_f(tempfile)

      ip = remote_ip || HelperFunctions.local_ip
      if remote_ip
        remove = "rm -rf #{tempfile}"
        HelperFunctions.run_remote_command(ip, remove, remote_key, NO_OUTPUT)
      end

      god_info = "Starting #{watch} on ip #{ip}, port #{ports.join(', ')}" +
        " with start command [#{start_cmd}] and stop command [#{stop_cmd}]"
      Djinn.log_info(god_info)

      self.run_god_command("god start #{watch}", remote_ip, remote_key)
    }
  end

  def self.stop(watch, remote_ip=nil, remote_key=nil)
    self.run_god_command("god stop #{watch}", remote_ip, remote_key)
  end

  def self.remove(watch, remote_ip=nil, remote_key=nil)
    self.run_god_command("god remove #{watch}", remote_ip, remote_key)
  end

  def self.shutdown(remote_ip=nil, remote_key=nil)
    god_status = `god status`
    services = god_status.scan(/^([\w\d]+)/).flatten

    services.each { |service|
      self.run_god_command("god stop #{service}", remote_ip, remote_key)
    }

    self.run_god_command("god terminate", remote_ip, remote_key)
  end

  private
  def self.run_god_command(cmd, ip, ssh_key)
    local = ip.nil?
    
    if local
      Djinn.log_run(cmd)
    else
      output = HelperFunctions.run_remote_command(ip, cmd, ssh_key, WANT_OUTPUT)
      Djinn.log_debug("running command #{cmd} on ip #{ip} returned #{output}")
    end
  end
end
