# Loki, a daemon that randomly kills other daemons
# to test fault-tolerance of AppScale components
# based on Netflix's Chaos Monkey
# http://techblog.netflix.com/2010/12/5-lessons-weve-learned-using-aws.html

# Programmer: Chris Bunch

# components to kill:
# blobstore
# uaserver
# pbserver
# appcontroller
# appserver python
# appserver java
# appdb
# memcached
# apploadbalancer
# TODO: nginx and haproxy also?

PROCESS_NAMES = {
  :blobstore => "blobstore_server.py",
  :uaserver => "soap_server.py",
  :pbserver => "appscale_server.py",
  #:appcontroller => "djinnServer.rb",
  #:appserver_python => "dev_appserver.py",
  #:appserver_java => "",
  #:appdb => "",
  :memcached => "memcached",
  #:apploadbalancer => "mongrel_rails"
}

def kill_process(name)
  proc_name = PROCESS_NAMES[name]
  command = "ps ax | grep #{proc_name} | grep -v grep | awk '{print $1}' | xargs kill -9"
  puts "Killing #{name}"
  `#{command}`
end

if ARGV[0].nil?
  use_random = true
else
  use_random = false
end

appscale_procs = PROCESS_NAMES.keys
num_procs = appscale_procs.length
should_break = false

trap('INT') {
  puts "Stopping the chaos for now..."
  should_break = true
}

index = 0

loop {
  index = rand(num_procs) if use_random

  proc_to_kill = appscale_procs[index]
  kill_process(proc_to_kill)
  puts "Sleeping...allowing #{proc_to_kill} to regenerate..."
  sleep(1)
  break if should_break

  unless use_random
    index += 1
    index %= num_procs
  end
}

