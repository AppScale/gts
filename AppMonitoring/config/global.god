# Heavily borrowed from Chris Anderson's AppDrop God config file

APPSCALE_HOME=ENV['APPSCALE_HOME']
RAILS_ROOT = File.expand_path("#{APPSCALE_HOME}/AppMonitoring")

%w{8003}.each do |port|
  God.watch do |w|
    w.name = "appscale-monitoring-#{port}"
    w.group = 'monitoring'
    w.interval = 30.seconds # default      
    w.start = "/usr/bin/mongrel_rails start -c #{RAILS_ROOT} -e production -p #{port} \
      -P #{RAILS_ROOT}/log/mongrel.#{port}.pid  -d"
    w.stop = "/usr/bin/mongrel_rails stop -P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
    w.restart = "/usr/bin/mongrel_rails restart -P #{RAILS_ROOT}/log/mongrel.#{port}.pid"
    w.start_grace = 20.seconds
    w.restart_grace = 20.seconds
    w.pid_file = File.join(RAILS_ROOT, "log/mongrel.#{port}.pid")
    
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
  end
end
