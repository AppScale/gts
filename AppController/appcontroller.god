
God.watch do |w|
  w.name = "appscale-controller-17443"
  w.group = "controller"
  w.interval = 30.seconds # default
  w.start = "ruby /root/appscale/AppController/djinnServer.rb"
  w.stop = "ruby /root/appscale/AppController/terminate.rb"
  w.log = "/var/log/appscale/controller-17443.log"
  w.pid_file = "/var/appscale/controller-17443.pid"

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

  w.env = {
    "APPSCALE_HOME" => "/root/appscale",
  }
end
