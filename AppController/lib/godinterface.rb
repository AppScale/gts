#!/usr/bin/ruby -w


# Most daemons within AppScale aren't fault-tolerant, so to make them
# fault-tolerant, we use the open source process monitor god. This
# module hides away having to write god config files, deploying it, and
# sending config files to it.
module GodInterface

  def self.start_god(remote_ip, remote_key)
    self.run_god_command("god", remote_ip, remote_key)
  end

  def self.start(watch, start_cmd, stop_cmd, ports, env_vars=nil, remote_ip=nil, remote_key=nil)

    ports = [ports] unless ports.class == Array

    prologue = <<BOO
    WATCH = "#{watch}"
    START_CMD = "#{start_cmd}"
    STOP_CMD = "#{stop_cmd}"
    PORTS = [#{ports.join(', ')}]

BOO

    body = <<'BAZ'
    PORTS.each do |port|
      God.watch do |w|
        w.name = "#{WATCH}-#{port}"
        w.group = WATCH
        w.interval = 30.seconds # default      
        w.start = START_CMD
        w.stop = STOP_CMD
        w.start_grace = 20.seconds
        w.restart_grace = 20.seconds
        w.log = "/var/log/appscale/#{WATCH}-#{port}.log"
        w.pid_file = "/var/appscale/#{WATCH}-#{port}.pid"
    
        w.behavior(:clean_pid_file)

        w.start_if do |start|
          start.condition(:process_running) do |c|
            c.running = false
          end
        end
    
        w.restart_if do |restart|
          restart.condition(:memory_usage) do |c|
            c.above = 150.megabytes
            c.times = [3, 5] # 3 out of 5 intervals
          end
    
          restart.condition(:cpu_usage) do |c|
            c.above = 50.percent
            c.times = 5
          end
        end
    
        # lifecycle
        w.lifecycle do |on|
          on.condition(:flapping) do |c|
            c.to_state = [:start, :restart]
            c.times = 5
            c.within = 5.minute
            c.transition = :unmonitored
            c.retry_in = 10.minutes
            c.retry_times = 5
            c.retry_within = 2.hours
          end
        end
BAZ

    if !env_vars.nil? and !env_vars.empty?
      env_vars_str = ""

      env_vars.each { |k, v|
        env_vars_str += "          \"#{k}\" => \"#{v}\",\n"
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
    Djinn.log_debug(god_info)   

    self.run_god_command("god start #{watch}", remote_ip, remote_key)
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

